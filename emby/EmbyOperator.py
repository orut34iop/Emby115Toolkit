import os
import threading
import time
import queue
import requests
import json
import re
from datetime import datetime
import xml.etree.ElementTree as ET
import sys
from pathlib import Path
import urllib.parse
import shutil
import logging
from utils.logger import setup_logger
from pathlib import Path

# 定义视频文件扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.mpeg', '.mpg', '.iso', '.ts', '.rmvb', '.rm', '.m4v', '.m2ts', '.webm', '.3gp', '.vob', '.divx', '.f4v', '.ogv', '.mxf', '.asf', '.mts'}
class EmbyOperator:
    def __init__(self, server_url=None, api_key=None, user_name=None, delete_nfo=False, delete_nfo_folder=False, logger=None):
        self.server_url = server_url
        self.api_key = api_key
        self.user_name = user_name
        self.user_id = None
        self.delete_nfo = delete_nfo
        self.delete_nfo_folder = delete_nfo_folder
        self.logger = logger or logging.getLogger(__name__)

    def check_duplicate(self, target_folder, callback):
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
    
            self.logger.info(f"开始查询...")
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
                f"\n"
                f"====================完成影剧查重==================\n"
                f"====================查重结果汇总==================\n"
                f"====================新影剧==================\n" + "\n".join(new_items_info) + "\n"
                f"====================重复影剧==================\n" + "\n".join(duplicate_items_info)+ "\n"
                f"NFO文件处理  : {'已删除' if self.delete_nfo else '保留'}重复影剧对应的nfo文件\n"
                f"NFO文件夹处理: {'已删除' if self.delete_nfo_folder else '保留'}重复影剧对应的nfo文件所在的目录\n"
                f"====================影剧查重结束==================\n"
                f"更新汇总数据:总耗时 {total_time:.2f} 秒, 共查询影剧数: {total_items}个，发现重复影剧: {duplicate_items}\n"
            )
            if callback:
                callback(message)

        thread = threading.Thread(target=run_check)
        thread.start()

    # 获取所有影剧的信息
    def get_all_media(self):
        url = f"{self.server_url}/emby/Items"
        params = {
            "api_key": self.api_key,
            "IncludeItemTypes": "Movie,Series",
            "Recursive": True,
            "Fields": "ProviderIds,Path",
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # 检查请求是否成功
            return response.json()["Items"]
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error occurred: {http_err}")  # 输出HTTP错误
        except requests.exceptions.RequestException as err:
            self.logger.error(f"Other error occurred: {err}")  # 输出其他错误
        except ValueError:
            self.logger.error("Error parsing JSON response")
            self.logger.error("Response content:", response.content)  # 输出响应内容以便调试
        return []

    # 获取所有影剧的信息
    def get_movie_media(self):
        url = f"{self.server_url}/emby/Items"
        params = {
            "api_key": self.api_key,
            "IncludeItemTypes": "Movie",
            "Recursive": True,
            "Fields": "ProviderIds,Path",
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # 检查请求是否成功
            return response.json()["Items"]
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error occurred: {http_err}")  # 输出HTTP错误
        except requests.exceptions.RequestException as err:
            self.logger.error(f"Other error occurred: {err}")  # 输出其他错误
        except ValueError:
            self.logger.error("Error parsing JSON response")
            self.logger.error("Response content:", response.content)  # 输出响应内容以便调试
        return []

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
                #self.logger.info(f"在 '{nfo_path}' 中找到 tmdbid: {query_tmdbid}")
                return query_tmdbid, False

        except ET.ParseError as e:
            self.logger.error(f"解析错误: 无法解析文件 '{nfo_path}'，错误信息: {e}")
            #异常的原因可能是xml不完整,再次尝试强制解析
            query_tmdbid = self.force_extract_tmdbid_from_file(nfo_path)  # 修改这里，添加 self
            if query_tmdbid is not None:
                return query_tmdbid , True
            else:
                return None, False  # 修改这里，返回两个值
        except Exception as e:
            self.logger.error(f"发生错误: 在处理文件 '{nfo_path}' 时出错，错误信息: {e}")

        return None, False  # 修改这里，返回两个值

    def force_extract_tmdbid_from_file(self,file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            match = re.search(r'^  <tmdbid>(\d+)<', line) #<tmdbid>前面要有两个空格
            if match:
                self.logger.info(f"{os.path.basename(file_path)} Found tmdbid: {match.group(1)}")
                return match.group(1)  # or do whatever you need with the extracted value

        self.logger.error("No matching tmdbid found.")
        return None

    # 按照TMDb ID分组
    def group_movies_by_tmdbid(self, movies):
        grouped_movies = {}
        for movie in movies:
            tmdb_id = movie.get("ProviderIds", {}).get("Tmdb", "")
            file_path = movie.get("Path", "")
            if tmdb_id:
                if tmdb_id not in grouped_movies:
                    grouped_movies[tmdb_id] = []
                grouped_movies[tmdb_id].append(movie)
        return grouped_movies

    def emby_get_user_id(self):
       # 构造请求URL
        url = f'{self.server_url}/Users/Public?api_key={self.api_key}'

        # 发送GET请求
        response = requests.get(url)

        # 检查请求是否成功
        if response.status_code == 200:
            users = response.json()
            for user in users:
                # self.logger.info(f"User Name: {user['Name']}, User ID: {user['Id']}")
                if user['Name'] == self.user_name:
                    self.logger.info(f"User Name: {self.user_name} if found, User ID is : {user['Id']}")
                    return user['Id']
        else:
            self.logger.error(f"Request failed, status code: {response.status_code}")
            self.logger.error(response.text)

    # 合并同一个TMDb ID下的不同版本
    def merge_movie_versions(self, grouped_movies):
        merged_movies = []
        for tmdb_id, movies in grouped_movies.items():
            if len(movies) > 1:
                name = movies[0]["Name"]
                self.logger.info("")
                self.logger.info(f"已发现相同版本的影片::: {name}")

                item_ids = ",".join(movie["Id"] for movie in movies)
                merge_url = f"{self.server_url}/emby/Videos/MergeVersions"
                payload = {
                    "Ids": item_ids,
                    "X-Emby-Token": self.api_key,
                }
                response = requests.post(merge_url, params=payload)
                if response.status_code == 204:
                    self.logger.info(f"合并版本成功:::         {name}")
                else:
                    self.logger.error(f"合并版本失败:::         {name}")
                merged_movies.append(movies[0])  # 暂时保留第一部影片为合并结果
        return merged_movies

    def merge_versions(self, callback):
        def run_merge_versions_check():
            all_movies = self.get_movie_media() #只需要合并电影，TV Emby会自动合并
            if not all_movies:
                self.logger.info("Emby库里没有影片")
                return
            self.logger.info(f"已连接服务器数据库，数据库共 {len(all_movies)} 部影片")
            grouped_movies = self.group_movies_by_tmdbid(all_movies)
            self.logger.info(f"已分组影片，共 {len(grouped_movies)} 个TMDb ID")
            merged_movies = self.merge_movie_versions(grouped_movies)
            self.logger.info(f"已合并版本，共 {len(merged_movies)} 部影片")

            if callback:
                callback(merged_movies)

            return merged_movies
        
        thread = threading.Thread(target=run_merge_versions_check)
        thread.start()

    def emby_get_item_info(self, movie_id):
        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }

        self.user_id = self.user_id or self.emby_get_user_id()
        if not self.user_id:
            self.logger.error("Failed to retrieve user ID.")
            return None

        detail_item_endpoint = f'{self.server_url}/users/{self.user_id}/items/{movie_id}'
        detail_item_response = requests.get(detail_item_endpoint, headers=headers)

        if detail_item_response.status_code == 200:
            return detail_item_response.json()
        else:
            self.logger.error(f"Failed to retrieve complete movie information, status code: {detail_item_response.status_code}")
            self.logger.error(f"Response content: {detail_item_response.text}")
            return None

    def emby_tv_translate_genres_and_update_whole_item(self):
        total_count = 0
        update_count = 0
        updated_series = []

        genres_map = {
            'Action': '动作',
            'Adventure': '冒险',
            'Animation': '动画',
            'Biography': '传记',
            'Comedy': '喜剧',
            'Crime': '犯罪',
            'Documentary': '纪录片',
            'Drama': '剧情',
            'Family': '家庭',
            'Fantasy': '奇幻',
            'Food': '美食',
            'Game Show': '游戏节目',
            'History': '历史',
            'Holiday': '节日',
            'Horror': '恐怖',
            'Mini-Series': '迷你剧',
            'Music': '音乐',
            'Musical': '音乐剧',
            'Mystery': '悬疑',
            'Reality': '纪实',
            'Reality TV': '真人秀电视',
            'Romance': '浪漫',
            'Sci-Fi & Fantasy': '科幻与奇幻',
            'Science Fiction': '科幻',
            'Short': '短片',
            'Soap': '肥皂剧',
            'Sport': '运动',
            'Suspense': '悬念',
            'Talk Show': '脱口秀',
            'Thriller': '惊悚',
            'Travel': '旅行',
            'War': '战争',
            'Western': '西部',
            'Animal': '动物',
            'War & Politics': '战争与政治'
        }

        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
        items_endpoint = f'{self.server_url}/Items'
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Series',
            'Fields': 'Genres,GenreItems',
            'Limit': '1000000'
        }

        response = requests.get(items_endpoint, headers=headers, params=params)

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

                tv = self.emby_get_item_info(tv_id)
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

                    update_endpoint = f'{self.server_url}/emby/Items/{tv_id}?/api_key={self.api_key}'
                    update_response = requests.post(update_endpoint, headers=headers, data=json.dumps(tv))

                    if update_response.status_code in [200, 204]:
                        update_count += 1
                        updated_series.append(tv)
                        self.logger.info(f"剧集: {tv['Name']} 流派信息已更新。(Total updates: {update_count})")
                    else:
                        self.logger.error(f"更新失败，状态码: {update_response.status_code}(Total updates: {update_count})")
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
        genres_map = {
            'Action': '动作', 
            'Adult': '成人', 
            'Adventure': '冒险', 
            'Animation': '动画', 
            'Anime': '动画',
            'Biography': '传记', 
            'Children': '儿童', 
            'Comedy': '喜剧', 
            'Crime': '犯罪', 
            'Documentary': '纪录片',
            '纪录': '纪录片',            
            'Drama': '剧情', 
            'Eastern': '东方', 
            'Erotic': '情色',
            'Family': '家庭', 
            'Fantasy': '奇幻',
            '魔幻': '奇幻',
            'Film Noir': '黑色影片', 
            'History': '历史', 
            'Holiday': '节日', 
            'Horror': '恐怖', 
            'Indie': '独立影片',
            'Martial Arts': '武术', 
            'Music': '音乐', 
            'Musical': '音乐剧', 
            'Mystery': '悬疑', 
            '悬念': '悬疑',            
            'News': '新闻',
            'Reality TV': '真人秀',
			'Reality': '真人秀',
            'Romance': '爱情', 
            'Science Fiction': '科幻', 
            'Short': '短片', 
            'Sport': '运动',
            'Suspense': '悬念', 
            'TV Movie': '电视电影', 
            'Thriller': '惊悚', 
            'War': '战争', 
            'Western': '西部',
            'superhero': '超级英雄',
            'Animal': '动物',
            'War & Politics': '战争与政治',
			'拷問': '折磨', 
			'ゲロ': '呕吐', 
			'触手': '触手', 
			'ツンデレ': '蛮横娇羞', 
			'童貞': '处男', 
			'ショタ': '正太控', 
			'寝取り・寝取られ': '绿帽/戴绿帽', 
			'くすぐり': '瘙痒', 
			'スポーツ': '运动', 
			'レズキス': '女同接吻', 
			'セクシー': '性感的', 
			'エステ': '美容院', 
			'処女': '处女', 
			'泥酔': '烂醉如泥的', 
			'残虐表現': '残忍画面', 
			'妄想': '妄想', 
			'イタズラ': '恶作剧', 
			'学園もの': '学校作品', 
			'鬼畜': '粗暴', 
			'不倫': '通姦', 
			'姉・妹': '姐妹', 
			'ふたなり': '双性人', 
			'ダンス': '跳舞', 
			'調教・奴隷': '性奴', 
			'逆ナン': '倒追', 
			'痴漢': '性骚扰', 
			'その他': '其他', 
			'脚フェチ': '恋腿癖', 
			'盗撮・のぞき': '偷窥', 
			'淫乱・ハード系': '花痴', 
			'ゲイ・ホモ': '男同性恋', 
			'カップル': '情侣', 
			'巨乳フェチ': '恋乳癖', 
			'近親相姦': '乱伦', 
			'その他フェチ': '其他恋物癖', 
			'アイドル・芸能人': '偶像艺人', 
			'野外・露出': '野外・露出', 
			'ナンパ': '猎艳', 
			'レズ': '女同性恋', 
			'企画': '企画', 
			'10枚組': '10枚组', 
			'SF': '科幻', 
			'女優ベスト・総集編': '最佳女演员/合集', 
			'温泉': '温泉', 
			'M男': '受虐狂', 
			'原作コラボ': '与原创作品合作', 
			'16時間以上作品': '16时间以上作品', 
			'デカチン・巨根': '巨根', 
			'ファン感謝・訪問': '粉丝答谢/探访', 
			'動画': '动画', 
			'巨尻': '大屁股', 
			'ハーレム': '后宫', 
			'日焼け': '日光浴', 
			'早漏': '早泄', 
			'キス・接吻': '接吻', 
			'汗だく': '汗流浃背', 
			'スマホ専用縦動画': '智能手机竖屏动画', 
			'Vシネマ': '影碟首发电影', 
			'Don Cipote\'s choice': '唐·西波特的精选', 
			'アニメ': '动漫', 
			'アクション': '动作', 
			'イメージビデオ（男性）': '男性形象视频', 
			'孕ませ': '怀孕', 
			'ボーイズラブ': '耽美', 
			'ビッチ': '婊子', 
			'特典あり（AVベースボール）': '附赠特典（AV）', 
			'コミック雑誌': '漫画杂志:', 
			'時間停止': '时间停止', 
			'極道・任侠': '黑帮成员', 
			'幼なじみ': '童年朋友', 
			'お姫様': '公主', 
			'アジア女優': '亚洲女演员', 
			'コンパニオン': '伴侣', 
			'インストラクター': '讲师', 
			'義母': '婆婆', 
			'アクション・格闘': '格斗家', 
			'女捜査官': '女检察官', 
			'そっくりさん': '明星脸', 
			'女将・女主人': '女主人、女老板', 
			'モデル': '模特儿', 
			'秘書': '秘书', 
			'美少女': '美少女', 
			'花嫁・若妻': '新娘、年轻妻子', 
			'お姉さん': '姐姐', 
			'格闘家': '格斗家', 
			'バスガイド': '车掌小姐', 
			'未亡人': '寡妇', 
			'お嬢様・令嬢': '千金小姐', 
			'白人女優': '白人', 
			'人妻': '已婚妇女', 
			'女医': '女医生', 
			'職業色々': '各种职业', 
			'キャバ嬢・風俗嬢': '妓女', 
			'レースクィーン': '赛车女郎', 
			'女子大生': '女大学生', 
			'キャンギャル': '展场女孩', 
			'女教師': '女教师', 
			'お母さん': '母亲', 
			'家庭教師': '家教', 
			'看護婦・ナース': '护士', 
			'痴女': '荡妇', 
			'黒人男優': '黑人演员', 
			'ギャル': '女生', 
			'女子アナ': '女主播', 
			'女子校生': '高中女生', 
			'ウェイトレス': '服务生', 
			'魔法少女': '魔法少女', 
			'学生（その他）': '学生（其他）', 
			'アニメキャラクター': '动画人物', 
			'ゲーム実写版': '游戏的真人版', 
			'変身ヒロイン': '超级女英雄', 
			'女戦士': '女战士', 
			'ニーソックス': '及膝袜', 
			'ドール': '娃娃', 
			'くノ一': '女忍者', 
			'女装・男の娘': '女装人妖', 
			'パンチラ': '内衣', 
			'着エロ': '猥褻穿著', 
			'バニーガール': '兔女郎', 
			'ネコミミ・獣系': '猫耳女', 
			'巫女': '女祭司', 
			'ルーズソックス': '泡泡袜', 
			'制服': '制服', 
			'レオタード': '紧身衣', 
			'裸エプロン': '裸体围裙', 
			'ミニスカポリス': '迷你裙警察', 
			'スチュワーデス': '空中小姐', 
			'パンスト': '连裤袜', 
			'ボディコン': '身体意识', 
			'OL': 'OL', 
			'和服・浴衣': '和服・丧服', 
			'体操着・ブルマ': '体育服', 
			'ランジェリー': '内衣', 
			'セーラー服': '水手服', 
			'競泳・スクール水着': '学校泳装', 
			'チャイナドレス': '旗袍', 
			'メイド': '女佣', 
			'ミニスカ': '迷你裙', 
			'学生服': '校服', 
			'水着': '泳装', 
			'めがね': '眼镜', 
			'コスプレ': '角色扮演', 
			'ゴシックロリータ': '哥德萝莉', 
			'超乳': '超乳', 
			'筋肉': '肌肉', 
			'美乳': '乳房', 
			'ミニ系・小柄': '娇小的', 
			'尻フェチ': '屁股', 
			'長身': '高', 
			'ニューハーフ': '变性者', 
			'パイパン': '无毛', 
			'ぽっちゃり': '胖女人', 
			'スレンダー': '苗条', 
			'妊婦': '孕妇', 
			'熟女': '成熟的女人', 
			'ロリ系': '萝莉塔', 
			'貧乳・微乳': '贫乳・微乳', 
			'巨乳': '巨乳', 
			'顔面騎乗': '顏面骑乘', 
			'食糞': '食粪', 
			'足コキ': '足交', 
			'母乳': '母乳', 
			'指マン': '手指插入', 
			'マッサージ': '按摩', 
			'騎乗位': '女上位', 
			'クンニ': '舔阴', 
			'フィスト': '拳交', 
			'イラマチオ': '深喉', 
			'シックスナイン': '69', 
			'淫語': '淫语', 
			'潮吹き': '潮吹', 
			'パイズリ': '乳交', 
			'脱糞': '排便', 
			'飲尿': '饮尿', 
			'フェラ': '口交', 
			'乱交': '滥交', 
			'放尿': '放尿', 
			'手コキ': '打手枪', 
			'ごっくん': '吞精', 
			'アナル': '肛交', 
			'ぶっかけ': '顏射', 
			'オナニー': '自慰', 
			'顔射': '顏射', 
			'中出し': '中出', 
			'アナルセックス': '肛内中出', 
			'即ハメ': '立即口交', 
			'電マ': '女优按摩棒', 
			'ポルチオ': '子宫颈', 
			'催眠・洗脳': '催眠', 
			'ローション': '乳液', 
			'羞恥': '羞耻', 
			'辱め': '凌辱', 
			'拘束': '拘束', 
			'輪姦': '轮姦', 
			'異物挿入': '插入异物', 
			'クスコ': '鸭嘴', 
			'浣腸': '灌肠', 
			'監禁': '监禁', 
			'縛り・緊縛': '紧缚', 
			'強姦': '强姦', 
			'ドラッグ': '药物', 
			'カーセックス': '汽车性爱', 
			'SM': 'SM', 
			'スカトロ': '粪便', 
			'おもちゃ': '玩具', 
			'ローター': '跳蛋', 
			'ボンテージ': '紧缚', 
			'バイブ': '按摩棒', 
			'3P・4P': '多P', 
			'エロス': '性爱', 
			'ディルド': '假阳具', 
			'逆レイプ': '逆强姦', 
			'コラボ作品': '合作作品', 
			'ホラー': '恐怖', 
			'女性向け': '给女性观眾', 
			'How To': '教学', 
			'DMM配信限定': 'DMM专属', 
			'R-15': 'R-15', 
			'R-18': 'R-18', 
			'3D': '3D', 
			'特撮': '特效', 
			'複数話': '故事集', 
			'期間限定セール': '限时降价', 
			'復刻': '复刻版', 
			'ドラマ': '戏剧', 
			'恋愛': '恋爱', 
			'ハイビジョン': '高画质', 
			'主観': '主观视角', 
			'イメージビデオ': '介绍影片', 
			'4時間以上作品': '4小时以上作品', 
			'ギリモザ': '薄马赛克', 
			'クラシック': '经典', 
			'デビュー作品': '首次亮相', 
			'デジモ': '数位马赛克', 
			'投稿': '投稿', 
			'ドキュメンタリー': '纪录片', 
			'洋ピン・海外輸入': '国外进口', 
			'ハメ撮り': '第一人称摄影', 
			'素人': '业餘', 
			'局部アップ': '局部特写', 
			'インディーズ': '独立製作', 
			'独占配信': 'DMM独家', 
			'単体作品': '单体作品', 
			'ベスト・総集編': '合集', 
			'高解像度': '高清', 
			'字幕': '字幕', 
			'パラダイスTV': '天堂TV', 
			'DVDトースター': 'DVD多士炉', 
			'AV OPEN 2014 スーパーヘビー': 'AV OPEN 2014 スーパーヘビー', 
			'AV OPEN 2014 ヘビー級': 'AV OPEN 2014 ヘビー级', 
			'AV OPEN 2014 ミドル級': 'AV OPEN 2014 ミド儿级', 
			'AV OPEN 2015 マニア/フェチ部門': 'AV OPEN 2015 マニア/フェチ部门', 
			'AV OPEN 2015 熟女部門': 'AV OPEN 2015 熟女部门', 
			'AV OPEN 2015 企画部門': 'AV OPEN 2015 企画部门', 
			'AV OPEN 2015 乙女部門': 'AV OPEN 2015 乙女部门', 
			'AV OPEN 2015 素人部門': 'AV OPEN 2015 素人部门', 
			'AV OPEN 2015 SM/ハード部門': 'AV OPEN 2015 SM/ハード部门', 
			'AV OPEN 2015 女優部門': 'AV OPEN 2015 女优部门', 
			'AVOPEN2016人妻・熟女部門': 'AVOPEN2016人妻・熟女部门', 
			'AVOPEN2016企画部門': 'AVOPEN2016企画部门', 
			'AVOPEN2016ハード部門': 'AVOPEN2016ハード部门', 
			'AVOPEN2016マニア・フェチ部門': 'AVOPEN2016マニア・フェチ部门', 
			'AVOPEN2016乙女部門': 'AVOPEN2016乙女部门', 
			'AVOPEN2016女優部門': 'AVOPEN2016女优部门', 
			'AVOPEN2016ドラマ・ドキュメンタリー部門': 'AVOPEN2016ドラマ・ドキュメンタリー部门', 
			'AVOPEN2016素人部門': 'AVOPEN2016素人部门', 
			'AVOPEN2016バラエティ部門': 'AVOPEN2016バラエティ部门', 
			'VR専用': 'VR専用', 
			'ギャグ・コメディ': '堵嘴·喜剧', 
			'ファンタジー': '幻想', 
			'性転換・女体化': '性别转型·女性化', 
			'スマホ推奨縦動画': '為智能手机推荐垂直视频', 
			'セット商品': '设置项目', 
			'ミニ系': '迷你系列', 
			'体験告白': '体验懺悔', 
			'ダーク系': '黑暗系统', 
			'オナサポ': '自慰支持', 
			'アスリート': '运动员', 
			'覆面・マスク': '蒙面', 
			'ハイクオリティVR': '高品质VR', 
			'ヘルス・ソープ': '健康与肥皂店', 
			'ホテル': '酒店', 
			'アクメ・オーガズム': '高潮', 
			'花嫁': '新娘', 
			'デート': '约会', 
			'軟体': '柔软的身体', 
			'娘・養女': '女儿与继女', 
			'スパンキング': '打屁股', 
			'スワッピング・夫婦交換': '交换伴侣与换夫', 
			'部下・同僚': '下属与同事', 
			'旅行': '旅行', 
			'胸チラ': '露乳', 
			'バック': '后入式', 
			'エロス': '情色', 
			'男の潮吹き': '男性喷水', 
			'女上司': '女老板', 
			'セクシー': '性感', 
			'受付嬢': '接待员', 
			'ノーブラ': '不穿胸罩', 
			'白目・失神': '翻白眼与晕厥', 
			'M女': '受虐狂女性', 
			'女王様': '女虐待狂', 
			'ノーパン': '不穿内裤', 
			'セレブ': '名人', 
			'病院・クリニック': '医院与诊所', 
			'面接': '采访', 
			'お風呂': '浴室', 
			'叔母さん': '阿姨', 
			'罵倒': '戏弄', 
			'お爺ちゃん': '爷爷', 
			'逆レイプ': '反向强奸', 
			'ディルド': '女儿', 
			'ヨガ': '瑜伽', 
			'飲み会・合コン': '饮酒派对与集体约会', 
			'部活・マネージャー': '俱乐部活动与经理', 
			'お婆ちゃん': '奶奶', 
			'ビジネススーツ': '职业套装', 
			'チアガール': '啦啦队长', 
			'ママ友': '妈妈朋友', 
			'エマニエル': '艾曼纽', 
			'妄想族': '妄想家庭', 
			'蝋燭': '蜡烛', 
			'鼻フック': '鼻钩', 
			'放置': '被遗弃', 
			'サンプル動画': '样品动画', 
			'サイコ・スリラー': '心理惊悚', 
			'ラブコメ': '浪漫喜剧', 
			'オタク': '宅男宅女', 
			'4K': '4K', 
			'福袋': '福袋', 
			'玩具責め': '玩具虐待', 
			'女優': '女演员', 
			'お掃除フェラ': '清洁口交', 
			'筆おろし': '铅笔羞辱', 
			'美脚': '美腿', 
			'美尻': '美臀', 
			'フェチ': '恋物癖', 
			'羞恥プレイ': '羞耻游戏', 
			'逆ナンパ': '反向搭讪', 
			'着衣': '着装', 
			'誘惑': '诱惑', 
			'チラリズム': '躲猫猫', 
			'写真集': '写真集', 
			'書籍版': '书籍版', 
			'SM拘束': 'SM束缚', 
			'ドキュメント': '纪录片', 
			'グッズ': '周边', 
			'Tシャツ': 'T恤', 
			'失禁': '失禁', 
			'オナホール': '飞机杯', 
			'カップホール': '杯洞', 
			'非貫通': '禁止交流', 
			'ローション付き': '含润滑液', 
			'配信専用': '仅限流媒体播放', 
			'官能小説': '情色小说', 
			'CD': 'CD', 
			'生挿入': '无套插入', 
			'風俗': '卖淫', 
			'外国人': '外国人', 
			'淫語責め': '污言秽语', 
			'アナルファック': '肛交', 
			'脚コキ': '足交', 
			'オイルプレイ': '油浴游戏', 
			'キャバ嬢': '家庭主妇', 
			'調教': '调教', 
			'ローション・オイル': '润肤露/油', 
			'媚薬': '催情剂', 
			'顔面騎乗位': '女上位颜射', 
			'微乳': '小胸', 
			'デカチン': '大阴茎', 
			'3P、4P': '3P、4P', 
			'野外': '户外', 
			'露出': '暴露癖', 
			'レイプ': '强奸', 
			'ベスト、総集編': '最佳合集', 
			'マジックミラー号': '魔镜面包车', 
			'看護師': '护士', 
			'アイドル': '偶像', 
			'妹': '妹妹', 
			'スクール水着': '学校泳装', 
			'デリヘル': '送货服务', 
			'凌辱': '羞辱', 
			'童貞モノ': '处女', 
			'ブルマ': '丑陋', 
			'ホテヘル': '酒店', 
			'縛り': '捆绑', 
			'ロリータ': '洛丽塔', 
			'ミニスカート': '迷你裙', 
			'尻': '屁股', 
			'奴隷': '奴隶', 
			'芸能人': '艺能人', 
			'下着': '内衣', 
			'母親': '母亲', 
			'湯': '浴室', 
			'教師': '教师', 
			'ストッキング': '街头性爱', 
			'電車、バス': '电车、公交车', 
			'健康診断': '健康检查', 
			'野球拳': '野球拳', 
			'浴衣': '浴衣', 
			'爆乳': '巨乳', 
			'ソープ': '泡泡浴', 
			'スワッピング': '换妻俱乐部', 
			'メガネ': '眼镜', 
			'素股': '素股', 
			'ドリンク': '饮料', 
			'フルハイビジョン(FHD)': '满的高清', 
			'三十路': '30多岁', 
			'羞恥・辱め': '羞耻/羞辱', 
			'パンチラモノ': '裙底偷拍', 
			'放尿・失禁': '小便/尿失禁', 
			'五十路': '50多岁', 
			'ショートヘアー': '短发', 
			'着物・浴衣': '和服/浴衣', 
			'清楚': '优雅', 
			'四十路': '40多岁', 
			'VR': 'VR', 
			'オモチャ': '玩具', 
			'エステ・マッサージ': '美容院/按摩', 
			'Gカップ': 'G罩杯', 
			'目隠し': '蒙眼', 
			'ドラッグ・媚薬': '药物/催情剂', 
			'六十路': '60多岁', 
			'淫語モノ': '污言秽语', 
			'口内発射': '口交', 
			'童顔': '娃娃脸', 
			'スチュワーデス・CA': '空姐/CA', 
			'Dカップ': 'D罩杯', 
			'美熟女': '美丽成熟女性', 
			'MGSだけのおまけ映像付き': 'MGS独家花絮', 
			'手マン': '手指爱抚', 
			'パンストモノ': '丝袜', 
			'フェラモノ': '口交', 
			'性教育': '性教育', 
			'HowTo': '教学', 
			'MGS限定特典映像': 'MGS独家花絮', 
			'寝取り･寝取られ': '绿帽/戴绿帽', 
			'Eカップ': 'E罩杯', 
			'Fカップ': 'F罩杯', 
			'ロングヘアー': '长发', 
			'黒髪': '黑发', 
			'ショートヘア': '短发', 
			'金髪': '金发', 
			'茶髪': '棕发', 
			'女子高生': '高中女生', 
			'ハーフ': '日裔混血', 
			'金髪・ブロンド': '金发', 
			'初撮り': '初次拍摄', 
			'介護': '护理', 
			'Hカップ': 'H罩杯', 
			'期間限定販売': '限时特惠', 
			'多人数': '群交', 
			'風俗嬢': '妓女', 
			'PICKUP素人': '搭讪业余', 
			'オイル・ローション': '油/乳液', 
			'8KVR': '8K VR', 
			'プレステージ20周年特別企画': '尊贵20周年特别版', 
			'口内射精': '口交极致体验', 
			'美女': '美丽', 
			'MGSだけの特典映像付': 'MGS独家花絮', 
			'色白': '白皙肌肤', 
			'総集編・ベスト': '合集/精选', 
			'近●相●': '乱伦', 
			'ハイビジョン(HD)': '高清 (HD)', 
			'配信専用素人': '仅限流媒体播放的业余作品', 
			'台湾モデル': '台湾模特', 
			'ショートカット': '短发', 
			'巨乳': '巨乳', 
			'清楚': '干净', 
			'お姉さん': '熟女', 
			'長身': '高挑', 
			'ギャル': '辣妹', 
			'美乳': '美胸', 
			'パイパン': '剃毛', 
			'スレンダー': '苗条', 
			'貧乳・微乳': '小胸', 
			'ミニ系': '迷你', 
			'小柄': '娇小', 
			'くびれ': '沙漏型身材', 
			'ぽっちゃり': '丰满', 
			'黒髪': '黑发', 
			'色白': '白皙肌肤', 
			'金髪': '金发', 
			'茶髪': '棕发', 
			'美脚': '美腿', 
			'ロングヘアー': '长发', 
			'外国人': '外国人', 
			'ショートヘアー': '短发', 
			'お嬢様・令嬢': '年轻女士', 
			'ミディアムヘアー': '中长发', 
			'AI生成作品': 'AI生成作品', 
			'個人撮影': '个人撮影', 
	
			'Torture': '折磨', 
			'Vomit': '呕吐', 
			'Tentacle': '触手', 
			'TSUNDERE': '蛮横娇羞', 
			'Cherry Boy': '处男', 
			'Shotacon': '正太控', 
			'Cheating Wife': '绿帽/戴绿帽', 
			'Tickling': '瘙痒', 
			'Sports': '运动', 
			'Lesbian Kissing': '女同接吻', 
			'Sexy': '性感的', 
			'Massage Parlor': '美容院', 
			'Virgin': '处女', 
			'Drunk Girl': '烂醉如泥的', 
			'Cruelty': '残忍画面', 
			'Daydream': '妄想', 
			'Pranks': '恶作剧', 
			'School': '学校作品', 
			'Rough Sex': '粗暴', 
			'Adultery': '通姦', 
			'Older & Younger Sister': '姐妹', 
			'Hermaphrodite': '双性人', 
			'Dance': '跳舞', 
			'Sex Slave': '性奴', 
			'Reverse Pick Up': '倒追', 
			'Molester': '性骚扰', 
			'Others': '其他', 
			'Foot Fetish': '恋腿癖', 
			'Voyeur': '偷窥', 
			'Nymphomaniac': '花痴', 
			'Gay': '男同性恋', 
			'Couple': '情侣', 
			'Big Tits Lover': '恋乳癖', 
			'Incest': '乱伦', 
			'Other Fetishes': '其他恋物癖', 
			'Idol & Celebrity': '偶像艺人', 
			'Outdoor': '野外・露出', 
			'Picking Up Girls': '猎艳', 
			'Lesbian': '女同性恋', 
			'Variety': '企画', 
			'Ten Clips': '10枚组', 
			'Sci-Fi': '科幻', 
			'Actress Best Compilation': '最佳女演员/合集', 
			'Hot Spring': '温泉', 
			'Masochist Man': '受虐狂', 
			'Original Collaboration': '与原创作品合作', 
			'More Than 16 Hours Of Footage': '16时间以上作品', 
			'Huge Dick - Large Dick': '巨根', 
			'Fan Appreciation/ Home Visit': '粉丝答谢/探访', 
			'動画': '动画', 
			'Big Asses': '大屁股', 
			'ハーレム': '后宫', 
			'Suntan': '日光浴', 
			'Premature Ejaculation': '早泄', 
			'Kiss Kiss': '接吻', 
			'Sweating': '汗流浃背', 
			'Special Smartphone Vertical Video': '智能手机竖屏动画', 
			'Vシネマ': '影碟首发电影', 
			'Don Cipote\'s choice': '唐·西波特的精选', 
			'Anime': '动漫', 
			'Action': '动作', 
			'Pretty Boy': '男性形象视频', 
			'孕ませ': '怀孕', 
			'BL': '耽美', 
			'ビッチ': '婊子', 
			'特典あり（AVベースボール）': '附赠特典（AV）', 
			'コミック雑誌': '漫画杂志:', 
			'Time Freezing': '时间停止', 
			'YAKUZA': '黑帮成员', 
			'Childhood Friend': '童年朋友', 
			'Princess': '公主', 
			'Asian Actress': '亚洲女演员', 
			'Hostess': '伴侣', 
			'Instructor': '讲师', 
			'Stepmom': '婆婆', 
			'Action & Fighting': '格斗家', 
			'Female Detective': '女检察官', 
			'Lookalike': '明星脸', 
			'Housewife': '女主人、女老板', 
			'Model': '模特儿', 
			'Secretary': '秘书', 
			'Beautiful Girl': '美少女', 
			'Young Wife': '新娘、年轻妻子', 
			'Older Sister': '姐姐', 
			'Martial Arts': '格斗家', 
			'Bus Tour Guide': '车掌小姐', 
			'Widow': '寡妇', 
			'Princess & Mademoiselle': '千金小姐', 
			'Caucasian Actress': '白人', 
			'Married Woman': '已婚妇女', 
			'Female Doctor': '女医生', 
			'Various Worker': '各种职业', 
			'Club Hostess & Sex Worker': '妓女', 
			'Race Queen': '赛车女郎', 
			'College Girl': '女大学生', 
			'Campaign Girl': '展场女孩', 
			'Female Teacher': '女教师', 
			'MILF': '母亲', 
			'Private Tutor': '家教', 
			'Nurse': '护士', 
			'Slut': '荡妇', 
			'Black Man': '黑人演员', 
			'Gal': '女生', 
			'Female Anchor': '女主播', 
			'Schoolgirl': '高中女生', 
			'Waitress': '服务生', 
			'Magical Girl': '魔法少女', 
			'Student (Other)': '学生（其他）', 
			'Anime Character': '动画人物', 
			'Live Game Filming Edition': '游戏的真人版', 
			'Super Heroine': '超级女英雄', 
			'Female Soldier': '女战士', 
			'Knee-High Socks': '及膝袜', 
			'Doll': '娃娃', 
			'Female Ninja': '女忍者', 
			'Cross Dresser': '女装人妖', 
			'Panty Shot': '内衣', 
			'Non-nude Erotica': '猥褻穿著', 
			'Bunny Girl': '兔女郎', 
			'Animal Ears': '猫耳女', 
			'Priestess': '女祭司', 
			'Loose Socks': '泡泡袜', 
			'Uniform': '制服', 
			'Leotards': '紧身衣', 
			'Naked Apron': '裸体围裙', 
			'Miniskirt Police': '迷你裙警察', 
			'Stewardess': '空中小姐', 
			'Pantyhose': '连裤袜', 
			'Tight Dress': '身体意识', 
			'Office Lady': 'OL', 
			'KIMONO': '和服・丧服', 
			'Gym Clothes': '体育服', 
			'Lingerie': '内衣', 
			'Sailor Uniform': '水手服', 
			'School Swimsuits': '学校泳装', 
			'Chinese Dress': '旗袍', 
			'Maid': '女佣', 
			'Miniskirt': '迷你裙', 
			'School Uniform': '校服', 
			'Swimsuits': '泳装', 
			'Glasses': '眼镜', 
			'Cosplay': '角色扮演', 
			'GothLoli': '哥德萝莉', 
			'Huge Tits': '超乳', 
			'Muscular': '肌肉', 
			'Beautiful Tits': '乳房', 
			'Short & Petite': '娇小的', 
			'Ass Lover': '屁股', 
			'Tall Girl': '高', 
			'Transsexual': '变性者', 
			'Shaved Pussy': '无毛', 
			'Chubby': '胖女人', 
			'Slender': '苗条', 
			'Pregnant': '孕妇', 
			'Mature Woman': '成熟的女人', 
			'Lolicon': '萝莉塔', 
			'Small Tits': '贫乳・微乳', 
			'Big Tits': '巨乳', 
			'Face Sitting': '顏面骑乘', 
			'Scat': '食粪', 
			'Footjob': '足交', 
			'Breast Milk': '母乳', 
			'Fingering': '手指插入', 
			'Massage': '按摩', 
			'Cowgirl': '女上位', 
			'Cunnilingus': '舔阴', 
			'Fisting': '拳交', 
			'Deep Throat': '深喉', 
			'69': '69', 
			'Dirty Talk': '淫语', 
			'Squirting': '潮吹', 
			'Titty Fuck': '乳交', 
			'Pooping': '排便', 
			'Golden Shower': '饮尿', 
			'Blowjob': '口交', 
			'Orgy': '滥交', 
			'Urination': '放尿', 
			'Handjob': '打手枪', 
			'Cum Swallowing': '吞精', 
			'Anal': '肛交', 
			'BUKKAKE': '顏射', 
			'Masturbation': '自慰', 
			'Facial': '顏射', 
			'Creampie': '中出', 
			'AF': '肛内中出', 
			'Quickie': '立即口交', 
			'Big Vibrator': '女优按摩棒', 
			'G-Spot': '子宫颈', 
			'Hypnotism': '催眠', 
			'Lotion': '乳液', 
			'Shame': '羞耻', 
			'Torture & Rape': '凌辱', 
			'Tied Up': '拘束', 
			'Gang Bang': '轮姦', 
			'Object Insertion': '插入异物', 
			'Gyno Exam': '鸭嘴', 
			'Enema': '灌肠', 
			'Confinement': '监禁', 
			'Bondage': '紧缚', 
			'Rape': '强姦', 
			'Drugs': '药物', 
			'Car Sex': '汽车性爱', 
			'BDSM': 'SM', 
			'Scat': '粪便', 
			'Sex Toys': '玩具', 
			'Egg Vibrator': '跳蛋', 
			'Bondage': '紧缚', 
			'Vibrator': '按摩棒', 
			'Threesome / Foursome': '多P', 
			'Eros': '性爱', 
			'Dildo': '假阳具', 
			'Reverse Rape': '逆强姦', 
			'Collaboration work': '合作作品', 
			'Horror': '恐怖', 
			'Boys Love': '给女性观眾', 
			'How To': '教学', 
			'DMM Exclusive': 'DMM专属', 
			'R-15': 'R-15', 
			'Restricted to Under ': 'R-18', 
			'3D': '3D', 
			'Special Effects': '特效', 
			'Series': '故事集', 
			'Sale (limited time)': '限时降价', 
			'Reprint': '复刻版', 
			'Drama': '戏剧', 
			'Love': '恋爱', 
			'Hi-Def': '高画质', 
			'POV': '主观视角', 
			'Idol Video': '介绍影片', 
			'Over 4 Hours': '4小时以上作品', 
			'Minimal Mosaic': '薄马赛克', 
			'Classics': '经典', 
			'Debut': '首次亮相', 
			'Digital Mosaic': '数位马赛克', 
			'Homemade': '投稿', 
			'Documentary': '纪录片', 
			'Foreign Imports': '国外进口', 
			'POV': '第一人称摄影', 
			'Amateur': '业餘', 
			'Genital Close-Up': '局部特写', 
			'Independent': '独立製作', 
			'DMM Exclusive': 'DMM独家', 
			'Featured Actress': '单体作品', 
			'Compilation': '合集', 
			'High Definition': '高清', 
			'Subtitle': '字幕', 
			'Paradise TV': '天堂TV', 
			'DVD Toaster': 'DVD多士炉', 
			'AV OPEN 2014 スーパーヘビー': 'AV OPEN 2014 スーパーヘビー', 
			'AV OPEN 2014 ヘビー級': 'AV OPEN 2014 ヘビー级', 
			'AV OPEN 2014 ミドル級': 'AV OPEN 2014 ミド儿级', 
			'AV OPEN 2015 Kink/Fetish Division': 'AV OPEN 2015 マニア/フェチ部门', 
			'AV OPEN 2015 Cougar Division': 'AV OPEN 2015 熟女部门', 
			'AV OPEN 2015 Variety Show Division': 'AV OPEN 2015 企画部门', 
			'AV OPEN 2015 Virgin Division': 'AV OPEN 2015 乙女部门', 
			'AV OPEN 2015 Amateur Division': 'AV OPEN 2015 素人部门', 
			'AV OPEN 2015 S&M/Hardcore Division': 'AV OPEN 2015 SM/ハード部门', 
			'AV OPEN 2015 Porn Star Division': 'AV OPEN 2015 女优部门', 
			'AV OPEN 2016 Kink/Fetish Division': 'AVOPEN2016人妻・熟女部门', 
			'AV OPEN 2016 Variety Show Division': 'AVOPEN2016企画部门', 
			'AV OPEN 2016 S&M/Hardcore Division': 'AVOPEN2016ハード部门', 
			'AVOPEN2016マニア・フェチ部門': 'AVOPEN2016マニア・フェチ部门', 
			'AV OPEN 2016 Virgin Division': 'AVOPEN2016乙女部门', 
			'AV OPEN 2016 Porn Star Division': 'AVOPEN2016女优部门', 
			'AVOPEN2016ドラマ・ドキュメンタリー部門': 'AVOPEN2016ドラマ・ドキュメンタリー部门', 
			'AV OPEN 2016 Amateur Division': 'AVOPEN2016素人部门', 
			'AVOPEN2016バラエティ部門': 'AVOPEN2016バラエティ部门', 
			'VR': 'VR専用', 
			'Gag·Comedy': '堵嘴·喜剧', 
			'Fantasy': '幻想', 
			'Gender transformation·feminization': '性别转型·女性化', 
			'Recommended vertical video for smartphone': '為智能手机推荐垂直视频', 
			'Set items': '设置项目', 
			'Mini series': '迷你系列', 
			'Experience confession': '体验懺悔', 
			'Dark system': '黑暗系统', 
			'オナサポ': '自慰支持', 
			'アスリート': '运动员', 
			'覆面・マスク': '蒙面', 
			'ハイクオリティVR': '高品质VR', 
			'ヘルス・ソープ': '健康与肥皂店', 
			'ホテル': '酒店', 
			'アクメ・オーガズム': '高潮', 
			'花嫁': '新娘', 
			'デート': '约会', 
			'軟体': '柔软的身体', 
			'娘・養女': '女儿与继女', 
			'スパンキング': '打屁股', 
			'スワッピング・夫婦交換': '交换伴侣与换夫', 
			'部下・同僚': '下属与同事', 
			'旅行': '旅行', 
			'胸チラ': '露乳', 
			'バック': '后入式', 
			'エロス': '情色', 
			'男の潮吹き': '男性喷水', 
			'女上司': '女老板', 
			'セクシー': '性感', 
			'受付嬢': '接待员', 
			'ノーブラ': '不穿胸罩', 
			'白目・失神': '翻白眼与晕厥', 
			'M女': '受虐狂女性', 
			'女王様': '女虐待狂', 
			'ノーパン': '不穿内裤', 
			'セレブ': '名人', 
			'病院・クリニック': '医院与诊所', 
			'面接': '采访', 
			'お風呂': '浴室', 
			'叔母さん': '阿姨', 
			'罵倒': '戏弄', 
			'お爺ちゃん': '爷爷', 
			'逆レイプ': '反向强奸', 
			'ディルド': '女儿', 
			'ヨガ': '瑜伽', 
			'飲み会・合コン': '饮酒派对与集体约会', 
			'部活・マネージャー': '俱乐部活动与经理', 
			'お婆ちゃん': '奶奶', 
			'ビジネススーツ': '职业套装', 
			'チアガール': '啦啦队长', 
			'ママ友': '妈妈朋友', 
			'エマニエル': '艾曼纽', 
			'妄想族': '妄想家庭', 
			'蝋燭': '蜡烛', 
			'鼻フック': '鼻钩', 
			'放置': '放置', 
			'サンプル動画': '样品动画', 
			'サイコ・スリラー': '心理惊悚', 
			'ラブコメ': '浪漫喜剧', 
			'オタク': '宅男宅女', 
			'4K': '4K', 
			'福袋': '福袋', 
			'玩具責め': '玩具虐待', 
			'女優': '女演员', 
			'お掃除フェラ': '清洁口交', 
			'筆おろし': '铅笔羞辱', 
			'美脚': '美腿', 
			'美尻': '美臀', 
			'フェチ': '恋物癖', 
			'羞恥プレイ': '羞耻游戏', 
			'逆ナンパ': '反向搭讪', 
			'着衣': '着装', 
			'誘惑': '诱惑', 
			'チラリズム': '躲猫猫', 
			'写真集': '写真集', 
			'書籍版': '书籍版', 
			'SM拘束': 'SM束缚', 
			'ドキュメント': '纪录片', 
			'グッズ': '周边', 
			'Tシャツ': 'T恤', 
			'失禁': '失禁', 
			'オナホール': '飞机杯', 
			'カップホール': '杯洞', 
			'非貫通': '禁止交流', 
			'ローション付き': '含润滑液', 
			'配信専用': '仅限流媒体播放', 
			'官能小説': '情色小说', 
			'CD': 'CD', 
			'生挿入': '无套插入', 
			'風俗': '卖淫', 
			'外国人': '外国人', 
			'淫語責め': '污言秽语', 
			'アナルファック': '肛交', 
			'脚コキ': '足交', 
			'オイルプレイ': '油浴游戏', 
			'キャバ嬢': '家庭主妇', 
			'調教': '调教', 
			'ローション・オイル': '润肤露/油', 
			'媚薬': '催情剂', 
			'顔面騎乗位': '女上位颜射', 
			'微乳': '小胸', 
			'デカチン': '大阴茎', 
			'3P、4P': '3P、4P', 
			'野外': '户外', 
			'露出': '暴露癖', 
			'レイプ': '强奸', 
			'ベスト、総集編': '最佳合集', 
			'マジックミラー号': '魔镜面包车', 
			'看護師': '护士', 
			'アイドル': '偶像', 
			'妹': '妹妹', 
			'スクール水着': '学校泳装', 
			'デリヘル': '送货服务', 
			'凌辱': '羞辱', 
			'童貞モノ': '处女', 
			'ブルマ': '丑陋', 
			'ホテヘル': '酒店', 
			'縛り': '捆绑', 
			'ロリータ': '洛丽塔', 
			'ミニスカート': '迷你裙', 
			'尻': '屁股', 
			'奴隷': '奴隶', 
			'芸能人': '艺能人', 
			'下着': '内衣', 
			'母親': '母亲', 
			'湯': '浴室', 
			'教師': '教师', 
			'ストッキング': '街头性爱', 
			'電車、バス': '电车、公交车', 
			'健康診断': '健康检查', 
			'野球拳': '野球拳', 
			'浴衣': '浴衣', 
			'爆乳': '巨乳', 
			'ソープ': '泡泡浴', 
			'スワッピング': '换妻俱乐部', 
			'メガネ': '眼镜', 
			'素股': '素股', 
			'ドリンク': '饮料', 
			'フルハイビジョン(FHD)': '满的高清', 
			'三十路': '30多岁', 
			'羞恥・辱め': '羞耻/羞辱', 
			'パンチラモノ': '裙底偷拍', 
			'放尿・失禁': '小便/尿失禁', 
			'五十路': '50多岁', 
			'ショートヘアー': '短发', 
			'着物・浴衣': '和服/浴衣', 
			'清楚': '优雅', 
			'四十路': '40多岁', 
			'VR': 'VR', 
			'オモチャ': '玩具', 
			'エステ・マッサージ': '美容院/按摩', 
			'Gカップ': 'G罩杯', 
			'目隠し': '蒙眼', 
			'ドラッグ・媚薬': '药物/催情剂', 
			'六十路': '60多岁', 
			'淫語モノ': '污言秽语', 
			'口内発射': '口交', 
			'童顔': '娃娃脸', 
			'スチュワーデス・CA': '空姐/CA', 
			'Dカップ': 'D罩杯', 
			'美熟女': '美丽成熟女性', 
			'MGSだけのおまけ映像付き': 'MGS独家花絮', 
			'手マン': '手指爱抚', 
			'パンストモノ': '丝袜', 
			'フェラモノ': '口交', 
			'性教育': '性教育', 
			'HowTo': '教学', 
			'MGS限定特典映像': 'MGS独家花絮', 
			'寝取り･寝取られ': '绿帽/戴绿帽', 
			'Eカップ': 'E罩杯', 
			'Fカップ': 'F罩杯', 
			'ロングヘアー': '长发', 
			'黒髪': '黑发', 
			'ショートヘア': '短发', 
			'金髪': '金发', 
			'茶髪': '棕发', 
			'女子高生': '高中女生', 
			'ハーフ': '日裔混血', 
			'金髪・ブロンド': '金发', 
			'初撮り': '初次拍摄', 
			'介護': '护理', 
			'Hカップ': 'H罩杯', 
			'期間限定販売': '限时特惠', 
			'多人数': '群交', 
			'風俗嬢': '妓女', 
			'PICKUP素人': '搭讪业余', 
			'オイル・ローション': '油/乳液', 
			'8KVR': '8K VR', 
			'プレステージ20周年特別企画': '尊贵20周年特别版', 
			'口内射精': '口交极致体验', 
			'美女': '美丽', 
			'MGSだけの特典映像付': 'MGS独家花絮', 
			'色白': '白皙肌肤', 
			'総集編・ベスト': '合集/精选', 
			'近●相●': '乱伦', 
			'ハイビジョン(HD)': '高清 (HD)', 
			'配信専用素人': '仅限流媒体播放的业余作品', 
			'台湾モデル': '台湾模特', 
			'ショートカット': '短发', 
			'巨乳': '大胸', 
			'清楚': '干净', 
			'お姉さん': '熟女', 
			'長身': '高挑', 
			'ギャル': '辣妹', 
			'美乳': '美胸', 
			'パイパン': '剃毛', 
			'スレンダー': '苗条', 
			'貧乳・微乳': '小胸', 
			'ミニ系': '迷你', 
			'小柄': '娇小', 
			'くびれ': '沙漏型身材', 
			'ぽっちゃり': '丰满', 
			'黒髪': '黑发', 
			'色白': '白皙肌肤', 
			'金髪': '金发', 
			'茶髪': '棕发', 
			'美脚': '美腿', 
			'ロングヘアー': '长发', 
			'外国人': '外国人', 
			'ショートヘアー': '短发', 
			'お嬢様・令嬢': '年轻女士', 
			'ミディアムヘアー': '中长发', 
			'AI生成作品': 'AI生成作品', 
			'個人撮影': '个人撮影', 

			'折磨': '折磨', 
			'嘔吐': '呕吐', 
			'觸手': '触手', 
			'蠻橫嬌羞': '蛮横娇羞', 
			'處男': '处男', 
			'正太控': '正太控', 
			'出軌': '绿帽/戴绿帽', 
			'瘙癢': '瘙痒', 
			'運動': '运动', 
			'女同接吻': '女同接吻', 
			'性感的': '性感的', 
			'美容院': '美容院', 
			'處女': '处女', 
			'爛醉如泥的': '烂醉如泥的', 
			'殘忍畫面': '残忍画面', 
			'妄想': '妄想', 
			'惡作劇': '恶作剧', 
			'學校作品': '学校作品', 
			'粗暴': '粗暴', 
			'通姦': '通姦', 
			'姐妹': '姐妹', 
			'雙性人': '双性人', 
			'跳舞': '跳舞', 
			'性奴': '性奴', 
			'倒追': '倒追', 
			'性騷擾': '性骚扰', 
			'其他': '其他', 
			'戀腿癖': '恋腿癖', 
			'偷窥': '偷窥', 
			'花癡': '花痴', 
			'男同性恋': '男同性恋', 
			'情侶': '情侣', 
			'戀乳癖': '恋乳癖', 
			'亂倫': '乱伦', 
			'其他戀物癖': '其他恋物癖', 
			'偶像藝人': '偶像艺人', 
			'野外・露出': '野外・露出', 
			'獵豔': '猎艳', 
			'女同性戀': '女同性恋', 
			'企畫': '企画', 
			'10枚組': '10枚组', 
			'科幻': '科幻', 
			'女優ベスト・総集編': '最佳女演员/合集', 
			'温泉': '温泉', 
			'M男': '受虐狂', 
			'原作コラボ': '与原创作品合作', 
			'16時間以上作品': '16时间以上作品', 
			'デカチン・巨根': '巨根', 
			'ファン感謝・訪問': '粉丝答谢/探访', 
			'動画': '动画', 
			'巨尻': '大屁股', 
			'ハーレム': '后宫', 
			'日焼け': '日光浴', 
			'早漏': '早泄', 
			'キス・接吻': '接吻', 
			'汗だく': '汗流浃背', 
			'スマホ専用縦動画': '智能手机竖屏动画', 
			'Vシネマ': '影碟首发电影', 
			'Don Cipote\'s choice': '唐·西波特的精选', 
			'アニメ': '动漫', 
			'アクション': '动作', 
			'イメージビデオ（男性）': '男性形象视频', 
			'孕ませ': '怀孕', 
			'ボーイズラブ': '耽美', 
			'ビッチ': '婊子', 
			'特典あり（AVベースボール）': '附赠特典（AV）', 
			'コミック雑誌': '漫画杂志:', 
			'時間停止': '时间停止', 
			'黑幫成員': '黑帮成员', 
			'童年朋友': '童年朋友', 
			'公主': '公主', 
			'亞洲女演員': '亚洲女演员', 
			'伴侶': '伴侣', 
			'講師': '讲师', 
			'婆婆': '婆婆', 
			'格鬥家': '格斗家', 
			'女檢察官': '女检察官', 
			'明星臉': '明星脸', 
			'女主人、女老板': '女主人、女老板', 
			'模特兒': '模特儿', 
			'秘書': '秘书', 
			'美少女': '美少女', 
			'新娘、年輕妻子': '新娘、年轻妻子', 
			'姐姐': '姐姐', 
			'格鬥家': '格斗家', 
			'車掌小姐': '车掌小姐', 
			'寡婦': '寡妇', 
			'千金小姐': '千金小姐', 
			'白人': '白人', 
			'已婚婦女': '已婚妇女', 
			'女醫生': '女医生', 
			'各種職業': '各种职业', 
			'妓女': '妓女', 
			'賽車女郎': '赛车女郎', 
			'女大學生': '女大学生', 
			'展場女孩': '展场女孩', 
			'女教師': '女教师', 
			'母親': '母亲', 
			'家教': '家教', 
			'护士': '护士', 
			'蕩婦': '荡妇', 
			'黑人演員': '黑人演员', 
			'女生': '女生', 
			'女主播': '女主播', 
			'高中女生': '高中女生', 
			'服務生': '服务生', 
			'魔法少女': '魔法少女', 
			'學生（其他）': '学生（其他）', 
			'動畫人物': '动画人物', 
			'遊戲的真人版': '游戏的真人版', 
			'超級女英雄': '超级女英雄', 
			'女戰士': '女战士', 
			'及膝襪': '及膝袜', 
			'娃娃': '娃娃', 
			'女忍者': '女忍者', 
			'女裝人妖': '女装人妖', 
			'內衣': '内衣', 
			'猥褻穿著': '猥褻穿著', 
			'兔女郎': '兔女郎', 
			'貓耳女': '猫耳女', 
			'女祭司': '女祭司', 
			'泡泡襪': '泡泡袜', 
			'制服': '制服', 
			'緊身衣': '紧身衣', 
			'裸體圍裙': '裸体围裙', 
			'迷你裙警察': '迷你裙警察', 
			'空中小姐': '空中小姐', 
			'連褲襪': '连裤袜', 
			'身體意識': '身体意识', 
			'OL': 'OL', 
			'和服・喪服': '和服・丧服', 
			'體育服': '体育服', 
			'內衣': '内衣', 
			'水手服': '水手服', 
			'學校泳裝': '学校泳装', 
			'旗袍': '旗袍', 
			'女傭': '女佣', 
			'迷你裙': '迷你裙', 
			'校服': '校服', 
			'泳裝': '泳装', 
			'眼鏡': '眼镜', 
			'角色扮演': '角色扮演', 
			'哥德蘿莉': '哥德萝莉', 
			'超乳': '超乳', 
			'肌肉': '肌肉', 
			'乳房': '乳房', 
			'嬌小的': '娇小的', 
			'屁股': '屁股', 
			'高': '高', 
			'變性者': '变性者', 
			'無毛': '无毛', 
			'胖女人': '胖女人', 
			'苗條': '苗条', 
			'孕婦': '孕妇', 
			'成熟的女人': '成熟的女人', 
			'蘿莉塔': '萝莉塔', 
			'貧乳・微乳': '贫乳・微乳', 
			'巨乳': '巨乳', 
			'顏面騎乘': '顏面骑乘', 
			'食糞': '食粪', 
			'足交': '足交', 
			'母乳': '母乳', 
			'手指插入': '手指插入', 
			'按摩': '按摩', 
			'女上位': '女上位', 
			'舔陰': '舔阴', 
			'拳交': '拳交', 
			'深喉': '深喉', 
			'69': '69', 
			'淫語': '淫语', 
			'潮吹': '潮吹', 
			'乳交': '乳交', 
			'排便': '排便', 
			'飲尿': '饮尿', 
			'口交': '口交', 
			'濫交': '滥交', 
			'放尿': '放尿', 
			'打手槍': '打手枪', 
			'吞精': '吞精', 
			'肛交': '肛交', 
			'顏射': '顏射', 
			'自慰': '自慰', 
			'顏射': '顏射', 
			'中出': '中出', 
			'肛内中出': '肛内中出', 
			'立即口交': '立即口交', 
			'女優按摩棒': '女优按摩棒', 
			'子宮頸': '子宫颈', 
			'催眠': '催眠', 
			'乳液': '乳液', 
			'羞恥': '羞耻', 
			'凌辱': '凌辱', 
			'拘束': '拘束', 
			'輪姦': '轮姦', 
			'插入異物': '插入异物', 
			'鴨嘴': '鸭嘴', 
			'灌腸': '灌肠', 
			'監禁': '监禁', 
			'紧缚': '紧缚', 
			'強姦': '强姦', 
			'藥物': '药物', 
			'汽車性愛': '汽车性爱', 
			'SM': 'SM', 
			'糞便': '粪便', 
			'玩具': '玩具', 
			'跳蛋': '跳蛋', 
			'緊縛': '紧缚', 
			'按摩棒': '按摩棒', 
			'多P': '多P', 
			'性愛': '性爱', 
			'假陽具': '假阳具', 
			'逆強姦': '逆强姦', 
			'合作作品': '合作作品', 
			'恐怖': '恐怖', 
			'給女性觀眾': '给女性观眾', 
			'教學': '教学', 
			'DMM專屬': 'DMM专属', 
			'R-15': 'R-15', 
			'R-18': 'R-18', 
			'3D': '3D', 
			'特效': '特效', 
			'故事集': '故事集', 
			'限時降價': '限时降价', 
			'複刻版': '复刻版', 
			'戲劇': '戏剧', 
			'戀愛': '恋爱', 
			'高畫質': '高画质', 
			'主觀視角': '主观视角', 
			'介紹影片': '介绍影片', 
			'4小時以上作品': '4小时以上作品', 
			'薄馬賽克': '薄马赛克', 
			'經典': '经典', 
			'首次亮相': '首次亮相', 
			'數位馬賽克': '数位马赛克', 
			'投稿': '投稿', 
			'纪录片': '纪录片', 
			'國外進口': '国外进口', 
			'第一人稱攝影': '第一人称摄影', 
			'業餘': '业餘', 
			'局部特寫': '局部特写', 
			'獨立製作': '独立製作', 
			'DMM獨家': 'DMM独家', 
			'單體作品': '单体作品', 
			'合集': '合集', 
			'高清': '高清', 
			'字幕': '字幕', 
			'天堂TV': '天堂TV', 
			'DVD多士爐': 'DVD多士炉', 
			'AV OPEN 2014 スーパーヘビー': 'AV OPEN 2014 スーパーヘビー', 
			'AV OPEN 2014 ヘビー級': 'AV OPEN 2014 ヘビー级', 
			'AV OPEN 2014 ミドル級': 'AV OPEN 2014 ミド儿级', 
			'AV OPEN 2015 マニア/フェチ部門': 'AV OPEN 2015 マニア/フェチ部门', 
			'AV OPEN 2015 熟女部門': 'AV OPEN 2015 熟女部门', 
			'AV OPEN 2015 企画部門': 'AV OPEN 2015 企画部门', 
			'AV OPEN 2015 乙女部門': 'AV OPEN 2015 乙女部门', 
			'AV OPEN 2015 素人部門': 'AV OPEN 2015 素人部门', 
			'AV OPEN 2015 SM/ハード部門': 'AV OPEN 2015 SM/ハード部门', 
			'AV OPEN 2015 女優部門': 'AV OPEN 2015 女优部门', 
			'AVOPEN2016人妻・熟女部門': 'AVOPEN2016人妻・熟女部门', 
			'AVOPEN2016企画部門': 'AVOPEN2016企画部门', 
			'AVOPEN2016ハード部門': 'AVOPEN2016ハード部门', 
			'AVOPEN2016マニア・フェチ部門': 'AVOPEN2016マニア・フェチ部门', 
			'AVOPEN2016乙女部門': 'AVOPEN2016乙女部门', 
			'AVOPEN2016女優部門': 'AVOPEN2016女优部门', 
			'AVOPEN2016ドラマ・ドキュメンタリー部門': 'AVOPEN2016ドラマ・ドキュメンタリー部门', 
			'AVOPEN2016素人部門': 'AVOPEN2016素人部门', 
			'AVOPEN2016バラエティ部門': 'AVOPEN2016バラエティ部门', 
			'VR専用': 'VR専用', 
			'堵嘴·喜劇': '堵嘴·喜剧', 
			'幻想': '幻想', 
			'性別轉型·女性化': '性别转型·女性化', 
			'為智能手機推薦垂直視頻': '為智能手机推荐垂直视频', 
			'設置項目': '设置项目', 
			'迷你係列': '迷你系列', 
			'體驗懺悔': '体验懺悔', 
			'黑暗系統': '黑暗系统', 
			'オナサポ': '自慰支持', 
			'アスリート': '运动员', 
			'覆面・マスク': '蒙面', 
			'ハイクオリティVR': '高品质VR', 
			'ヘルス・ソープ': '健康与肥皂店', 
			'ホテル': '酒店', 
			'アクメ・オーガズム': '高潮', 
			'花嫁': '新娘', 
			'デート': '约会', 
			'軟体': '柔软的身体', 
			'娘・養女': '女儿与继女', 
			'スパンキング': '打屁股', 
			'スワッピング・夫婦交換': '交换伴侣与换夫', 
			'部下・同僚': '下属与同事', 
			'旅行': '旅行', 
			'胸チラ': '露乳', 
			'バック': '后入式', 
			'エロス': '情色', 
			'男の潮吹き': '男性喷水', 
			'女上司': '女老板', 
			'セクシー': '性感', 
			'受付嬢': '接待员', 
			'ノーブラ': '不穿胸罩', 
			'白目・失神': '翻白眼与晕厥', 
			'M女': '受虐狂女性', 
			'女王様': '女虐待狂', 
			'ノーパン': '不穿内裤', 
			'セレブ': '名人', 
			'病院・クリニック': '医院与诊所', 
			'面接': '采访', 
			'お風呂': '浴室', 
			'叔母さん': '阿姨', 
			'罵倒': '戏弄', 
			'お爺ちゃん': '爷爷', 
			'逆レイプ': '反向强奸', 
			'ディルド': '女儿', 
			'ヨガ': '瑜伽', 
			'飲み会・合コン': '饮酒派对与集体约会', 
			'部活・マネージャー': '俱乐部活动与经理', 
			'お婆ちゃん': '奶奶', 
			'ビジネススーツ': '职业套装', 
			'チアガール': '啦啦队长', 
			'ママ友': '妈妈朋友', 
			'エマニエル': '艾曼纽', 
			'妄想族': '妄想家庭', 
			'蝋燭': '蜡烛', 
			'鼻フック': '鼻钩', 
			'放置': '放置', 
			'サンプル動画': '样品动画', 
			'サイコ・スリラー': '心理惊悚', 
			'ラブコメ': '浪漫喜剧', 
			'オタク': '宅男宅女', 
			'4K': '4K', 
			'福袋': '福袋', 
			'玩具責め': '玩具虐待', 
			'女優': '女演员', 
			'お掃除フェラ': '清洁口交', 
			'筆おろし': '铅笔羞辱', 
			'美脚': '美腿', 
			'美尻': '美臀', 
			'フェチ': '恋物癖', 
			'羞恥プレイ': '羞耻游戏', 
			'逆ナンパ': '反向搭讪', 
			'着衣': '着装', 
			'誘惑': '诱惑', 
			'チラリズム': '躲猫猫', 
			'写真集': '写真集', 
			'書籍版': '书籍版', 
			'SM拘束': 'SM束缚', 
			'ドキュメント': '纪录片', 
			'グッズ': '周边', 
			'Tシャツ': 'T恤', 
			'失禁': '失禁', 
			'オナホール': '飞机杯', 
			'カップホール': '杯洞', 
			'非貫通': '禁止交流', 
			'ローション付き': '含润滑液', 
			'配信専用': '仅限流媒体播放', 
			'官能小説': '情色小说', 
			'CD': 'CD', 
			'生挿入': '无套插入', 
			'風俗': '卖淫', 
			'外国人': '外国人', 
			'淫語責め': '污言秽语', 
			'アナルファック': '肛交', 
			'脚コキ': '足交', 
			'オイルプレイ': '油浴游戏', 
			'キャバ嬢': '家庭主妇', 
			'調教': '调教', 
			'ローション・オイル': '润肤露/油', 
			'媚薬': '催情剂', 
			'顔面騎乗位': '女上位颜射', 
			'微乳': '小胸', 
			'デカチン': '大阴茎', 
			'3P、4P': '3P、4P', 
			'野外': '户外', 
			'露出': '暴露癖', 
			'レイプ': '强奸', 
			'ベスト、総集編': '最佳合集', 
			'マジックミラー号': '魔镜面包车', 
			'看護師': '护士', 
			'アイドル': '偶像', 
			'妹': '妹妹', 
			'スクール水着': '学校泳装', 
			'デリヘル': '送货服务', 
			'凌辱': '羞辱', 
			'童貞モノ': '处女', 
			'ブルマ': '丑陋', 
			'ホテヘル': '酒店', 
			'縛り': '捆绑', 
			'ロリータ': '洛丽塔', 
			'ミニスカート': '迷你裙', 
			'尻': '屁股', 
			'奴隷': '奴隶', 
			'芸能人': '艺能人', 
			'下着': '内衣', 
			'母親': '母亲', 
			'湯': '浴室', 
			'教師': '教师', 
			'ストッキング': '街头性爱', 
			'電車、バス': '电车、公交车', 
			'健康診断': '健康检查', 
			'野球拳': '野球拳', 
			'浴衣': '浴衣', 
			'爆乳': '巨乳', 
			'ソープ': '泡泡浴', 
			'スワッピング': '换妻俱乐部', 
			'メガネ': '眼镜', 
			'素股': '素股', 
			'ドリンク': '饮料', 
			'フルハイビジョン(FHD)': '满的高清', 
			'三十路': '30多岁', 
			'羞恥・辱め': '羞耻/羞辱', 
			'パンチラモノ': '裙底偷拍', 
			'放尿・失禁': '小便/尿失禁', 
			'五十路': '50多岁', 
			'ショートヘアー': '短发', 
			'着物・浴衣': '和服/浴衣', 
			'清楚': '优雅', 
			'四十路': '40多岁', 
			'VR': 'VR', 
			'オモチャ': '玩具', 
			'エステ・マッサージ': '美容院/按摩', 
			'Gカップ': 'G罩杯', 
			'目隠し': '蒙眼', 
			'ドラッグ・媚薬': '药物/催情剂', 
			'六十路': '60多岁', 
			'淫語モノ': '污言秽语', 
			'口内発射': '口交', 
			'童顔': '娃娃脸', 
			'スチュワーデス・CA': '空姐/CA', 
			'Dカップ': 'D罩杯', 
			'美熟女': '美丽成熟女性', 
			'MGSだけのおまけ映像付き': 'MGS独家花絮', 
			'手マン': '手指爱抚', 
			'パンストモノ': '丝袜', 
			'フェラモノ': '口交', 
			'性教育': '性教育', 
			'HowTo': '教学', 
			'MGS限定特典映像': 'MGS独家花絮', 
			'寝取り･寝取られ': '绿帽/戴绿帽', 
			'Eカップ': 'E罩杯', 
			'Fカップ': 'F罩杯', 
			'ロングヘアー': '长发', 
			'黒髪': '黑发', 
			'ショートヘア': '短发', 
			'金髪': '金发', 
			'茶髪': '棕发', 
			'女子高生': '高中女生', 
			'ハーフ': '日裔混血', 
			'金髪・ブロンド': '金发', 
			'初撮り': '初次拍摄', 
			'介護': '护理', 
			'Hカップ': 'H罩杯', 
			'期間限定販売': '限时特惠', 
			'多人数': '群交', 
			'風俗嬢': '妓女', 
			'PICKUP素人': '搭讪业余', 
			'オイル・ローション': '油/乳液', 
			'8KVR': '8K VR', 
			'プレステージ20周年特別企画': '尊贵20周年特别版', 
			'口内射精': '口交极致体验', 
			'美女': '美丽', 
			'MGSだけの特典映像付': 'MGS独家花絮', 
			'色白': '白皙肌肤', 
			'総集編・ベスト': '合集/精选', 
			'近●相●': '乱伦', 
			'ハイビジョン(HD)': '高清 (HD)', 
			'配信専用素人': '仅限流媒体播放的业余作品', 
			'台湾モデル': '台湾模特', 
			'ショートカット': '短发', 
			'巨乳': '巨乳', 
			'清楚': '干净', 
			'お姉さん': '熟女', 
			'長身': '高挑', 
			'ギャル': '辣妹', 
			'美乳': '美胸', 
			'パイパン': '剃毛', 
			'スレンダー': '苗条', 
			'貧乳・微乳': '小胸', 
			'ミニ系': '迷你', 
			'小柄': '娇小', 
			'くびれ': '沙漏型身材', 
			'ぽっちゃり': '丰满', 
			'黒髪': '黑发', 
			'色白': '白皙肌肤', 
			'金髪': '金发', 
			'茶髪': '棕发', 
			'美脚': '美腿', 
			'ロングヘアー': '长发', 
			'外国人': '外国人', 
			'ショートヘアー': '短发', 
			'お嬢様・令嬢': '年轻女士', 
			'ミディアムヘアー': '中长发', 
			'AI生成作品': 'AI生成作品', 
			'個人撮影': '个人撮影',
			# patch
			'騎在臉上': '顏面骑乘',
			'艾玛妮': '艾曼纽',
			'被遗弃': '放置',
			'擦洗口交': '清洁口交',
			'第一視角': '第一视角',
			'後入': '后入',
			'後入內射': '后入內射',
			'護士': '护士',
			'紀錄片': '纪录片',
			'嬌小': '娇小',
			'巨大陽具': '巨根',
			'巨大陰莖': '巨根',
			'劇情': '剧情',
			'老師': '教师',
			'戀物癖': '恋物癖',
			'旅館': '酒店',
			'S級女優': 'S级女优', 
			'VR専用': 'VR专用', 
			'业餘': '业余', 
			'亂交': '乱交',  
			'体验懺悔': '体验忏悔', 
			'做家務': '做家务', 
			'側位內射': '侧位内射',  
			'同性戀': '同性恋', 
			'喪服': '丧服',  
			'學校': '学校', 
			'店員' :'店员',
			'廚房': '厨房',  
			'房間': '房间', 
			'手銬': '手铐',
			'打底褲': '打底裤', 
			'振動': '震动',
			'推薦作品': '推荐作品',
			'晚禮服': '晚礼服',
			'檢查': '检查', 
			'沙發': '沙发',
			'治癒系': '治愈系', 
			'淫亂真實': '淫乱真实', 
			'淫蕩': '淫荡', 
			'滥交': '滥交', 
			'煩惱': '烦恼',  
			'牛仔褲': '牛仔裤',
			'猥褻穿著': '猥亵穿着',
			'短褲': '短裤',  
			'綁縛': '绑缚', 
			'網襪': '网袜',
			'给女性观眾': '给女性观众', 
			'職員': '职员', 
			'肛門': '肛门',
			'蘿莉': '萝莉',  
			'裸體襪子': '裸体袜子', 
			'視訊小姐': '视讯小姐',  
			'變態': '变态',  
			'豐滿': '丰满', 
			'購物': '购物',  
			'轮姦': '轮奸', 
			'連續內射': '连续内射', 
			'連衣裙': '连衣裙', 
			'遠程操作': '远程操作', 
			'醫生': '医生', 
			'長發': '长发', 
			'門口': '门口', 
			'陰道觀察': '阴道观察',
			'電動按摩器': '电动按摩棒',
			'電動陽具': '电动阳具', 
			'不戴胸罩':  '不穿胸罩', 
			'主婦': '主妇', 
			'內射':  '内射',
			'不穿內褲': '不穿内裤', 
			'偶像':  '偶像艺人',
			'偷拍':  '偷窥', 
			'后入式':  '后入', 
			'偷窺':  '偷窥', 
			'大胸': '巨乳', 
			'大阴茎': '巨根', 
			'女仆': '女佣',
			'女僕': '女佣',
			'强姦': '强奸',
			'性感的': '性感',
			'搭訕': '搭讪' ,
			'最佳合集': '最佳女演员/合集', 
			'服侍': '服务生',
			'模特': '模特儿', 
			'泳衣':  '泳装',
			'淫亂': '淫乱', 
			'溫泉': '温泉', 
			'满的高清': '高清', 
			'騎乘位':  '骑乘位', 
			'首次':  '首次亮相', 
			'首次作品':  '首次亮相', 
			'颜射':'顏射',  
			'通姦':'通奸',
			'第一人称摄影':'第一视角', 
			'站立姿勢': '站立位', 
			'白領': '白领', 
			'独立製作':'独立影片', 
			'無碼流出':'无码流出', 
			'無碼破解' :'无码流出', 
			'潤滑劑' :'含润滑液', 
			'潤滑油' :'含润滑液'
			
        }

        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
        items_endpoint = f'{self.server_url}/Items'
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Movie',
            'Fields': 'Genres,GenreItems',
            'Limit': '1000000'
        }

        response = requests.get(items_endpoint, headers=headers, params=params)

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

                movie = self.emby_get_item_info(movie_id)
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

                    update_endpoint = f'{self.server_url}/emby/Items/{movie_id}?/api_key={self.api_key}'
                    update_response = requests.post(update_endpoint, headers=headers, data=json.dumps(movie))

                    if update_response.status_code in [200, 204]:
                        update_count += 1
                        updated_movies.append(movie)
                        self.logger.info(f"影片: {movie['Name']} 流派信息已更新。(Total updates: {update_count})")
                    else:
                        self.logger.error(f"更新失败，状态码: {update_response.status_code}(Total updates: {update_count})")
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
        # Set API request headers
        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }

        # Get the API endpoint for all movies
        items_endpoint = f'{self.server_url}/Items'

        # Set query parameters
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Movie',
            'Fields': 'Genres',  # Request to include the Genres field
            'Limit': '1000000'  # Adjust the limit according to your needs
        }

        # Send request to get the list of movies
        response = requests.get(items_endpoint, headers=headers, params=params)

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
        # Set API request headers
        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }

        # Get the API endpoint for all movies
        items_endpoint = f'{self.server_url}/Items'

        # Set query parameters
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Series',
            'Fields': 'Genres',  # Request to include the Genres field
            'Limit': '1000000'  # Adjust the limit according to your needs 后续解析"TotalRecordCount":1812字段
        }

        # Send request to get the list of movies
        response = requests.get(items_endpoint, headers=headers, params=params)

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

    def update_genress(self, callback=None):
        def run_update_genress_check():
            self.logger.info(f"开始更新影片流派信息...")
            updated_movies = self.emby_movie_translate_genres_and_update_whole_item()
            self.logger.info(f"完成更新影片流派信息")
            self.logger.info(f"开始更新剧集流派信息...")
            updated_series = self.emby_tv_translate_genres_and_update_whole_item()
            self.logger.info(f"完成更新剧集流派信息")

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
        
        thread = threading.Thread(target=run_update_genress_check)
        thread.start()


    def clear_files_by_type(self, folderPath, filetype= 'VIDEO', callback=None):
        def run_clear_files_by_type_check():
            num = 0
            # 要删除的文件后缀
            for root, dirs, files in os.walk(folderPath):
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
        
        thread = threading.Thread(target=run_clear_files_by_type_check)
        thread.start()

    def check_metadata_integrity(self, folderPath, callback=None):
        def run_check_metadata_integrity_check():
            video_check_result = self.check_video_files(folderPath)
            nfo_check_result = self.check_nfo_files(folderPath)

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
        
        thread = threading.Thread(target=run_check_metadata_integrity_check)
        thread.start()


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
        results = {
            'total_nfo': 0,
            'no_video_nfo': [],
            'found_video_nfo': []
        }    

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

    def check_video_files(self,folder_path):
        # 初始化结果汇总
        results = {
            'total_videos': 0,
            'no_nfo_videos': [],
            'found_nfo_videos': []
        }

        # 遍历指定文件夹及其子文件夹
        for root, _, files in os.walk(folder_path):
            video_files = [f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS]
            
            for video_file in video_files:      
                if not os.path.isfile(video_file):
                    continue
                results['total_videos'] += 1
                base_name, _ = os.path.splitext(video_file)
                nfo_file = base_name + '.nfo'
                
                video_full_path = os.path.join(root, video_file)
                nfo_full_path = os.path.join(root, nfo_file)
                
                if not os.path.exists(nfo_full_path):
                    results['no_nfo_videos'].append(video_full_path)
                else:
                    results['found_nfo_videos'].append(video_full_path)
        
        return results