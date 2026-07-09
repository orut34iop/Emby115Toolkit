import logging
import os
import re
import shutil
import threading
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import requests

from media_server.genre_maps import MOVIE_GENRE_TRANSLATIONS, TV_GENRE_TRANSLATIONS

# 定义视频文件扩展名
VIDEO_EXTENSIONS = {
    '.mp4',
    '.mkv',
    '.avi',
    '.mov',
    '.wmv',
    '.flv',
    '.mpeg',
    '.mpg',
    '.iso',
    '.ts',
    '.rmvb',
    '.rm',
    '.m4v',
    '.m2ts',
    '.webm',
    '.3gp',
    '.vob',
    '.divx',
    '.f4v',
    '.ogv',
    '.mxf',
    '.asf',
    '.mts',
}

GENRE_NORMALIZATION_TRANSLATION = str.maketrans(
    {
        '　': ' ',
        '・': '·',
        '･': '·',
        '•': '·',
        '／': '/',
        '，': ',',
        '（': '(',
        '）': ')',
        '獨': '独',
        '專': '专',
        '屬': '属',
        '優': '优',
        '顔': '颜',
        '顏': '颜',
        '騎': '骑',
        '乗': '乘',
        '貧': '贫',
        '觀': '观',
        '視': '视',
        '攝': '摄',
        '內': '内',
        '陰': '阴',
        '陽': '阳',
        '義': '义',
        '婦': '妇',
        '處': '处',
        '処': '处',
        '劇': '剧',
        '複': '复',
        '復': '复',
        '無': '无',
        '長': '长',
        '個': '个',
        '畫': '画',
        '質': '质',
        '體': '体',
        '驗': '验',
        '懺': '忏',
        '係': '系',
        '統': '统',
        '國': '国',
        '進': '进',
        '業': '业',
        '餘': '余',
        '寫': '写',
        '製': '制',
        '單': '单',
        '爐': '炉',
        '別': '别',
        '轉': '转',
        '為': '为',
        '薦': '荐',
        '頻': '频',
        '設': '设',
        '項': '项',
        '臉': '脸',
        '後': '后',
        '護': '护',
        '師': '师',
        '嬌': '娇',
        '莖': '茎',
        '戀': '恋',
        '愛': '爱',
        '眾': '众',
        '學': '学',
        '時': '时',
        '問': '问',
        '價': '价',
        '經': '经',
        '數': '数',
        '碼': '码',
        '錄': '录',
        '紀': '纪',
        '風': '风',
        '孃': '娘',
        '緊': '紧',
        '縛': '缚',
        '親': '亲',
        '姦': '奸',
        '職': '职',
        '場': '场',
        '與': '与',
        '馬': '马',
        '賽': '赛',
        '異': '异',
        '導': '导',
        '醫': '医',
        '檢': '检',
        '查': '查',
        '飲': '饮',
        '聯': '联',
        '誼': '谊',
    }
)


class RequestFailureResponse:
    def __init__(self, error):
        self.status_code = 0
        self.text = f"请求异常: {error}"


class MediaServerClient:
    def __init__(
        self,
        server_url=None,
        api_key=None,
        username=None,
        delete_nfo=False,
        delete_nfo_folder=False,
        logger=None,
        server_type='emby',
    ):
        self.server_url = (server_url or "").rstrip("/")
        self.api_key = api_key
        self.username = username
        self.user_id = None
        self.delete_nfo = delete_nfo
        self.delete_nfo_folder = delete_nfo_folder
        self.logger = logger or logging.getLogger(__name__)
        self.server_type = self._normalize_server_type(server_type)
        self.detected_server_type = None
        self.api_prefix = self._configured_api_prefix()
        self.stop_flag = threading.Event()
        self._genre_lookup_index_cache = {}

    def _normalize_server_type(self, server_type):
        value = str(server_type or 'emby').strip().lower()
        return 'jellyfin' if value == 'jellyfin' else 'emby'

    def _configured_api_prefix(self):
        return '' if self.server_type == 'jellyfin' else '/emby'

    def request_stop(self):
        self.stop_flag.set()
        self.logger.info("已请求停止当前媒体服务器任务")

    def _start_background_task(self, target, task_name):
        self.stop_flag.clear()

        def safe_target():
            try:
                target()
            except Exception as e:
                self.logger.exception(f"{task_name}执行异常: {e}")

        thread = threading.Thread(target=safe_target, daemon=True)
        thread.start()
        return thread

    def _auth_headers(self):
        return {
            'X-Emby-Token': self.api_key or '',
            'X-MediaBrowser-Token': self.api_key or '',
            'Content-Type': 'application/json',
        }

    def _api_url(self, path, prefix=None):
        if not path.startswith('/'):
            path = f'/{path}'
        if prefix is None:
            prefix = self.api_prefix or ''
        return f'{self.server_url}{prefix}{path}'

    def _server_label(self):
        return 'Jellyfin' if self.server_type == 'jellyfin' else 'Emby'

    def detect_server_type(self, force=False):
        """检测当前服务器是 Emby 还是 Jellyfin，仅用于校验用户选择。"""
        if self.detected_server_type and not force:
            return self.detected_server_type
        if force:
            self.detected_server_type = None

        info_paths = [
            ('', '/System/Info/Public'),
            ('/emby', '/System/Info/Public'),
        ]
        for prefix, path in info_paths:
            url = self._api_url(path, prefix)
            try:
                response = requests.get(url, timeout=10)
            except requests.exceptions.RequestException as err:
                self.logger.warning(f"服务器识别请求失败: {url} - {err}")
                continue

            if response.status_code != 200:
                continue

            try:
                info = response.json()
            except ValueError:
                self.logger.warning(f"服务器识别响应不是 JSON: {url}")
                continue

            product_text = " ".join(
                str(info.get(key, '')) for key in ('ProductName', 'ServerName', 'OperatingSystemDisplayName', 'Version')
            ).lower()

            if 'jellyfin' in product_text:
                self.detected_server_type = 'jellyfin'
                self.logger.info("已检测到服务器类型: Jellyfin")
                return self.detected_server_type

            if 'emby' in product_text:
                self.detected_server_type = 'emby'
                self.logger.info("已检测到服务器类型: Emby")
                return self.detected_server_type

        self.logger.error("无法检测服务器类型，请检查服务器地址和 API Key")
        return None

    def validate_server_type(self):
        detected_type = self.detect_server_type(force=True)
        expected_label = self._server_label()

        if not detected_type:
            raise RuntimeError("无法检测服务器类型，请检查服务器地址或 API Key")

        detected_label = 'Jellyfin' if detected_type == 'jellyfin' else 'Emby'
        if detected_type != self.server_type:
            raise RuntimeError(
                f"服务器类型选择不一致：当前选择 {expected_label}，实际检测到 {detected_label}，请修改单选框后重试。"
            )

        self.logger.info(f"服务器类型校验通过: {expected_label}")
        return True

    def _request(self, method, path, *, params=None, data=None, json_body=None, timeout=30):
        headers = self._auth_headers()
        url = self._api_url(path)
        return requests.request(method, url, headers=headers, params=params, data=data, json=json_body, timeout=timeout)

    def _request_with_retries(
        self,
        method,
        path,
        *,
        params=None,
        data=None,
        json_body=None,
        timeout=30,
        retries=0,
        retry_delay=1,
        retry_status_codes=None,
        retry_label=None,
    ):
        retry_status_codes = retry_status_codes or set()
        for attempt in range(retries + 1):
            try:
                response = self._request(method, path, params=params, data=data, json_body=json_body, timeout=timeout)
                if response.status_code not in retry_status_codes or attempt >= retries:
                    return response
                self.logger.warning(
                    f"{retry_label or path} 请求返回 {response.status_code}，"
                    f"{retry_delay} 秒后重试 {attempt + 1}/{retries}"
                )
            except requests.exceptions.RequestException as err:
                if attempt >= retries:
                    raise
                self.logger.warning(
                    f"{retry_label or path} 请求异常，{retry_delay} 秒后重试 {attempt + 1}/{retries}: {err}"
                )
            time.sleep(retry_delay)

    def _get_items(self, include_item_types, fields):
        params = {
            "api_key": self.api_key,
            "IncludeItemTypes": include_item_types,
            "Recursive": True,
            "Fields": fields,
            "Limit": "1000000",
        }
        try:
            response = self._request('get', '/Items', params=params)
            response.raise_for_status()
            return response.json().get("Items", [])
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error occurred: {http_err}")
        except requests.exceptions.RequestException as err:
            self.logger.error(f"Other error occurred: {err}")
        except ValueError:
            self.logger.error("Error parsing JSON response")
        return []

    def _prepare_item_update_payload(self, item):
        payload = dict(item)
        if self.server_type == 'jellyfin':
            # Jellyfin validates GenreItems as GUID pairs; Genres is enough for metadata update.
            payload.pop('GenreItems', None)
        return payload

    def _post_item_update(self, item_id, item):
        params = {"api_key": self.api_key}
        payload = self._prepare_item_update_payload(item)
        path = f"/Items/{urllib.parse.quote(str(item_id), safe='')}"
        try:
            return self._request_with_retries(
                'post',
                path,
                params=params,
                json_body=payload,
                timeout=(5, 45),
                retries=1,
                retry_delay=1,
                retry_status_codes={408, 429, 500, 502, 503, 504},
                retry_label=f"更新条目 {item.get('Name', item_id)}({item_id})",
            )
        except requests.exceptions.RequestException as err:
            return RequestFailureResponse(err)

    @staticmethod
    def _clean_genre_name(genre):
        text = str(genre or '').strip()
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _normalize_genre_name(genre):
        text = MediaServerClient._clean_genre_name(genre)
        text = text.translate(GENRE_NORMALIZATION_TRANSLATION)
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _normalize_genre_lookup_name(genre):
        text = unicodedata.normalize('NFKC', MediaServerClient._clean_genre_name(genre))
        text = text.translate(GENRE_NORMALIZATION_TRANSLATION)
        return re.sub(r'\s+', ' ', text).strip()

    def _genre_lookup_key(self, genre, genres_map, allow_normalized_index=True):
        if genre in genres_map:
            return genre

        normalized_genre = self._normalize_genre_lookup_name(genre)
        if normalized_genre in genres_map:
            return normalized_genre
        if not allow_normalized_index:
            return None

        map_id = id(genres_map)
        cached_map, cached_index = self._genre_lookup_index_cache.get(map_id, (None, None))
        if cached_map is not genres_map:
            cached_index = {}
            for key in genres_map:
                cached_index.setdefault(self._normalize_genre_lookup_name(key), key)
            self._genre_lookup_index_cache[map_id] = (genres_map, cached_index)

        return cached_index.get(normalized_genre)

    def _resolve_genre_translation(self, genre, genres_map):
        current = self._clean_genre_name(genre)
        seen = set()
        allow_normalized_index = True
        while True:
            lookup_key = self._genre_lookup_key(
                current,
                genres_map,
                allow_normalized_index=allow_normalized_index,
            )
            if not lookup_key:
                return self._normalize_genre_name(current)
            if lookup_key in seen:
                return self._normalize_genre_name(current)

            seen.add(lookup_key)
            translated = self._normalize_genre_name(genres_map[lookup_key])
            if translated == current:
                return translated
            current = translated
            allow_normalized_index = False

    def _translate_genres(self, genres, genres_map):
        translated_genres = []
        seen = set()
        for genre in genres:
            translated = self._resolve_genre_translation(genre, genres_map)
            if translated not in seen:
                translated_genres.append(translated)
                seen.add(translated)
        return translated_genres

    def _unique_items_by_id(self, items, item_label):
        unique_items = []
        seen_ids = set()
        duplicate_count = 0
        for item in items:
            item_id = item.get('Id')
            if item_id and item_id in seen_ids:
                duplicate_count += 1
                continue
            if item_id:
                seen_ids.add(item_id)
            unique_items.append(item)
        if duplicate_count:
            self.logger.info(f"{item_label}列表中跳过重复条目 {duplicate_count} 个")
        return unique_items

    @staticmethod
    def _should_report_progress(current, total, interval=500):
        if not total:
            return False
        if total <= 100:
            return True
        return current in {1, total} or current % interval == 0

    @staticmethod
    def _should_log_item_update(update_count, interval=100):
        return update_count <= 20 or update_count % interval == 0

    @staticmethod
    def _format_limited_values(values, max_items=200):
        sorted_values = sorted(values, key=lambda value: str(value))
        displayed_values = sorted_values[:max_items]
        suffix = f" ... 还有 {len(sorted_values) - max_items} 项未列出" if len(sorted_values) > max_items else ""
        return f"{displayed_values}{suffix}"

    @staticmethod
    def _format_updated_items_message(item_label, updated_items, max_items=100):
        if not updated_items:
            return f"没有需要更新的{item_label}流派信息。\n"

        displayed_items = updated_items[:max_items]
        updated_items_info = "\n".join(
            f"{item_label}: {item.get('Name', item.get('Id', ''))}" for item in displayed_items
        )
        omitted_count = len(updated_items) - max_items
        omitted_message = f"\n... 还有 {omitted_count} 个{item_label}已更新，省略写入日志。" if omitted_count > 0 else ""
        return (
            f"更新的{item_label}数量: {len(updated_items)}\n"
            f"更新的{item_label}（最多列出 {max_items} 个）:\n"
            f"{updated_items_info}{omitted_message}\n"
        )

    @staticmethod
    def _build_genre_item_index(items):
        all_genreitems = set()
        genre_item_ids = {}
        all_genres = set()

        for item in items:
            all_genres.update(item.get('Genres', []))
            for genre_item in item.get('GenreItems', []):
                name = genre_item.get('Name')
                gid = genre_item.get('Id')
                if name and gid:
                    all_genreitems.add((name, gid))
                    genre_item_ids.setdefault(name, gid)

        return all_genres, all_genreitems, genre_item_ids

    @staticmethod
    def _build_genre_items(translated_genres, genre_item_ids):
        return [{'Name': genre, 'Id': genre_item_ids.get(genre, '')} for genre in translated_genres]

    def _get_genre_update_items_response(self, include_item_types, params):
        if self.server_type != 'jellyfin':
            return self._request('get', '/Items', params=params)

        self.user_id = self.user_id or self.emby_get_user_id()
        if not self.user_id:
            self.logger.error("Failed to retrieve user ID.")
            return None

        path = f"/Users/{urllib.parse.quote(str(self.user_id), safe='')}/Items"
        return self._request('get', path, params=params)

    def _collect_genre_update_candidates(self, items, genres_map, item_label, progress_callback=None):
        candidates = []
        genre_changes = Counter()
        total_items = len(items)
        checked_count = 0

        for item in items:
            if self.stop_flag.is_set():
                return candidates, genre_changes, checked_count, True

            checked_count += 1
            original_genres = item.get('Genres', [])
            translated_genres = self._translate_genres(original_genres, genres_map)
            if original_genres != translated_genres:
                candidates.append(item)
                for genre in original_genres:
                    translated_genre = self._resolve_genre_translation(genre, genres_map)
                    if genre != translated_genre:
                        genre_changes[(genre, translated_genre)] += 1
                if len(original_genres) != len(translated_genres):
                    genre_changes[('重复或近似流派', '合并去重后的流派列表')] += 1

            if self._should_report_progress(checked_count, total_items):
                self._report_progress(
                    progress_callback,
                    checked_count,
                    total_items,
                    f"扫描{item_label}流派进度: {checked_count}/{total_items}，待更新 {len(candidates)} 部",
                    percent=self._progress_percent(checked_count, total_items, 0, 50),
                )

        return candidates, genre_changes, checked_count, False

    def _log_genre_change_summary(self, item_label, genre_changes, max_items=80):
        if not genre_changes:
            self.logger.info(f"{item_label}预扫描未发现需要翻译或合并的流派")
            return

        displayed_changes = [
            f"{source} -> {target}（{count}）"
            for (source, target), count in genre_changes.most_common(max_items)
        ]
        omitted_count = len(genre_changes) - max_items
        if omitted_count > 0:
            displayed_changes.append(f"... 还有 {omitted_count} 个变更项未列出")
        self.logger.info(f"{item_label}流派变更统计: {'; '.join(displayed_changes)}")

    def _translate_items_genres_and_update(
        self,
        item_label,
        include_item_types,
        genres_map,
        progress_callback=None,
        rescan_attempts=0,
    ):
        update_count = 0
        updated_items = []
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': include_item_types,
            'Fields': 'Genres,GenreItems',
            'Limit': '1000000',
        }

        response = self._get_genre_update_items_response(include_item_types, params)
        if response is None:
            return updated_items
        if response.status_code != 200:
            self.logger.error(f"请求失败，状态码: {response.status_code}")
            self.logger.error(response.text)
            return updated_items

        items = self._unique_items_by_id(response.json().get('Items', []), item_label)
        total_items = len(items)
        all_genres, all_genreitems, genre_item_ids = self._build_genre_item_index(items)
        self.logger.info(
            f"{item_label}所有去重后的Genres（{len(all_genres)} 个）: "
            f"{self._format_limited_values(all_genres)}"
        )
        self.logger.info(
            f"{item_label}所有去重后的GenreItems（{len(all_genreitems)} 个）: "
            f"{self._format_limited_values(all_genreitems)}"
        )

        candidates, genre_changes, checked_count, stopped = self._collect_genre_update_candidates(
            items,
            genres_map,
            item_label,
            progress_callback,
        )
        if stopped:
            self.logger.info(f"{item_label}流派更新已停止，已扫描 {checked_count}/{total_items} 部，已更新 0 部")
            return updated_items

        self.logger.info(f"{item_label}共 {total_items} 部，预扫描后需要更新 {len(candidates)} 部")
        self._log_genre_change_summary(item_label, genre_changes)

        if not candidates:
            self._report_progress(
                progress_callback,
                1,
                1,
                f"{item_label}流派预扫描完成，没有需要更新的条目",
                percent=100,
            )
            self.logger.info(f"没有需要更新的{item_label}流派信息。")
            return updated_items

        stopped = False
        last_update_heartbeat = 0
        unchanged_detail_count = 0
        self._report_progress(
            progress_callback,
            0,
            len(candidates),
            f"开始更新{item_label}流派，候选 {len(candidates)} 部",
            percent=50,
        )
        for candidate_index, each_item in enumerate(candidates, start=1):
            if self.stop_flag.is_set():
                stopped = True
                break

            item_id = each_item['Id']
            item_name = each_item.get('Name', item_id)
            now = time.monotonic()
            should_log_heartbeat = (
                candidate_index <= 50
                or candidate_index % 100 == 0
                or now - last_update_heartbeat >= 30
            )
            if should_log_heartbeat:
                heartbeat_message = (
                    f"正在更新{item_label}流派: {candidate_index}/{len(candidates)}，"
                    f"已成功 {update_count} 部，当前: {item_name}"
                )
                self._report_progress(
                    progress_callback,
                    candidate_index - 1,
                    len(candidates),
                    heartbeat_message,
                    percent=self._progress_percent(candidate_index - 1, len(candidates), 50, 50),
                )
                last_update_heartbeat = now

            item = self.get_item_info(item_id)
            if not item:
                self.logger.error(f"{item_label}ID '{item_id}' 的信息读取失败.(Total updates: {update_count})")
                continue

            original_genres = item.get('Genres', [])
            translated_genres = self._translate_genres(original_genres, genres_map)
            if original_genres == translated_genres:
                unchanged_detail_count += 1
                if unchanged_detail_count in {50, 100, 200} or unchanged_detail_count % 500 == 0:
                    self.logger.info(
                        f"{item_label}候选详情已无需更新 {unchanged_detail_count} 部，"
                        f"已成功 {update_count} 部"
                    )
                if update_count == 0 and unchanged_detail_count >= 200:
                    self.logger.warning(
                        f"{item_label}候选快照疑似已过期：连续 {unchanged_detail_count} 个候选详情均无需更新。"
                    )
                    if rescan_attempts < 1 and not self.stop_flag.is_set():
                        self.logger.info(f"重新扫描{item_label}流派候选后继续")
                        return self._translate_items_genres_and_update(
                            item_label,
                            include_item_types,
                            genres_map,
                            progress_callback=progress_callback,
                            rescan_attempts=rescan_attempts + 1,
                        )
                    self.logger.warning(f"{item_label}流派更新停止：重扫后仍未发现可提交的更新")
                    break
                continue
            unchanged_detail_count = 0

            if self.stop_flag.is_set():
                stopped = True
                break

            item['Genres'] = translated_genres
            item['GenreItems'] = self._build_genre_items(translated_genres, genre_item_ids)

            update_response = self._post_item_update(item_id, item)

            if update_response.status_code in [200, 204]:
                update_count += 1
                updated_items.append(item)
                if self._should_log_item_update(update_count):
                    self.logger.info(f"{item_label}: {item['Name']} 流派信息已更新。(Total updates: {update_count})")
            else:
                self.logger.error(
                    f"{item_label} '{item.get('Name', item_id)}'({item_id}) 更新失败，"
                    f"状态码: {update_response.status_code}(Total updates: {update_count})"
                )
                self.logger.error(update_response.text)

            if self._should_report_progress(candidate_index, len(candidates)):
                self._report_progress(
                    progress_callback,
                    candidate_index,
                    len(candidates),
                    f"更新{item_label}流派进度: {candidate_index}/{len(candidates)}，已成功 {update_count} 部",
                    percent=self._progress_percent(candidate_index, len(candidates), 50, 50),
                )

        if stopped:
            self.logger.info(
                f"{item_label}流派更新已停止，候选 {len(candidates)} 部，已处理 {candidate_index - 1} 部，"
                f"已更新 {update_count} 部"
            )
        else:
            self.logger.info(f"{item_label}共 {total_items} 部，实际更新 {update_count} 部")

        if update_count == 0:
            self.logger.info(f"没有需要更新的{item_label}流派信息。")

        return updated_items

    def check_duplicates(self, target_folder, callback):
        def run_check():
            total_items = 0
            duplicate_items = 0
            start_time = time.time()
            new_items_info = []
            duplicate_items_info = []
            self.logger.info(f"连接emby服务器 : {self.server_url} ......")
            all_movies = self.get_all_media()
            if not all_movies:
                self.logger.info("Emby库里没有影剧")
                return
            self.logger.info(f"已连接服务器数据库，数据库共 {len(all_movies)} 部影剧")

            self.logger.info("开始查询...")
            # 遍历指定路径下的所有子目录和文件
            for root, dirs, files in os.walk(target_folder):
                for file in files:
                    if file.endswith('.nfo'):
                        nfo_path = os.path.join(root, file)
                        query_emdb_value, is_demaged_nfo = self.extract_tmdbid_from_nfo(nfo_path)
                        if query_emdb_value is not None:
                            total_items += 1

                            if is_demaged_nfo:
                                nfo_log = "NFO文件破损"
                            else:
                                nfo_log = "NFO校验通过"

                            if not self.query_movies_by_tmdbid(all_movies, query_emdb_value):
                                self.logger.info(f"{nfo_log}, 发现新影剧 : {nfo_path} ")
                                self.logger.info(f"{nfo_log}, 新影剧路径 : {os.path.dirname(nfo_path)}")
                                self.logger.info(f"{nfo_log}, 新影剧名 :   {os.path.basename(nfo_path)}")
                                new_items_info.append(f"{nfo_log}, 新影剧  : {nfo_path}")
                            else:
                                duplicate_items += 1
                                self.logger.info(f"{nfo_log}, 发现重复影剧:  {nfo_path}")
                                self.logger.info(f"{nfo_log}, 重复影剧路径 : {os.path.dirname(nfo_path)}")
                                self.logger.info(f"{nfo_log}, 重复影剧名 :   {os.path.basename(nfo_path)}")
                                duplicate_items_info.append(f"{nfo_log}, 重复影剧 : {nfo_path}")
                                if self.delete_nfo:
                                    os.remove(nfo_path)
                                    self.logger.info(f"{nfo_log}, 删除重复影剧nfo : {nfo_path}")
                                if self.delete_nfo_folder:
                                    folder_path = os.path.dirname(nfo_path)
                                    shutil.rmtree(folder_path)
                                    self.logger.info(f"{nfo_log}, 删除重复影剧所在的文件夹 : {folder_path}")

            end_time = time.time()
            total_time = end_time - start_time
            message = (
                "\n"
                "====================完成影剧查重==================\n"
                "====================查重结果汇总==================\n"
                "====================新影剧==================\n" + "\n".join(new_items_info) + "\n"
                "====================重复影剧==================\n" + "\n".join(duplicate_items_info) + "\n"
                f"NFO文件处理  : {'已删除' if self.delete_nfo else '保留'}重复影剧对应的nfo文件\n"
                f"NFO文件夹处理: {'已删除' if self.delete_nfo_folder else '保留'}重复影剧对应的nfo文件所在的目录\n"
                f"====================影剧查重结束==================\n"
                f"更新汇总数据:总耗时 {total_time:.2f} 秒, 共查询影剧数: {total_items}个，发现重复影剧: {duplicate_items}\n"
            )
            if callback:
                callback(message)

        return self._start_background_task(run_check, "影剧查重")

    # 获取所有影剧的信息
    def get_all_media(self):
        return self._get_items("Movie,Series", "ProviderIds,Path")

    # 获取所有影剧的信息
    def get_movie_media(self):
        return self._get_items("Movie", "ProviderIds,Path")

    # 查询TMDb ID
    def query_movies_by_tmdbid(self, movies, tmdb_value):
        for movie in movies:
            tmdb_id = movie.get("ProviderIds", {}).get("Tmdb", "")
            if tmdb_value == tmdb_id:
                # self.logger.info(f"影剧 '{movie['Name']}' 存在于 Emby 库中，TMDB 值: {tmdb_value}")
                return True
        # self.logger.info(f"没有找到与 TMDB 值 {tmdb_value} 相同的影剧。")
        return False

    def extract_tmdbid_from_nfo(self, nfo_path):
        try:
            # 解析 .nfo 文件
            tree = ET.parse(nfo_path)
            root = tree.getroot()

            # 查找名为 movie 的根元素下的一级子元素 tmdbid
            tmdbid_element = root.find('tmdbid')

            if tmdbid_element is not None:
                query_tmdbid = tmdbid_element.text.strip()
                # self.logger.info(f"在 '{nfo_path}' 中找到 tmdbid: {query_tmdbid}")
                return query_tmdbid, False
            else:
                return None, False

        except ET.ParseError as e:
            self.logger.error(f"解析错误: 无法解析文件 '{nfo_path}'，错误信息: {e}")
            # 异常的原因可能是xml不完整,再次尝试强制解析
            query_tmdbid = self.force_extract_tmdbid_from_file(nfo_path)  # 修改这里，添加 self
            if query_tmdbid is not None:
                return query_tmdbid, True
            else:
                return None, False  # 修改这里，返回两个值
        except Exception as e:
            self.logger.error(f"发生错误: 在处理文件 '{nfo_path}' 时出错，错误信息: {e}")
            return None, False  # 确保总是返回两个值

    def force_extract_tmdbid_from_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            match = re.search(r'^  <tmdbid>(\d+)<', line)  # <tmdbid>前面要有两个空格
            if match:
                self.logger.info(f"{os.path.basename(file_path)} Found tmdbid: {match.group(1)}")
                return match.group(1)  # or do whatever you need with the extracted value

        self.logger.error("No matching tmdbid found.")
        return None

    def _get_provider_id(self, movie, provider_key):
        provider_ids = movie.get("ProviderIds", {}) or {}
        provider_key = str(provider_key or "").lower()
        for key, value in provider_ids.items():
            if str(key).lower() == provider_key and value:
                provider_value = str(value).strip()
                if provider_key == "num":
                    return provider_value.upper()
                return provider_value
        return ""

    def group_movies_by_provider_id(self, movies, provider_key):
        grouped_movies = {}
        for movie in movies:
            provider_value = self._get_provider_id(movie, provider_key)
            if provider_value:
                if provider_value not in grouped_movies:
                    grouped_movies[provider_value] = []
                grouped_movies[provider_value].append(movie)
        return grouped_movies

    def _count_mergeable_groups(self, grouped_movies):
        return sum(1 for movies in grouped_movies.values() if len(movies) > 1)

    @staticmethod
    def _progress_percent(current, total, start_percent=0, span_percent=100):
        if not total:
            return start_percent
        return start_percent + (float(current) / float(total)) * span_percent

    @staticmethod
    def _scale_progress_callback(callback, start_percent, span_percent):
        if callback is None:
            return None

        def scaled_callback(payload):
            if not isinstance(payload, dict):
                callback(payload)
                return

            scaled_payload = dict(payload)
            percent = payload.get('percent')
            current = payload.get('current')
            total = payload.get('total')
            if isinstance(percent, (int, float)):
                scaled_payload['percent'] = MediaServerClient._progress_percent(
                    percent,
                    100,
                    start_percent,
                    span_percent,
                )
            elif isinstance(current, (int, float)) and isinstance(total, (int, float)) and total > 0:
                scaled_payload['percent'] = MediaServerClient._progress_percent(
                    current,
                    total,
                    start_percent,
                    span_percent,
                )
            callback(scaled_payload)

        return scaled_callback

    @staticmethod
    def _report_progress(callback, current, total, message, percent=None):
        if callback is None:
            return
        payload = {'message': message}
        if percent is not None:
            payload['percent'] = percent
        if total is not None and total > 0:
            payload['current'] = current
            payload['total'] = total
        else:
            payload['current'] = current
            payload['total'] = total
        callback(payload)

    # 按照TMDb ID分组
    def group_movies_by_tmdbid(self, movies):
        return self.group_movies_by_provider_id(movies, "tmdb")

    def emby_get_user_id(self):
        params = {"api_key": self.api_key}
        if self.server_type == 'emby':
            response = requests.get(
                f'{self.server_url}/Users/Public', headers=self._auth_headers(), params=params, timeout=30
            )
        else:
            response = self._request('get', '/Users', params=params)
        if response.status_code == 200:
            users = response.json()
            for user in users:
                # self.logger.info(f"User Name: {user['Name']}, User ID: {user['Id']}")
                if user['Name'] == self.username:
                    self.logger.info(f"User Name: {self.username} if found, User ID is : {user['Id']}")
                    return user['Id']
        else:
            self.logger.error(f"Request failed, status code: {response.status_code}")
            self.logger.error(response.text)

    # 合并同一个TMDb ID下的不同版本
    def merge_movie_versions(
        self,
        grouped_movies,
        identity_label="TMDB",
        progress_callback=None,
        progress_base=0,
        progress_total=None,
    ):
        if self.server_type == 'jellyfin':
            return self.jellyfin_merge_movie_versions(
                grouped_movies,
                identity_label=identity_label,
                progress_callback=progress_callback,
                progress_base=progress_base,
                progress_total=progress_total,
            )
        return self.emby_merge_movie_versions(
            grouped_movies,
            identity_label=identity_label,
            progress_callback=progress_callback,
            progress_base=progress_base,
            progress_total=progress_total,
        )

    def emby_merge_movie_versions(
        self,
        grouped_movies,
        identity_label="TMDB",
        progress_callback=None,
        progress_base=0,
        progress_total=None,
    ):
        return self._merge_movie_versions(
            grouped_movies,
            ids_key="Ids",
            server_label="Emby",
            identity_label=identity_label,
            progress_callback=progress_callback,
            progress_base=progress_base,
            progress_total=progress_total,
        )

    def jellyfin_merge_movie_versions(
        self,
        grouped_movies,
        identity_label="TMDB",
        progress_callback=None,
        progress_base=0,
        progress_total=None,
    ):
        return self._merge_movie_versions(
            grouped_movies,
            ids_key="ids",
            server_label="Jellyfin",
            identity_label=identity_label,
            progress_callback=progress_callback,
            progress_base=progress_base,
            progress_total=progress_total,
        )

    def _merge_movie_versions(
        self,
        grouped_movies,
        ids_key,
        server_label,
        identity_label="TMDB",
        progress_callback=None,
        progress_base=0,
        progress_total=None,
    ):
        merged_movies = []
        if progress_total is None:
            progress_total = self._count_mergeable_groups(grouped_movies)

        processed = 0
        for identity_value, movies in grouped_movies.items():
            if self.stop_flag.is_set():
                self.logger.info("合并版本操作已停止")
                break

            if len(movies) > 1:
                name = movies[0]["Name"]
                self.logger.info("")
                self.logger.info(f"发现相同 {identity_label} 影片：{identity_value}")
                self.logger.info(f"已发现相同版本的影片::: {name}")

                item_ids = ",".join(movie["Id"] for movie in movies)
                payload = {
                    ids_key: item_ids,
                    "api_key": self.api_key,
                }
                response = self._request('post', '/Videos/MergeVersions', params=payload)
                if response.status_code == 204:
                    self.logger.info(f"{server_label} 合并版本成功:::         {name}")
                else:
                    self.logger.error(f"{server_label} 合并版本失败:::         {name}")
                    self.logger.error(response.text)
                merged_movies.append(movies[0])  # 暂时保留第一部影片为合并结果
                processed += 1
                if progress_total > 0:
                    self._report_progress(
                        progress_callback,
                        progress_base + processed,
                        progress_base + progress_total,
                        f"{identity_label} 已合并: {processed}/{progress_total}（{server_label}）",
                    )
        return merged_movies

    def merge_versions(self, callback):
        self.validate_server_type()
        if self.server_type == 'jellyfin':
            return self.jellyfin_merge_versions(callback)
        return self.emby_merge_versions(callback)

    def emby_merge_versions(self, callback):
        return self._merge_versions(callback, "Emby")

    def jellyfin_merge_versions(self, callback):
        return self._merge_versions(callback, "Jellyfin")

    def _merge_versions(self, callback, server_label):
        def run_merge_versions_check():
            self.logger.info(f"开始使用 {server_label} 流程合并版本")
            all_movies = self.get_movie_media()  # 只需要合并电影，TV Emby会自动合并
            if not all_movies:
                self.logger.info(f"{server_label} 库里没有影片")
                return
            self.logger.info(f"已连接服务器数据库，数据库共 {len(all_movies)} 部影片")

            self.logger.info("开始按 TMDB 合并标准影片版本")
            tmdb_grouped_movies = self.group_movies_by_tmdbid(all_movies)
            tmdb_mergeable_count = self._count_mergeable_groups(tmdb_grouped_movies)
            self.logger.info(f"已分组影片，共 {len(tmdb_grouped_movies)} 个TMDb ID")
            self.logger.info(f"TMDB 可合并分组：{tmdb_mergeable_count} 组")
            merged_movies = self.merge_movie_versions(
                tmdb_grouped_movies,
                identity_label="TMDB",
                progress_callback=callback,
                progress_base=0,
                progress_total=tmdb_mergeable_count,
            )
            if self.stop_flag.is_set():
                self.logger.info("已停止合并版本")
                if callback:
                    callback(merged_movies)
                return merged_movies
            self.logger.info(f"TMDB 已合并版本，共 {len(merged_movies)} 部影片")

            self.logger.info("开始检查 AV 番号版本")
            av_grouped_movies = self.group_movies_by_provider_id(all_movies, "num")
            if not av_grouped_movies:
                self.logger.info("未发现 AV 番号数据，跳过 AV 合并")
            else:
                av_mergeable_count = self._count_mergeable_groups(av_grouped_movies)
                self.logger.info(f"已分组影片，共 {len(av_grouped_movies)} 个 AV 番号")
                self.logger.info(f"AV 番号可合并分组：{av_mergeable_count} 组")
                av_merged_movies = self.merge_movie_versions(
                    av_grouped_movies,
                    identity_label="AV 番号",
                    progress_callback=callback,
                    progress_base=tmdb_mergeable_count,
                    progress_total=av_mergeable_count,
                )
                self.logger.info(f"AV 番号已合并版本，共 {len(av_merged_movies)} 部影片")
                merged_movies.extend(av_merged_movies)

            self._report_progress(callback, 1, 1, "合并版本处理完成")
            if callback:
                callback(merged_movies)

            return merged_movies

        return self._start_background_task(run_merge_versions_check, "合并版本")

    def get_item_info(self, movie_id):
        if self.server_type == 'jellyfin':
            return self.jellyfin_get_item_info(movie_id)
        return self.emby_get_item_info(movie_id)

    def emby_get_item_info(self, movie_id):
        headers = {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json'}

        self.user_id = self.user_id or self.emby_get_user_id()
        if not self.user_id:
            self.logger.error("Failed to retrieve user ID.")
            return None

        detail_item_endpoint = self._api_url(
            f"/Users/{self.user_id}/Items/{urllib.parse.quote(str(movie_id), safe='')}", ''
        )
        detail_item_response = requests.get(detail_item_endpoint, headers=headers, timeout=(5, 30))

        if detail_item_response.status_code == 200:
            return detail_item_response.json()
        else:
            self.logger.error(
                f"Failed to retrieve complete movie information, status code: {detail_item_response.status_code}"
            )
            self.logger.error(f"Response content: {detail_item_response.text}")
            return None

    def jellyfin_get_item_info(self, movie_id):
        self.user_id = self.user_id or self.emby_get_user_id()
        if not self.user_id:
            self.logger.error("Failed to retrieve user ID.")
            return None

        path = (
            f"/Users/{urllib.parse.quote(str(self.user_id), safe='')}/"
            f"Items/{urllib.parse.quote(str(movie_id), safe='')}"
        )
        try:
            response = self._request_with_retries(
                'get',
                path,
                params={"api_key": self.api_key},
                timeout=(5, 30),
                retries=1,
                retry_delay=1,
                retry_status_codes={408, 429, 500, 502, 503, 504},
                retry_label=f"读取条目详情 {movie_id}",
            )
        except requests.exceptions.RequestException as err:
            self.logger.error(f"Failed to retrieve complete item information: {err}")
            return None

        if response.status_code == 200:
            return response.json()

        self.logger.error(f"Failed to retrieve complete item information, status code: {response.status_code}")
        self.logger.error(f"Response content: {response.text}")
        return None

    def emby_tv_translate_genres_and_update_whole_item(
        self,
        progress_callback=None,
        progress_base=0,
        progress_total=None,
    ):
        return self._translate_items_genres_and_update(
            "剧集",
            'Series',
            TV_GENRE_TRANSLATIONS,
            progress_callback=progress_callback,
        )

    def emby_movie_translate_genres_and_update_whole_item(
        self,
        progress_callback=None,
        progress_base=0,
        progress_total=None,
    ):
        return self._translate_items_genres_and_update(
            "影片",
            'Movie',
            MOVIE_GENRE_TRANSLATIONS,
            progress_callback=progress_callback,
        )

    # 列出库中所有的影片流派
    def emby_get_all_movie_genres(self):
        # Set query parameters
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Movie',
            'Fields': 'Genres',  # Request to include the Genres field
            'Limit': '1000000',  # Adjust the limit according to your needs
        }

        # Send request to get the list of movies
        response = self._request('get', '/Items', params=params)

        # Check if the request was successful
        if response.status_code == 200:
            movies = response.json()['Items']
            # Use a set to remove duplicate genres
            all_genres = set()

            for movie in movies:
                movie_name = movie['Name']
                genres = movie.get('Genres', [])
                if genres:
                    # Add genres to the set
                    all_genres.update(genres)
                else:
                    self.logger.info(f"Movie '{movie_name}' has no specified genres.")

            # debug_function all unique genres
            self.logger.info("All unique genres:")
            self.logger.info(', '.join(sorted(all_genres)))
        else:
            self.logger.info(f"Request failed, status code: {response.status_code}")
            self.logger.info(response.text)

    # 列出库中所有的电视剧集流派
    def emby_get_all_tv_genres(self):
        # Set query parameters
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Series',
            'Fields': 'Genres',  # Request to include the Genres field
            'Limit': '1000000',  # Adjust the limit according to your needs 后续解析"TotalRecordCount":1812字段
        }

        # Send request to get the list of movies
        response = self._request('get', '/Items', params=params)

        # Check if the request was successful
        if response.status_code == 200:
            tvs = response.json()['Items']
            # Use a set to remove duplicate genres
            all_genres = set()

            for tv in tvs:
                tv_name = tv['Name']
                genres = tv.get('Genres', [])
                if genres:
                    # Add genres to the set
                    all_genres.update(genres)
                    self.logger.info(f"tv: {tv_name}")
                    self.logger.info(f"tv: {', '.join(genres)}")
                    self.logger.info('-' * 30)
                else:
                    self.logger.info(f"tv '{tv_name}' has no specified genres.")

            # self.logger.info all unique genres
            self.logger.info("All unique genres:")
            self.logger.info(', '.join(sorted(all_genres)))
        else:
            self.logger.error(f"Request failed, status code: {response.status_code}")
            self.logger.error(response.text)

    def update_genres(self, callback=None):
        self.validate_server_type()

        def run_update_genres_check():
            self.logger.info(f"开始使用 {self._server_label()} 流程更新流派")
            self.logger.info("开始更新影片流派信息...")
            movie_callback = self._scale_progress_callback(callback, 0, 50)
            series_callback = self._scale_progress_callback(callback, 50, 50)

            updated_movies = self.emby_movie_translate_genres_and_update_whole_item(progress_callback=movie_callback)
            stopped = self.stop_flag.is_set()
            if stopped:
                self.logger.info("已停止更新影片流派信息")
                updated_series = []
            else:
                self.logger.info("完成更新影片流派信息")
                self.logger.info("开始更新剧集流派信息...")
                updated_series = self.emby_tv_translate_genres_and_update_whole_item(progress_callback=series_callback)
                stopped = self.stop_flag.is_set()
                if stopped:
                    self.logger.info("已停止更新剧集流派信息")
                else:
                    self.logger.info("完成更新剧集流派信息")

            # 汇总信息
            movies_message = self._format_updated_items_message("影片", updated_movies)
            series_message = self._format_updated_items_message("剧集", updated_series)

            title = "已停止更新流派" if stopped else "完成更新所有影剧流派"
            message = (
                f"\n"
                f"----------------------------------------\n"
                f"{title}\n"
                f"{movies_message}"
                f"{series_message}"
                f"----------------------------------------\n"
            )

            self.logger.info(message)
            self._report_progress(callback, 1, 1, title, percent=100)

            return message

        return self._start_background_task(run_update_genres_check, "更新流派")

    def clear_files_by_type(self, folder_path, file_type='VIDEO', callback=None):
        def run_clear_files_by_type_check():
            video_files = []
            for root, _, files in os.walk(folder_path):
                if self.stop_flag.is_set():
                    self.logger.info("删除视频文件操作已停止")
                    break
                for file in files:
                    if self.stop_flag.is_set():
                        self.logger.info("删除视频文件操作已停止")
                        break

                    if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                        video_files.append(os.path.join(root, file))

            num = 0
            total = len(video_files)
            if callback:
                self._report_progress(callback, 0, total, f"准备删除视频文件，共 {total} 个")

            for file_path in video_files:
                if self.stop_flag.is_set():
                    self.logger.info("删除视频文件操作已停止")
                    break

                file = os.path.basename(file_path)
                try:
                    os.remove(file_path)
                    num += 1
                    self.logger.info(f"删除文件:: {file} 共删除文件数目: {num}")
                    if callback:
                        self._report_progress(callback, num, total, f"删除文件:: {file}")
                except Exception as e:
                    self.logger.error(f"发生错误: 在删除文件 '{file_path}' 时出错，错误信息: {e}")

            message = (
                f"\n"
                f"----------------{'已停止文件删除' if self.stop_flag.is_set() else '完成文件删除'}----------------------------\n"
                f"----------------共删除文件数目:  {num}------------------\n"
            )

            self.logger.info(message)
            if callback:
                callback(message)

            return

        return self._start_background_task(run_clear_files_by_type_check, "删除视频文件")

    def check_metadata_integrity(self, folder_path, callback=None):
        def run_check_metadata_integrity_check():
            video_check_result = self.check_video_files(
                folder_path,
                progress_callback=(
                    lambda payload: callback(
                        {'stage': '视频检查', **payload, 'message': f"[视频检查] {payload.get('message', payload)}"}
                    )
                    if callback
                    else None
                ),
            )
            if self.stop_flag.is_set():
                self.logger.info("检查刮削数据完整性操作已停止")
                if callback:
                    callback("检查刮削数据完整性操作已停止")
                return

            nfo_check_result = self.check_nfo_files(
                folder_path,
                progress_callback=(
                    lambda payload: callback(
                        {'stage': 'NFO检查', **payload, 'message': f"[NFO检查] {payload.get('message', payload)}"}
                    )
                    if callback
                    else None
                ),
            )

            for video in video_check_result['no_nfo_videos']:
                self.logger.info(f"没有找到nfo文件的视频文件: {video}")
            for nfo in nfo_check_result['no_video_nfo']:
                self.logger.info(f"没有找到视频文件的nfo文件: {nfo}")

            message = (
                f"\n"
                f"-------------汇总信息------------------------\n"
                f"总共找到 {video_check_result['total_videos']} 个视频文件。\n"
                f"其中有 {len(video_check_result['no_nfo_videos'])} 个视频文件没有找到对应的.nfo文件: \n"
                f"总共找到 {nfo_check_result['total_nfo']} 个nfo文件。\n"
                f"其中有 {len(nfo_check_result['no_video_nfo'])} 个nfo文件没有找到对应的视频文件: \n"
                f"-------------检查结束------------------------\n"
            )

            self.logger.info(message)
            if callback:
                callback(message)

            return

        return self._start_background_task(run_check_metadata_integrity_check, "检查刮削数据完整性")

    def find_related_videos(self, nfo_file_path):
        """
        对于给定的 .nfo 文件，查找相同文件夹下的同名视频文件。

        :param nfo_file_path: .nfo 文件的路径
        :return: 包含同名视频文件路径的列表
        """
        # 获取 .nfo 文件所在的目录和不带后缀的文件名
        nfo_dir = os.path.dirname(nfo_file_path)
        base_name = os.path.splitext(os.path.basename(nfo_file_path))[0]

        # 查找同名但不同后缀的视频文件
        for ext in VIDEO_EXTENSIONS:
            video_path = os.path.join(nfo_dir, base_name + ext)
            if os.path.isfile(video_path) or os.path.islink(video_path):
                return video_path

        return None

    def check_nfo_files(self, folder_path, progress_callback=None):
        """
        遍历给定文件夹中的所有 .nfo 文件，并检查对应的同名视频文件。

        :param folder_path: 要检查的文件夹路径
        :return: 汇总查询结果的字典
        """
        # 初始化结果汇总
        results = {'total_nfo': 0, 'no_video_nfo': [], 'found_video_nfo': []}

        nfo_files = [path for path in Path(folder_path).rglob('*.nfo')]
        filtered_nfo_files = [
            path
            for path in nfo_files
            if os.path.basename(str(path)) not in ('tvshow.nfo', 'season.nfo') and os.path.isfile(str(path))
        ]

        if progress_callback:
            self._report_progress(
                progress_callback,
                0,
                len(filtered_nfo_files),
                f"开始扫描 NFO 文件：共 {len(filtered_nfo_files)} 个",
            )

        # 使用 glob 递归查找所有的 .nfo 文件
        for nfo_path in filtered_nfo_files:
            if self.stop_flag.is_set():
                self.logger.info("NFO 文件检查已停止")
                break

            nfo_str_path = str(nfo_path)
            results['total_nfo'] += 1

            video_path = self.find_related_videos(nfo_str_path)

            if video_path:
                results['found_video_nfo'].append(nfo_str_path)
            else:
                results['no_video_nfo'].append(nfo_str_path)
            if progress_callback:
                self._report_progress(
                    progress_callback,
                    results['total_nfo'],
                    len(filtered_nfo_files),
                    f"扫描 NFO: {results['total_nfo']}/{len(filtered_nfo_files)}",
                )

        return results

    def check_video_files(self, folder_path, progress_callback=None):
        # 初始化结果汇总
        results = {'total_videos': 0, 'no_nfo_videos': [], 'found_nfo_videos': []}

        all_video_files = []
        for root, _, files in os.walk(folder_path):
            if self.stop_flag.is_set():
                self.logger.info("视频文件检查已停止")
                break

            video_files = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS]
            all_video_files.extend([os.path.join(root, video_file) for video_file in video_files if os.path.isfile(os.path.join(root, video_file))])

        if progress_callback:
            self._report_progress(
                progress_callback,
                0,
                len(all_video_files),
                f"开始扫描视频文件：共 {len(all_video_files)} 个",
            )

        # 遍历指定文件夹及其子文件夹
        for video_full_path in all_video_files:
            if self.stop_flag.is_set():
                self.logger.info("视频文件检查已停止")
                break

            results['total_videos'] += 1
            base_name, _ = os.path.splitext(os.path.basename(video_full_path))
            nfo_file = base_name + '.nfo'
            nfo_full_path = os.path.join(os.path.dirname(video_full_path), nfo_file)

            if not os.path.exists(nfo_full_path):
                results['no_nfo_videos'].append(video_full_path)
            else:
                results['found_nfo_videos'].append(video_full_path)

            if progress_callback:
                self._report_progress(
                    progress_callback,
                    results['total_videos'],
                    len(all_video_files),
                    f"扫描视频: {results['total_videos']}/{len(all_video_files)}",
                )

        return results
