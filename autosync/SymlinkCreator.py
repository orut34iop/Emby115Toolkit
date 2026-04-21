import os
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
    """
    符号链接/STRM 文件创建器
    """
    def __init__(
        self,
        link_folders=None,
        target_folder=None,
        symlink_mode="symlink",
        thread_count=4,
        enable_replace_path=False,
        original_path='',
        replace_path='',
        only_tvshow_nfo=True,
        allowed_extensions=None,
        source_folders=None,
        num_threads=None,
        symlink_size=0,
        cloud_type=None,
        cloud_root_path=None,
        cloud_url=None,
        logger=None
    ):
        """
        初始化 SymlinkCreator
        支持两种参数风格：
        1. 测试风格: link_folders, target_folder, thread_count, only_tvshow_nfo
        2. GUI风格: source_folders, allowed_extensions, num_threads
        """
        # 兼容两种参数风格
        self.link_folders = link_folders or source_folders or []
        self.source_folders = self.link_folders  # 兼容旧代码
        self.target_folder = target_folder
        self.symlink_mode = symlink_mode
        self.thread_count = thread_count
        self.num_threads = num_threads or thread_count  # 兼容旧代码
        self.enable_replace_path = enable_replace_path
        self.original_path = original_path
        self.replace_path = replace_path
        self.only_tvshow_nfo = only_tvshow_nfo
        self.allowed_extensions = allowed_extensions or ('.mp4', '.mkv', '.avi', '.ts')
        self.symlink_size = symlink_size
        self.cloud_type = cloud_type
        self.cloud_root_path = cloud_root_path
        self.cloud_url = cloud_url
        
        self.logger = logger or logging.getLogger(__name__)
        
        # 计数器
        self.total_files = 0
        self.processed_files = 0
        self.success_count = 0
        self.error_count = 0
        self.created_links = 0
        self.existing_links = 0
        
        # 停止标志
        self.stop_flag = threading.Event()
        
        # 队列（用于旧版多线程模式）
        self.file_queue = queue.Queue()
        self._counter_lock = threading.Lock()
        
        # 验证 symlink_mode
        if symlink_mode not in ('symlink', 'strm'):
            raise ValueError(f"无效的 symlink_mode: {symlink_mode}，必须是 'symlink' 或 'strm'")
        
        self.symlink_name = symlink_name_dict.get(self.symlink_mode, '链接')

    def scan(self, folder_path: str) -> list:
        """
        扫描文件夹，返回文件列表
        :param folder_path: 要扫描的文件夹路径
        :return: 文件列表，每个元素是包含 name, path, is_symlink 的字典
        """
        result = []
        if not os.path.exists(folder_path):
            return result
            
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                # 跳过符号链接
                if os.path.islink(file_path):
                    continue
                rel_path = os.path.relpath(file_path, folder_path)
                result.append({
                    'name': filename,
                    'path': file_path,
                    'rel_path': rel_path,
                    'stem': os.path.splitext(filename)[0],
                    'ext': os.path.splitext(filename)[1].lower()
                })
        return result

    def create(self, files: list, target_folder: str) -> None:
        """
        创建符号链接或 strm 文件
        :param files: 源文件列表
        :param target_folder: 目标文件夹
        """
        for file_info in files:
            if self.stop_flag.is_set():
                self.logger.info("创建操作已停止")
                return
            
            source_file = file_info['path']
            rel_path = file_info['rel_path']
            
            # 计算目标路径
            target_file = os.path.join(target_folder, rel_path)
            target_dir = os.path.dirname(target_file)
            os.makedirs(target_dir, exist_ok=True)
            
            # 处理 only_tvshow_nfo 选项
            if file_info['name'].lower().endswith('.nfo'):
                if self.only_tvshow_nfo and file_info['name'].lower() != 'tvshow.nfo':
                    continue
            
            if self.symlink_mode == 'symlink':
                self._create_symlink(source_file, target_file)
            elif self.symlink_mode == 'strm':
                self._create_strm(source_file, target_file)

    def _create_symlink(self, src: str, dst: str) -> None:
        """创建符号链接"""
        try:
            # 路径替换
            link_src = src
            if self.enable_replace_path and self.original_path and self.replace_path:
                link_src = src.replace(self.original_path, self.replace_path)
            
            if os.path.exists(dst):
                self.existing_links += 1
                return
            
            os.symlink(link_src, dst)
            self.created_links += 1
            self.success_count += 1
            self.processed_files += 1
            self.logger.info(f"创建软链接: {dst} -> {link_src}")
        except Exception as e:
            self.error_count += 1
            self.processed_files += 1
            self.logger.error(f"创建软链接失败: {e}")

    def _create_strm(self, src: str, dst: str) -> None:
        """创建 strm 文件"""
        try:
            # 路径替换
            content = src
            if self.enable_replace_path and self.original_path and self.replace_path:
                content = src.replace(self.original_path, self.replace_path)
            
            # 处理云盘模式
            if self.cloud_type:
                content = content.replace("\\", "/")
                if self.cloud_root_path:
                    content = content.replace(self.cloud_root_path, "")
                content = urllib.parse.quote(content, safe="")
                if str(self.cloud_type) == "cd2":
                    content = f"http://{self.cloud_url}/static/http/{self.cloud_url}/False/{content}"
                elif str(self.cloud_type) == "alist":
                    content = f"http://{self.cloud_url}/d/{content}"
            
            strm_path = dst
            if not dst.lower().endswith('.strm'):
                strm_path = os.path.splitext(dst)[0] + '.strm'
            
            if os.path.exists(strm_path):
                self.existing_links += 1
                return
            
            with open(strm_path, 'w') as f:
                f.write(content)
            self.created_links += 1
            self.success_count += 1
            self.processed_files += 1
            self.logger.info(f"创建 strm 文件: {strm_path}")
        except Exception as e:
            self.error_count += 1
            self.processed_files += 1
            self.logger.error(f"创建 strm 文件失败: {e}")

    def run(self, callback=None):
        """
        运行完整的创建流程
        :param callback: 回调函数，接收消息字符串
        """
        def send_message(msg):
            self.logger.info(msg)
            if callback:
                callback(msg)
        
        if self.stop_flag.is_set():
            send_message("操作已停止")
            return
        
        # 如果没有指定 link_folders，无法运行
        if not self.link_folders:
            send_message("错误: 未指定源文件夹")
            return
        
        total_created = 0
        total_existing = 0
        
        for source_folder in self.link_folders:
            if self.stop_flag.is_set():
                send_message("操作已停止")
                return
            
            if not os.path.exists(source_folder):
                self.logger.warning(f"源文件夹不存在: {source_folder}")
                continue
            
            send_message(f"扫描源文件夹: {source_folder}")
            files = self.scan(source_folder)
            self.total_files += len(files)
            send_message(f"发现 {len(files)} 个文件")
            
            if self.stop_flag.is_set():
                send_message("操作已停止")
                return
            
            send_message("开始创建链接...")
            self.create(files, self.target_folder)
            total_created += self.created_links
            total_existing += self.existing_links
        
        message = (
            f"创建{self.symlink_name}完成\n"
            f"共创建: {self.success_count}\n"
            f"已存在: {self.existing_links}\n"
            f"失败: {self.error_count}"
        )
        send_message(message)

    # ========== 兼容旧版 GUI 接口 ==========
    
    def create_symlink(self, src, dst, thread_name):
        """兼容旧接口"""
        self._create_symlink(src, dst)

    def check_strm(self, strm_path):
        """兼容旧接口"""
        try:
            with open(strm_path, "r") as f:
                strm_link = f.read().strip()
            strm_link = urllib.parse.quote(strm_link)
            file_extension = os.path.splitext(strm_link)[1]
            strm_media_path = strm_path.replace(".txt", "").replace(".strm", file_extension)
            source_file = strm_media_path.replace(self.target_folder, str(self.source_folders[0]) if self.source_folders else "")
            return os.path.exists(source_file)
        except:
            return False

    def create_strm_file(self, source_dir, target_dir, source_file, cloud_type, cloud_root_path, cloud_url, thread_name):
        """兼容旧接口"""
        try:
            target_file = source_file.replace(source_dir, target_dir)
            self._create_strm(source_file, target_file)
        except Exception as e:
            self.logger.error(f"创建strm文件失败:{source_file} - {e}")

    def create_and_print_link(self, thread_name):
        """兼容旧版多线程接口"""
        while True:
            item = self.file_queue.get()
            if item is None:
                break
            
            source_file, source_folder = item
            relative_path = os.path.relpath(source_file, os.path.dirname(source_folder))
            target_file = os.path.join(self.target_folder, relative_path)
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            
            if self.symlink_mode == "symlink":
                self.create_symlink(source_file, target_file, thread_name)
            elif self.symlink_mode == "strm":
                self.create_strm_file(
                    source_folder,
                    self.target_folder,
                    source_file,
                    self.cloud_type,
                    self.cloud_root_path,
                    self.cloud_url,
                    thread_name,
                )
            
            self.file_queue.task_done()

    def get_source_files(self):
        """兼容旧版接口"""
        for source_folder in self.source_folders:
            if not os.path.exists(source_folder):
                self.logger.warning(f"源文件夹不存在: {source_folder}")
                continue
            self.logger.info(f"扫描源文件夹: {source_folder}")
            for dp, dn, filenames in os.walk(source_folder):
                for f in filenames:
                    source_file = os.path.join(dp, f)
                    if source_file.endswith(self.allowed_extensions):
                        self.logger.info(f"发现文件: {source_file}")
                        yield source_file, source_folder

    def _run_legacy(self, callback):
        """兼容旧版运行方式（多线程队列模式）"""
        start_time = time.time()
        self.logger.info(f"开始更新{self.symlink_name}...")
        os.makedirs(self.target_folder, exist_ok=True)
        
        threads = []
        for i in range(self.num_threads):
            thread_name = f"Thread-{i + 1}"
            thread = threading.Thread(target=self.create_and_print_link, args=(thread_name,))
            threads.append(thread)
            thread.start()
        
        for source_file, source_folder in self.get_source_files():
            self.file_queue.put((source_file, source_folder))
        
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
