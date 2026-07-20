import logging
import os
import queue
import shutil
import threading
import time
from typing import List


class MetadataCopier:
    def __init__(
        self,
        source_folders: List[str],
        target_folder: str,
        allowed_extensions,
        thread_count=1,
        only_tvshow_nfo=False,
        overwrite_existing=False,
        logger=None,
    ):
        """
        初始化MetadataCopier
        Args:
            source_folders: 源文件夹路径列表
            target_folder: 目标文件夹路径
            allowed_extensions: 允许的文件扩展名
            thread_count: 线程数
            overwrite_existing: 已存在元数据文件时是否覆盖
            logger: 日志记录器
        """
        self.source_folders = source_folders
        self.target_folder = target_folder
        self.metadata_extensions = allowed_extensions
        self.thread_count = thread_count
        self.copied_metadatas = 0
        self.existing_links = 0
        self.file_queue = queue.Queue()
        self.only_tvshow_nfo = only_tvshow_nfo
        self.overwrite_existing = overwrite_existing
        self.overwritten_metadatas = 0
        self.logger = logger or logging.getLogger(__name__)
        self._counter_lock = threading.Lock()  # 线程锁保护计数器
        self.stop_flag = threading.Event()
        self.progress_callback = None
        self.total_files = 0
        self.processed_files = 0

    @staticmethod
    def _report_progress(callback, current, total, message):
        if callback is None:
            return
        if total is not None and total > 0:
            callback({'current': current, 'total': total, 'message': message})
        else:
            callback({'message': message})

    def request_stop(self):
        self.stop_flag.set()
        self.logger.info("已请求停止元数据下载")

    def _relative_target_path(self, source_file, root_directory):
        """计算目标相对路径，多源导出时保留源文件夹名称。"""
        relative_path = os.path.relpath(source_file, root_directory)
        if len(self.source_folders) <= 1:
            return relative_path

        source_name = os.path.basename(os.path.normpath(root_directory))
        if not source_name:
            return relative_path
        return os.path.join(source_name, relative_path)

    def copy_metadata(self, source, target_file, thread_name):
        try:
            if os.path.exists(target_file):
                if self.overwrite_existing:
                    os.makedirs(os.path.dirname(target_file), exist_ok=True)
                    shutil.copy2(source, target_file)
                    self.logger.info(f"线程 {thread_name} 覆盖元数据: {source} 到 {target_file}")
                    with self._counter_lock:
                        self.overwritten_metadatas += 1
                else:
                    self.logger.info(f"线程 {thread_name} 元数据已存在，跳过:{target_file}")
                    with self._counter_lock:
                        self.existing_links += 1
            else:
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                shutil.copy2(source, target_file)
                self.logger.info(f"线程 {thread_name}: {source} 到 {target_file}")
                with self._counter_lock:
                    self.copied_metadatas += 1
        except Exception as e:
            self.logger.error(f"元数据复制出错:{e}")

    def start_to_copy_metadata(self, thread_name):
        while True:
            if self.stop_flag.is_set():
                break

            item = self.file_queue.get()
            if item is None:
                break

            source_file, source_folder, root_directory = item
            relative_path = self._relative_target_path(source_file, root_directory)
            target_file = os.path.join(self.target_folder, relative_path)

            # 确保目标文件夹存在，如果不存在则创建
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            self.copy_metadata(source_file, target_file, thread_name)
            with self._counter_lock:
                self.processed_files += 1
                processed_files = self.processed_files
                total_files = self.total_files
                progress_callback = self.progress_callback
            if progress_callback:
                self._report_progress(
                    progress_callback,
                    processed_files,
                    total_files,
                    f"已处理 {processed_files}/{total_files} 文件（线程 {thread_name}）",
                )
            self.file_queue.task_done()

    def get_source_files(self):
        """遍历所有源文件夹获取符合条件的文件"""
        visited_dirs = set()  # 用于检测循环符号链接

        def scan_directory(directory, root_directory=None):
            if self.stop_flag.is_set():
                return iter([])

            if root_directory is None:
                self.logger.error("scan_directory root_directory 值未设置")
                return iter([])

            # 获取目录的绝对路径和真实路径（用于检测符号链接）
            real_path = os.path.realpath(directory)
            if real_path in visited_dirs:
                self.logger.warning(f"检测到循环符号链接或重复目录，跳过: {directory}")
                return iter([])
            visited_dirs.add(real_path)

            self.logger.info(f"开始扫描文件夹: {directory}")

            files = []  # 用于存储文件条目
            directories = []  # 用于存储目录条目

            try:
                with os.scandir(directory) as it:
                    for entry in it:
                        if entry.is_file():
                            files.append(entry)
                        elif entry.is_dir(follow_symlinks=False):  # 不跟随符号链接
                            directories.append(entry)
            except OSError as e:
                self.logger.error(f"访问目录时发生错误: {e}")

            # 先处理文件
            for file_entry in files:
                if self.stop_flag.is_set():
                    return
                if self.only_tvshow_nfo and (file_entry.name.lower() == "tvshow.nfo"):
                    self.logger.info(f"发现文件: {file_entry.path}")
                    yield file_entry.path, directory, root_directory
                    return  # 如果找到 tvshow.nfo，直接返回,不需要再检查其他同一级的文件或文件夹
                elif (not self.only_tvshow_nfo) and (file_entry.name.lower().endswith(self.metadata_extensions)):
                    yield file_entry.path, directory, root_directory
            # 再处理目录
            for dir_entry in directories:
                if self.stop_flag.is_set():
                    return
                yield from scan_directory(dir_entry.path, root_directory)

        for source_folder in self.source_folders:
            if self.stop_flag.is_set():
                self.logger.info("元数据扫描已停止")
                return

            if not os.path.exists(source_folder):
                self.logger.warning(f"源文件夹不存在: {source_folder}")
                continue

            self.logger.info(f"扫描源文件夹: {source_folder}")
            visited_dirs.clear()  # 每个源文件夹清空visited集合
            root_directory = source_folder
            yield from scan_directory(source_folder, root_directory)

    def run(self, callback=None):
        def run_meta_copy_check():
            try:
                start_time = time.time()
                self.logger.info("开始更新元数据...")

                # 确保目标文件夹存在
                os.makedirs(self.target_folder, exist_ok=True)
                source_files = list(self.get_source_files())
                self.total_files = len(source_files)
                self.processed_files = 0
                self.progress_callback = callback

                if callback:
                    self._report_progress(callback, 0, max(self.total_files, 1), f"准备下载元数据，共 {self.total_files} 个文件")
                if self.total_files == 0:
                    message = "没有可下载的元数据文件"
                    self.logger.info(message)
                    if callback:
                        callback(message)
                    return message

                threads = []
                for i in range(self.thread_count):
                    thread_name = f"Thread-{i + 1}"
                    thread = threading.Thread(target=self.start_to_copy_metadata, args=(thread_name,))
                    threads.append(thread)
                    thread.start()

                # 添加所有源文件到队列
                for source_file, source_folder, root_directory in source_files:
                    if self.stop_flag.is_set():
                        break
                    self.file_queue.put((source_file, source_folder, root_directory))

                # 添加停止任务
                for _ in range(self.thread_count):
                    self.file_queue.put(None)

                for thread in threads:
                    thread.join()

                end_time = time.time()
                total_time = end_time - start_time
                title = "下载元数据已停止" if self.stop_flag.is_set() else "下载元数据完成"
                message = (
                    f"{title}\n"
                    f"总耗时: {total_time:.2f} 秒\n"
                    f"处理元数据总数: {self.copied_metadatas + self.overwritten_metadatas + self.existing_links}\n"
                    f"新复制元数据数: {self.copied_metadatas}\n"
                    f"覆盖元数据数: {self.overwritten_metadatas}\n"
                    f"跳过元数据数: {self.existing_links}"
                )

                if callback:
                    callback(message)

                return message
            except Exception as e:
                self.logger.exception(f"下载元数据执行异常: {e}")
            finally:
                self.progress_callback = None

        thread = threading.Thread(target=run_meta_copy_check, daemon=True)
        thread.start()
        return thread
