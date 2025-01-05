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

class SymlinkCreator:
    def __init__(
        self,
        source_folders,  # 修改为接收文件夹列表
        target_folder,
        allowed_extensions,
        symlink_mode="symlink",
        symlink_size=0,
        cloud_type=None,
        cloud_root_path=None,
        cloud_url=None,
        num_threads=8,
        enable_115_protect=False,
        op_interval_sec = 0,
        logger=None  # 添加logger参数
    ):
        self.source_folders = source_folders  # 改为保存文件夹列表
        self.target_folder = target_folder
        self.allowed_extensions = allowed_extensions
        self.symlink_mode = symlink_mode
        self.symlink_size = symlink_size
        self.cloud_type = cloud_type
        self.cloud_root_path = cloud_root_path
        self.cloud_url = cloud_url
        self.num_threads = num_threads
        self.enable_115_protect = enable_115_protect
        self.created_links = 0
        self.existing_links = 0
        self.symlink_name = symlink_name_dict.get(self.symlink_mode)
        self.file_queue = queue.Queue()
        self.op_interval_sec = op_interval_sec
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger

    def create_symlink(self, src, dst, thread_name):
        try:
            if os.path.exists(dst):
                self.existing_links += 1
                self.logger.info(f"线程 {thread_name}: {self.symlink_name}已存在，跳过:{dst}")
                return
            os.symlink(src, dst)

            self.created_links += 1
            self.logger.info(f"线程 {thread_name}: {src} => {dst}")
        except Exception as e:
            self.logger.error(f"{self.symlink_name}创建出错:{e}")
		
        if self.enable_115_protect:
            self.logger.info(f"线程 {thread_name}: 启动115防封机制,sleep {self.op_interval_sec} 秒")
            time.sleep(self.op_interval_sec)

    def check_strm(self, strm_path):
        with open(strm_path, "r") as f:
            strm_link = f.read().strip()
        strm_link = urllib.parse.quote(strm_link)
        file_extension = os.path.splitext(strm_link)[1]
        strm_media_path = strm_path.replace(".txt", "").replace(".strm", file_extension)
        source_file = strm_media_path.replace(self.target_folder, self.source_folders)
        if os.path.exists(source_file):
            return True
        else:
            return False

    def create_strm_file(
        self,
        source_dir: str,
        target_dir: str,
        source_file: str,
        cloud_type: str,
        cloud_root_path: str,
        cloud_url: str,
        thread_name: str,
    ):
        try:
            # 获取视频文件名和目录
            target_file = source_file.replace(source_dir, target_dir)
            video_name = Path(target_file).name
            # 获取视频目录
            dest_path = Path(target_file).parent

            if not dest_path.exists():
                os.makedirs(str(dest_path), exist_ok=True)

            # 构造.strm文件路径
            strm_path = os.path.join(
                dest_path, f"{os.path.splitext(video_name)[0]}.strm"
            )
            if os.path.exists(strm_path):
                if self.check_strm(strm_path):
                    self.existing_links += 1
                    return
                else:
                    os.remove(strm_path)
                    self.logger.info(f"发现无效strm文件,已删除::: {strm_path}")
                    self.logger.info(f"开始创建新的strm文件::: {strm_path}")
            # 云盘模式
            if cloud_type:
                # 替换路径中的\为/
                target_file = source_file.replace("\\", "/")
                target_file = target_file.replace(cloud_root_path, "")
                # 对盘符之后的所有内容进行url转码
                target_file = urllib.parse.quote(target_file, safe="")
                if str(cloud_type) == "cd2":
                    # 将路径的开头盘符"/mnt/user/downloads"替换为"http://localhost:19798/static/http/localhost:19798/False/"
                    target_file = f"http://{cloud_url}/static/http/{cloud_url}/False/{target_file}"
                elif str(cloud_type) == "alist":
                    target_file = f"http://{cloud_url}/d/{target_file}"
                else:
                    self.logger.error(f"云盘类型 {cloud_type} 错误")
                    return

            # 写入.strm文件
            with open(strm_path, "w") as f:
                f.write(target_file)
            self.created_links += 1
            self.logger.info(f"线程 {thread_name}::: {source_file} => {strm_path}")
        except Exception as e:
            self.logger.error(f"创建strm文件失败:{source_file}")
            self.logger.error(f"error:{e}")

    def create_and_print_link(self, thread_name):
        while True:
            item = self.file_queue.get()
            if item is None:
                break
                
            source_file, source_folder, root_directory = item
            relative_path = os.path.relpath(source_file, os.path.dirname(root_directory))
            target_file = os.path.join(self.target_folder, relative_path)
            
            # 确保目标文件夹存在
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            
            if self.symlink_mode == "symlink":
                self.create_symlink(source_file, target_file, thread_name)
            elif self.symlink_mode == "strm":
                self.create_strm_file(
                    source_folder,  # 使用当前源文件夹
                    self.target_folder,
                    source_file,
                    self.cloud_type,
                    self.cloud_root_path,
                    self.cloud_url,
                    thread_name,
                )
            else:
                self.logger.error(f"symlink_mode: {self.symlink_mode}不是支持的模式,程序即将退出")
                sys.exit(0)
                
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
            self.logger.info(f"文件夹根目录:   {root_directory}")
            with os.scandir(directory) as it:
                for entry in it:
                    if entry.is_file() and entry.name.lower().endswith(self.allowed_extensions):
                        self.logger.info(f"发现文件: {entry.path}")
                        yield entry.path, directory, root_directory
                    elif entry.is_dir():
                        yield from scan_directory(entry.path, root_directory)

        for source_folder in self.source_folders:
            if not os.path.exists(source_folder):
                self.logger.warning(f"源文件夹不存在: {source_folder}")
                continue

            self.logger.info(f"扫描源文件夹: {source_folder}")
            root_directory = source_folder
            yield from scan_directory(source_folder,root_directory)

    def run(self,callback):
        def run_symlink_create_check():
            start_time = time.time()
            self.logger.info(f"开始更新{self.symlink_name}...")

            # 确保目标文件夹存在
            os.makedirs(self.target_folder, exist_ok=True)

            if self.enable_115_protect:
                self.num_threads = 1

            threads = []
            for i in range(self.num_threads):
                thread_name = f"Thread-{i + 1}"
                thread = threading.Thread(target=self.create_and_print_link, args=(thread_name,))
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
            message = (
                f"创建{self.symlink_name}完成\n"
                f"总耗时: {total_time:.2f} 秒\n"
                f"共处理{self.symlink_name}数：{self.created_links + self.existing_links}\n"
                f"共创建{self.symlink_name}数：{self.created_links}\n"
                f"共跳过{self.symlink_name}数：{self.existing_links}"
            )
            if callback:
                callback(message)
            return total_time, message
        
        thread = threading.Thread(target=run_symlink_create_check)
        thread.start()
