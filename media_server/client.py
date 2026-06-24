import logging
import os
import re
import shutil
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
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

    def _normalize_server_type(self, server_type):
        value = str(server_type or 'emby').strip().lower()
        return 'jellyfin' if value == 'jellyfin' else 'emby'

    def _configured_api_prefix(self):
        return '' if self.server_type == 'jellyfin' else '/emby'

    def _start_background_task(self, target, task_name):
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
                timeout=(10, 120),
                retries=2,
                retry_delay=2,
                retry_status_codes={408, 429, 500, 502, 503, 504},
                retry_label=f"更新条目 {item.get('Name', item_id)}({item_id})",
            )
        except requests.exceptions.RequestException as err:
            return RequestFailureResponse(err)

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
    def merge_movie_versions(self, grouped_movies, identity_label="TMDB"):
        if self.server_type == 'jellyfin':
            return self.jellyfin_merge_movie_versions(grouped_movies, identity_label)
        return self.emby_merge_movie_versions(grouped_movies, identity_label)

    def emby_merge_movie_versions(self, grouped_movies, identity_label="TMDB"):
        return self._merge_movie_versions(
            grouped_movies, ids_key="Ids", server_label="Emby", identity_label=identity_label
        )

    def jellyfin_merge_movie_versions(self, grouped_movies, identity_label="TMDB"):
        return self._merge_movie_versions(
            grouped_movies, ids_key="ids", server_label="Jellyfin", identity_label=identity_label
        )

    def _merge_movie_versions(self, grouped_movies, ids_key, server_label, identity_label="TMDB"):
        merged_movies = []
        for identity_value, movies in grouped_movies.items():
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
            merged_movies = self.merge_movie_versions(tmdb_grouped_movies, "TMDB")
            self.logger.info(f"TMDB 已合并版本，共 {len(merged_movies)} 部影片")

            self.logger.info("开始检查 AV 番号版本")
            av_grouped_movies = self.group_movies_by_provider_id(all_movies, "num")
            if not av_grouped_movies:
                self.logger.info("未发现 AV 番号数据，跳过 AV 合并")
            else:
                av_mergeable_count = self._count_mergeable_groups(av_grouped_movies)
                self.logger.info(f"已分组影片，共 {len(av_grouped_movies)} 个 AV 番号")
                self.logger.info(f"AV 番号可合并分组：{av_mergeable_count} 组")
                av_merged_movies = self.merge_movie_versions(av_grouped_movies, "AV 番号")
                self.logger.info(f"AV 番号已合并版本，共 {len(av_merged_movies)} 部影片")
                merged_movies.extend(av_merged_movies)

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
        detail_item_response = requests.get(detail_item_endpoint, headers=headers)

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
                timeout=(10, 60),
                retries=1,
                retry_delay=2,
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

    def emby_tv_translate_genres_and_update_whole_item(self):
        total_count = 0
        update_count = 0
        updated_series = []

        genres_map = TV_GENRE_TRANSLATIONS

        params = {'Recursive': 'true', 'IncludeItemTypes': 'Series', 'Fields': 'Genres,GenreItems', 'Limit': '1000000'}

        response = self._request('get', '/Items', params=params)

        if response.status_code == 200:
            tvs = response.json().get('Items', [])

            # Use a set to remove duplicate genres
            all_genres = set()
            all_genreitems = set()
            for tv in tvs:
                genres = tv.get('Genres', [])
                genreitems = tv.get('GenreItems', [])
                all_genres.update(genres)
                for genre_item in genreitems:
                    name = genre_item.get('Name')
                    gid = genre_item.get('Id')
                    if name and gid:
                        all_genreitems.add((name, gid))
            self.logger.info(f"剧集所有去重后的Genres: {sorted(all_genres)}")
            self.logger.info(f"剧集所有去重后的GenreItems: {sorted(all_genreitems)}")

            for each_tv in tvs:
                tv_id = each_tv['Id']
                original_genres = each_tv.get('Genres', [])
                translated_genres = [genres_map.get(genre, genre) for genre in original_genres]
                total_count += 1

                if original_genres == translated_genres:
                    continue

                tv = self.get_item_info(tv_id)
                if not tv:
                    self.logger.error(f"剧集ID '{tv_id}' 的信息读取失败.(Total updates: {update_count})")
                    continue

                original_genres = tv.get('Genres', [])
                translated_genres = [genres_map.get(genre, genre) for genre in original_genres]

                if original_genres != translated_genres:
                    # 根据 translated_genres，从 all_genreitems 中查找对应的 id
                    genreitems = []
                    for genre in translated_genres:
                        # 在 all_genreitems 中查找名称为 genre 的元组
                        found = False
                        for name, gid in all_genreitems:
                            if name == genre:
                                genreitems.append({'Name': name, 'Id': gid})
                                found = True
                                break
                        if not found:
                            # 如果没有找到，Id 可以设为 None 或空字符串，EmbyServer会新分配有效ID
                            genreitems.append({'Name': genre, 'Id': ''})

                    tv['Genres'] = translated_genres
                    tv['GenreItems'] = genreitems

                    update_response = self._post_item_update(tv_id, tv)

                    if update_response.status_code in [200, 204]:
                        update_count += 1
                        updated_series.append(tv)
                        self.logger.info(f"剧集: {tv['Name']} 流派信息已更新。(Total updates: {update_count})")
                    else:
                        self.logger.error(
                            f"剧集 '{tv.get('Name', tv_id)}'({tv_id}) 更新失败，"
                            f"状态码: {update_response.status_code}(Total updates: {update_count})"
                        )
                        self.logger.error(update_response.text)
                else:
                    self.logger.info(f"剧集 '{tv['Name']}' 的流派信息没有改变.")
        else:
            self.logger.info(f"请求失败，状态码: {response.status_code}")
            self.logger.info(response.text)

        self.logger.info(f"剧集共 {total_count} 部")
        if update_count == 0:
            self.logger.info("没有需要更新的剧集流派信息。")

        return updated_series

    def emby_movie_translate_genres_and_update_whole_item(self):
        total_count = 0
        update_count = 0
        updated_movies = []
        genres_map = MOVIE_GENRE_TRANSLATIONS

        params = {'Recursive': 'true', 'IncludeItemTypes': 'Movie', 'Fields': 'Genres,GenreItems', 'Limit': '1000000'}

        response = self._request('get', '/Items', params=params)

        if response.status_code == 200:
            movies = response.json().get('Items', [])
            # Use a set to remove duplicate genres
            all_genres = set()
            all_genreitems = set()
            for movie in movies:
                genres = movie.get('Genres', [])
                genreitems = movie.get('GenreItems', [])
                all_genres.update(genres)
                for genre_item in genreitems:
                    name = genre_item.get('Name')
                    gid = genre_item.get('Id')
                    if name and gid:
                        all_genreitems.add((name, gid))
            self.logger.info(f"影片所有去重后的Genres: {sorted(all_genres)}")
            self.logger.info(f"影片所有去重后的GenreItems: {sorted(all_genreitems)}")

            for each_movie in movies:
                movie_id = each_movie['Id']
                original_genres = each_movie.get('Genres', [])
                translated_genres = [genres_map.get(genre, genre) for genre in original_genres]
                total_count += 1
                if original_genres == translated_genres:
                    continue

                movie = self.get_item_info(movie_id)
                if not movie:
                    self.logger.info(f"影片ID '{movie_id}' 的信息读取失败.(Total updates: {update_count})")
                    continue

                original_genres = movie.get('Genres', [])
                translated_genres = [genres_map.get(genre, genre) for genre in original_genres]

                if original_genres != translated_genres:
                    # 根据 translated_genres，从 all_genreitems 中查找对应的 id
                    genreitems = []
                    for genre in translated_genres:
                        # 在 all_genreitems 中查找名称为 genre 的元组
                        found = False
                        for name, gid in all_genreitems:
                            if name == genre:
                                genreitems.append({'Name': name, 'Id': gid})
                                found = True
                                break
                        if not found:
                            # 如果没有找到，Id 可以设为 None 或空字符串，EmbyServer会新分配有效ID
                            genreitems.append({'Name': genre, 'Id': ''})

                    movie['Genres'] = translated_genres
                    movie['GenreItems'] = genreitems

                    update_response = self._post_item_update(movie_id, movie)

                    if update_response.status_code in [200, 204]:
                        update_count += 1
                        updated_movies.append(movie)
                        self.logger.info(f"影片: {movie['Name']} 流派信息已更新。(Total updates: {update_count})")
                    else:
                        self.logger.error(
                            f"影片 '{movie.get('Name', movie_id)}'({movie_id}) 更新失败，"
                            f"状态码: {update_response.status_code}(Total updates: {update_count})"
                        )
                        self.logger.error(update_response.text)
                else:
                    self.logger.info(f"影片 '{movie['Name']}' 的流派信息没有改变.")
        else:
            self.logger.error(f"请求失败，状态码: {response.status_code}")
            self.logger.error(response.text)

        self.logger.info(f"影片共 {total_count} 部")
        if update_count == 0:
            self.logger.info("没有需要更新的影片流派信息。")

        return updated_movies

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
            updated_movies = self.emby_movie_translate_genres_and_update_whole_item()
            self.logger.info("完成更新影片流派信息")
            self.logger.info("开始更新剧集流派信息...")
            updated_series = self.emby_tv_translate_genres_and_update_whole_item()
            self.logger.info("完成更新剧集流派信息")

            # 汇总信息
            if updated_movies:
                updated_movies_info = "\n".join([f"影片: {movie['Name']}" for movie in updated_movies])
                movies_message = f"更新的影片数量: {len(updated_movies)}\n更新的影片:\n{updated_movies_info}\n"
            else:
                movies_message = "没有需要更新的影片流派信息。\n"

            if updated_series:
                updated_series_info = "\n".join([f"剧集: {series['Name']}" for series in updated_series])
                series_message = f"更新的剧集数量: {len(updated_series)}\n更新的剧集:\n{updated_series_info}\n"
            else:
                series_message = "没有需要更新的剧集流派信息。\n"

            message = (
                f"\n"
                f"----------------------------------------\n"
                f"完成更新所有影剧流派\n"
                f"{movies_message}"
                f"{series_message}"
                f"----------------------------------------\n"
            )

            self.logger.info(message)
            if callback:
                callback(message)

            return message

        return self._start_background_task(run_update_genres_check, "更新流派")

    def clear_files_by_type(self, folder_path, file_type='VIDEO', callback=None):
        def run_clear_files_by_type_check():
            num = 0
            # 要删除的文件后缀
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                            num += 1
                            self.logger.info(f"删除文件:: {file} 共删除文件数目: {num}")
                        except Exception as e:
                            self.logger.error(f"发生错误: 在删除文件 '{file_path}' 时出错，错误信息: {e}")

            message = (
                f"\n"
                f"----------------完成文件删除----------------------------\n"
                f"----------------共删除文件数目:  {num}------------------\n"
            )

            self.logger.info(message)
            if callback:
                callback(message)

            return

        return self._start_background_task(run_clear_files_by_type_check, "删除视频文件")

    def check_metadata_integrity(self, folder_path, callback=None):
        def run_check_metadata_integrity_check():
            video_check_result = self.check_video_files(folder_path)
            nfo_check_result = self.check_nfo_files(folder_path)

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

    def check_nfo_files(self, folder_path):
        """
        遍历给定文件夹中的所有 .nfo 文件，并检查对应的同名视频文件。

        :param folder_path: 要检查的文件夹路径
        :return: 汇总查询结果的字典
        """
        # 初始化结果汇总
        results = {'total_nfo': 0, 'no_video_nfo': [], 'found_video_nfo': []}

        # 使用 glob 递归查找所有的 .nfo 文件
        for nfo_path in Path(folder_path).rglob('*.nfo'):
            nfo_str_path = str(nfo_path)
            if os.path.basename(nfo_str_path) in ('tvshow.nfo', 'season.nfo'):
                continue
            if not os.path.isfile(nfo_str_path):
                continue
            results['total_nfo'] += 1

            video_path = self.find_related_videos(nfo_str_path)

            if video_path:
                results['found_video_nfo'].append(nfo_str_path)
            else:
                results['no_video_nfo'].append(nfo_str_path)

        return results

    def check_video_files(self, folder_path):
        # 初始化结果汇总
        results = {'total_videos': 0, 'no_nfo_videos': [], 'found_nfo_videos': []}

        # 遍历指定文件夹及其子文件夹
        for root, _, files in os.walk(folder_path):
            video_files = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS]

            for video_file in video_files:
                video_full_path = os.path.join(root, video_file)
                if not os.path.isfile(video_full_path):
                    continue
                results['total_videos'] += 1
                base_name, _ = os.path.splitext(video_file)
                nfo_file = base_name + '.nfo'

                nfo_full_path = os.path.join(root, nfo_file)

                if not os.path.exists(nfo_full_path):
                    results['no_nfo_videos'].append(video_full_path)
                else:
                    results['found_nfo_videos'].append(video_full_path)

        return results
