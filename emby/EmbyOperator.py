import os
import threading
import time
import queue
import requests
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
        logger=None  # 添加logger参数
    ):
        self.server_url = server_url
        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger

    def check_duplicate(self,target_folder):
        total_items = 0
        duplicate_items = 0
        start_time = time.time()
        remove_duplicate_nfo_file = "no"
        self.logger.info(f"连接emby服务器 : {self.server_url} ......")
        all_movies = self.get_all_movies()
        if not all_movies:
            self.logger.info("Emby库里没有电影")
            return    
        self.logger.info(f"已连接服务器数据库，数据库共 {len(all_movies)} 部电影")
 
        self.logger.info(f"开始查询...")
        # 归地遍历指定路径下的所有子目录和文件
        for root, dirs, files in os.walk(target_folder):
            for file in files:
                if file.endswith('.nfo'):
                    nfo_path = os.path.join(root, file)
                    query_emdb_value = self.extract_tmdbid_from_nfo(nfo_path)
                    if query_emdb_value is not None:
                        total_items += 1
                        if not self.query_movies_by_tmdbid(all_movies,query_emdb_value):
                            pass
                            # self.logger.info(f"发现新电影 : '{nfo_path}' ")
                        else:
                            duplicate_items += 1
                            self.logger.info(f"发现重复电影: {nfo_path} ")
                            if remove_duplicate_nfo_file == "yes":
                                os.remove(nfo_path)
                                self.logger.info(f"删除重复电影nfo : '{nfo_path}' ")

        end_time = time.time()
        total_time = end_time - start_time
        message = f"更新元数据:总耗时 {total_time:.2f} 秒, 共查询影剧数：{total_items}个，发现重复影剧：{duplicate_items}"
        return total_time, message


    # 获取所有电影的信息
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
    def query_movies_by_tmdbid(self,movies,tmdb_value):

        for movie in movies:
            tmdb_id = movie.get("ProviderIds", {}).get("Tmdb", "")
            if tmdb_value == tmdb_id:
                # self.logger.info(f"电影 '{movie['Name']}' 存在于 Emby 库中，TMDB 值: {tmdb_value}")
                return True;
        
        # self.logger.info(f"没有找到与 TMDB 值 {tmdb_value} 相同的电影。")
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
        except Exception as e:
            self.logger.error(f"发生错误：在处理文件 '{nfo_path}' 时出错，错误信息: {e}")

        return None

