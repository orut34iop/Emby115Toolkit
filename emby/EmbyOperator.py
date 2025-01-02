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

class EmbyOperator:
    def __init__(
        self,
        server_url,
        api_key,
        user_id=None,
        logger=None  # 添加logger参数
    ):
        self.server_url = server_url
        self.api_key = api_key
        self.user_id = user_id
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger

    def check_duplicate(self, target_folder, callback):
        def run_check():
            total_items = 0
            duplicate_items = 0
            start_time = time.time()
            remove_duplicate_nfo_file = "no"
            self.logger.info(f"连接emby服务器 : {self.server_url} ......")
            all_movies = self.get_all_movies()
            if not all_movies:
                self.logger.info("Emby库里没有影片")
                return    
            self.logger.info(f"已连接服务器数据库，数据库共 {len(all_movies)} 部影片")
    
            self.logger.info(f"开始查询...")
            # 归地遍历指定路径下的所有子目录和文件
            for root, dirs, files in os.walk(target_folder):
                for file in files:
                    if file.endswith('.nfo'):
                        nfo_path = os.path.join(root, file)
                        query_emdb_value = self.extract_tmdbid_from_nfo(nfo_path)
                        if query_emdb_value is not None:
                            total_items += 1
                            if not self.query_movies_by_tmdbid(all_movies, query_emdb_value):
                                pass
                                self.logger.info(f"发现新影片 : '{nfo_path}' ")
                                self.logger.info(f"新影片路径 : '{os.path.dirname(nfo_path)}' ")
                                self.logger.info(f"新影片名 :   '{os.path.basename(nfo_path)}' ")
                            else:
                                duplicate_items += 1
                                self.logger.info(f"发现重复影片:  '{nfo_path}' ")
                                self.logger.info(f"重复影片路径 : '{os.path.dirname(nfo_path)}' ")
                                self.logger.info(f"重复影片名 :   '{os.path.basename(nfo_path)}' ")                                
                                if remove_duplicate_nfo_file == "yes":
                                    os.remove(nfo_path)
                                    self.logger.info(f"删除重复影片nfo : '{nfo_path}' ")

            end_time = time.time()
            total_time = end_time - start_time
            message = f"更新元数据:总耗时 {total_time:.2f} 秒, 共查询影剧数：{total_items}个，发现重复影剧：{duplicate_items}"
            self.logger.info(message)
            if callback:
                callback(total_time, message)

        thread = threading.Thread(target=run_check)
        thread.start()

    # 获取所有影片的信息
    def get_all_movies(self):
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
                # self.logger.info(f"影片 '{movie['Name']}' 存在于 Emby 库中，TMDB 值: {tmdb_value}")
                return True
        # self.logger.info(f"没有找到与 TMDB 值 {tmdb_value} 相同的影片。")
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
                return query_tmdbid

        except ET.ParseError as e:
            self.logger.error(f"解析错误：无法解析文件 '{nfo_path}'，错误信息: {e}")
            #异常的原因可能是xml不完整,再次尝试强制解析
            return self.force_extract_tmdbid_from_file(nfo_path)  # 修改这里，添加 self
        except Exception as e:
            self.logger.error(f"发生错误：在处理文件 '{nfo_path}' 时出错，错误信息: {e}")

        return None

    def force_extract_tmdbid_from_file(self,file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        for i, line in enumerate(lines):
            match = re.search(r'  <tmdbid>(\d+)<', line) #<tmdbid>前面要有两个空格
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

    # 合并同一个TMDb ID下的不同版本
    def merge_movie_versions(self, grouped_movies):
        merged_movies = []
        for tmdb_id, movies in grouped_movies.items():
            if len(movies) > 1:
                name = movies[0]["Name"]
                self.logger.info(f"已发现相同版本的影片::: {name} \n")

                item_ids = ",".join(movie["Id"] for movie in movies)
                merge_url = f"{self.server_url}/emby/Videos/MergeVersions"
                payload = {
                    "Ids": item_ids,
                    "X-Emby-Token": self.api_key,
                }
                self.logger.info(f"合并版本成功::: {name}\n")
                response = requests.post(merge_url, params=payload)
                if response.status_code == 204:
                    self.logger.info(f"合并版本成功::: {name}")
                else:
                    self.logger.error(f"合并版本失败::: {name}")
                merged_movies.append(movies[0])  # 暂时保留第一部影片为合并结果
        return merged_movies

    def merge_versions(self, callback):
        def run_merge_versions_check():
            all_movies = self.get_all_movies()
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

        genres_map = {
            'Action': '动作',
            'Adventure': '冒险',
            'Animation': '动画',
            'Biography': '传记',
            'Comedy': '喜剧',
            'Crime': '犯罪',
            'Documentary': '纪录',
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
            'Reality': '真人秀',
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
            'Western': '西部'
        }

        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
        items_endpoint = f'{self.server_url}/Items'
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Series',
            'Fields': 'Genres',
            'Limit': '1000000'
        }

        response = requests.get(items_endpoint, headers=headers, params=params)

        if response.status_code == 200:
            tvs = response.json().get('Items', [])
            
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
                    genreitems = [{'Name': genres_map.get(genreitem['Name'], genreitem['Name']), 'Id': genreitem['Id']} for genreitem in tv.get('GenreItems', [])]
                    tv['Genres'] = translated_genres
                    tv['GenreItems'] = genreitems

                    update_endpoint = f'{self.server_url}/emby/Items/{tv_id}?/api_key={self.api_key}'
                    update_response = requests.post(update_endpoint, headers=headers, data=json.dumps(tv))

                    if update_response.status_code in [200, 204]:
                        update_count += 1
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

    def emby_movie_translate_genres_and_update_whole_item(self):
        total_count = 0
        update_count = 0
        genres_map = {
            'Action': '动作', 
            'Adult': '成人', 
            'Adventure': '冒险', 
            'Animation': '动画', 
            'Anime': '动漫',
            'Biography': '传记', 
            'Children': '儿童', 
            'Comedy': '喜剧', 
            'Crime': '犯罪', 
            'Documentary': '纪录',
            'Drama': '剧情', 
            'Eastern': '东方', 
            'Erotic': '情色',
            'Family': '家庭', 
            'Fantasy': '奇幻',
            'Film Noir': '黑色影片', 
            'History': '历史', 
            'Holiday': '节日', 
            'Horror': '恐怖', 
            'Indie': '独立影片',
            'Martial Arts': '武术', 
            'Music': '音乐', 
            'Musical': '音乐剧', 
            'Mystery': '悬疑', 
            'News': '新闻',
            'Reality TV': '真人秀',
            'Romance': '爱情', 
            'Science Fiction': '科幻', 
            'Short': '短片', 
            'Sport': '运动',
            'Suspense': '悬念', 
            'TV Movie': '电视影片', 
            'Thriller': '惊悚', 
            'War': '战争', 
            'Western': '西部',
            'superhero': '超级英雄'
        }

        headers = {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
        items_endpoint = f'{self.server_url}/Items'
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'Movie',
            'Fields': 'Genres',
            'Limit': '1000000'
        }

        response = requests.get(items_endpoint, headers=headers, params=params)

        if response.status_code == 200:
            movies = response.json().get('Items', [])
            
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
                    genreitems = [{'Name': genres_map.get(genreitem['Name'], genreitem['Name']), 'Id': genreitem['Id']} for genreitem in movie.get('GenreItems', [])]
                    movie['Genres'] = translated_genres
                    movie['GenreItems'] = genreitems

                    update_endpoint = f'{self.server_url}/emby/Items/{movie_id}?/api_key={self.api_key}'
                    update_response = requests.post(update_endpoint, headers=headers, data=json.dumps(movie))

                    if update_response.status_code in [200, 204]:
                        update_count += 1
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

    def update_genress(self, callback):
        def run_update_genress_check():
            self.logger.info(f"开始更新影片流派信息...")
            self.emby_movie_translate_genres_and_update_whole_item()
            self.logger.info(f"完成更新影片流派信息")
            self.logger.info(f"开始更新剧集流派信息...")
            self.emby_tv_translate_genres_and_update_whole_item()
            self.logger.info(f"完成更新影片流派信息")
            message = f"完成更新所有影剧流派"
            if callback:
                callback(message)

            return message
        
        thread = threading.Thread(target=run_update_genress_check)
        thread.start()