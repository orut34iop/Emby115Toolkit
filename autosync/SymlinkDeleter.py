import os
import threading
import time
import queue
import sys
from pathlib import Path
import urllib.parse
import shutil
import logging
from utils.logger import setup_logger

symlink_name_dict = {"symlink":"软链接","strm":"strm文件"}

class SymlinkDeleter:
    def __init__(
        self,
        target_folder,
        logger=None  # 添加logger参数
    ):
        self.target_folder = target_folder
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger
        self.symlink_name = symlink_name_dict.get("symlink")

    def run(self):
        deleted_links=0
        total_links=0
        start_time = time.time()
        self.logger.info(f"开始删除{self.symlink_name}...")

        # 遍历目录中的所有文件
        for root, _, files in os.walk(self.target_folder):
            for file in files:
                file_path = os.path.join(root, file)
                # 检查是否为符号链接
                if os.path.islink(file_path):
                    try:
                        total_links += 1
                        # 删除符号链接
                        os.unlink(file_path)
                        deleted_links += 1
                        self.logger.info(f"已删除符号链接：{file_path}")
                    except PermissionError:
                        self.logger.error(f"错误：无法删除符号链接 {file_path}，权限不足。")
                    except Exception as e:
                        self.logger.error(f"错误：删除符号链接 {file_path} 时发生错误：{e}")



        end_time = time.time()
        total_time = end_time - start_time
        message = f"创建{self.symlink_name}:总耗时 {total_time:.2f} 秒, 共处理{self.symlink_name}数：{total_links}个，共删除{self.symlink_name}数：{deleted_links}，共跳过{self.symlink_name}数：{total_links - deleted_links}"
        self.logger.info(f"完成::: 更新{self.symlink_name}")
        self.logger.info(message)
        return total_time, message
