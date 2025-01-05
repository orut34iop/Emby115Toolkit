import os
import threading
import time
import queue
import logging
import shutil
from typing import List


class MetadataCopyer:
    def __init__(self, source_folders: List[str], target_folder: str, allowed_extensions, num_threads=1, enable_115_protect=False, op_interval_sec=0, logger=None):
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
        self.enable_115_protect = enable_115_protect
        self.copied_metadatas = 0
        self.existing_links = 0
        self.op_interval_sec = op_interval_sec
        self.file_queue = queue.Queue()
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
                if self.enable_115_protect:
                    self.logger.info(f"线程 {thread_name}: 启动115防封机制,sleep {self.op_interval_sec} 秒")
                    time.sleep(self.op_interval_sec)
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

            if self.enable_115_protect:
                self.logger.info(f"启动115防封机制,sleep {self.op_interval_sec} 秒")
                time.sleep(self.op_interval_sec)

            self.logger.info(f"开始扫描文件夹: {directory}")
            # self.logger.info(f"文件夹根目录:   {root_directory}")
            with os.scandir(directory) as it:
                for entry in it:
                    if entry.is_file() and entry.name.lower().endswith(self.metadata_extensions):
                        yield entry.path, directory, root_directory
                    elif entry.is_dir():
                        yield from scan_directory(entry.path, root_directory)

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
            
            if self.enable_115_protect:
                self.num_threads = 1
                self.logger.info("开启115防封")

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