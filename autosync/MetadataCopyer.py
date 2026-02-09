import os
import threading
import time
import queue
import logging
import shutil
from typing import List


class MetadataCopyer:
    def __init__(self, source_folders: List[str], target_folder: str, allowed_extensions, num_threads=1, only_tvshow_nfo=False, logger=None):
        """
        初始化MetadataCopyer
        Args:
            source_folders: 源文件夹路径列表
            target_folder: 目标文件夹路径
            allowed_extensions: 允许的文件扩展名
            num_threads: 线程数
            logger: 日志记录器
        """
        self.source_folders = source_folders
        self.target_folder = target_folder
        self.metadata_extensions = allowed_extensions
        self.num_threads = num_threads
        self.copied_metadatas = 0
        self.existing_links = 0
        self.file_queue = queue.Queue()
        self.only_tvshow_nfo = only_tvshow_nfo
        self.logger = logger or logging.getLogger(__name__)

    def copy_metadata(self, source, target_file, thread_name):
        try:
            if os.path.exists(target_file):
                self.logger.info(f"线程 {thread_name} 元数据已存在，跳过:{target_file}")
                self.existing_links += 1
            else:
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                shutil.copy2(source, target_file)
                self.logger.info(f"线程 {thread_name}: {source} 到 {target_file}")
                self.copied_metadatas += 1
        except Exception as e:
            self.logger.error(f"元数据复制出错:{e}")

    def start_to_copy_metadata(self, thread_name):
        while True:
            item = self.file_queue.get()
            if item is None:
                break

            source_file, source_folder, root_directory = item
            relative_path = os.path.relpath(source_file, os.path.dirname(root_directory))
            target_file = os.path.join(self.target_folder, relative_path)
            
            # 确保目标文件夹存在，如果不存在则创建
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            self.copy_metadata(source_file, target_file, thread_name)
            self.file_queue.task_done()

    def get_source_files(self):
        """遍历所有源文件夹获取符合条件的文件"""
        def scan_directory(directory,root_directory=None):
            if root_directory is None:
                self.logger.error("scan_directory root_directory 值未设置")
                return iter([])

            self.logger.info(f"开始扫描文件夹: {directory}")

            files = []  # 用于存储文件条目
            directories = []  # 用于存储目录条目

            try:
                with os.scandir(directory) as it:
                    for entry in it:
                        if entry.is_file():
                            files.append(entry)
                        elif entry.is_dir():
                            directories.append(entry)
            except OSError as e:
                self.logger.error(f"访问目录时发生错误: {e}")
            
            # 先处理文件
            for file_entry in files:
                if self.only_tvshow_nfo and (file_entry.name.lower() == "tvshow.nfo"):
                    self.logger.info(f"发现文件: {file_entry.path}")
                    yield file_entry.path, directory, root_directory
                    return  # 如果找到 tvshow.nfo，直接返回,不需要再检查其他同一级的文件或文件夹
                elif (not self.only_tvshow_nfo) and (file_entry.name.lower().endswith(self.metadata_extensions)):
                    yield file_entry.path, directory, root_directory
            # 再处理目录
            for dir_entry in directories:
                yield from scan_directory(dir_entry.path, root_directory)

        for source_folder in self.source_folders:
            if not os.path.exists(source_folder):
                self.logger.warning(f"源文件夹不存在: {source_folder}")
                continue

            self.logger.info(f"扫描源文件夹: {source_folder}")
            root_directory = source_folder
            yield from scan_directory(source_folder, root_directory)

    def run(self,callback):
        def run_meta_copy_check():
            start_time = time.time()
            self.logger.info("开始更新元数据...")
            
            # 确保目标文件夹存在
            os.makedirs(self.target_folder, exist_ok=True)
            


            threads = []
            for i in range(self.num_threads):
                thread_name = f"Thread-{i + 1}"
                thread = threading.Thread(target=self.start_to_copy_metadata, args=(thread_name,))
                threads.append(thread)
                thread.start()

            # 添加所有源文件到队列
            for source_file, source_folder, root_directory in self.get_source_files():
                self.file_queue.put((source_file, source_folder, root_directory))

            # 添加停止任务
            for _ in range(self.num_threads):
                self.file_queue.put(None)

            for thread in threads:
                thread.join()

            end_time = time.time()
            total_time = end_time - start_time
            message = (f"下载元数据完成\n"
                    f"总耗时: {total_time:.2f} 秒\n"
                    f"处理元数据总数: {self.copied_metadatas + self.existing_links}\n"
                    f"新复制元数据数: {self.copied_metadatas}\n"
                    f"跳过元数据数: {self.existing_links}")
            
            if callback:
                callback(message)

            return message

        thread = threading.Thread(target=run_meta_copy_check)
        thread.start()