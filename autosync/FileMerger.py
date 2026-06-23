import os
import os
import time
import threading
import logging
import shutil
from utils.logger import setup_logger
from utils.listdir import list_files

class FileMerger:
    """
    文件合并器 - 将刮削文件夹中的元数据文件合并到视频文件夹中
    """
    def __init__(self, scrap_folder: str, target_folder: str, thread_count=4, logger=None):
        """
        初始化FileMerger类
        :param scrap_folder: 刮削文件夹路径（包含nfo等元数据文件）
        :param target_folder: 视频文件夹路径
        :param thread_count: 线程数（默认4）
        :param logger: 日志记录器
        """
        self.scrap_folder = scrap_folder
        self.target_folder = target_folder
        self.thread_count = thread_count
        self.logger = logger or logging.getLogger(__name__)
        
        # 计数器
        self.total_files = 0
        self.processed_files = 0
        self.success_count = 0
        self.error_count = 0
        
        # 停止标志
        self.stop_flag = threading.Event()
        
        # 验证文件夹存在
        if not os.path.exists(scrap_folder):
            raise FileNotFoundError(f"文件夹不存在: {scrap_folder}")
        if not os.path.exists(target_folder):
            raise FileNotFoundError(f"文件夹不存在: {target_folder}")

    def scan(self, folder_path: str) -> list:
        """
        扫描文件夹，返回文件列表
        :param folder_path: 要扫描的文件夹路径
        :return: 文件列表，每个元素是包含 name 和 path 的字典
        """
        result = []
        if not os.path.exists(folder_path):
            return result
            
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, folder_path)
                result.append({
                    'name': filename,
                    'path': file_path,
                    'rel_path': rel_path,
                    'stem': os.path.splitext(filename)[0]
                })
        return result

    def match(self, scrap_files: list, target_files: list) -> list:
        """
        匹配刮削文件和目标视频文件
        :param scrap_files: 刮削文件夹中的文件列表
        :param target_files: 目标文件夹中的文件列表
        :return: 匹配结果列表，每个元素是 (scrap_file, target_file) 元组
        """
        matches = []
        
        # 获取目标文件夹中的视频文件stem集合
        video_stems = set()
        for target_file in target_files:
            ext = os.path.splitext(target_file['name'])[1].lower()
            if ext in ['.mp4', '.mkv', '.avi', '.ts', '.iso', '.rmvb', '.wmv', 
                       '.m2ts', '.mpg', '.flv', '.mov', '.vob', '.webm', 
                       '.divx', '.3gp', '.rm', '.m4v']:
                video_stems.add(target_file['stem'])
        
        # 为每个刮削文件查找匹配的视频文件
        for scrap_file in scrap_files:
            scrap_stem = scrap_file['stem']
            if scrap_stem in video_stems:
                # 找到匹配的视频文件
                for target_file in target_files:
                    if target_file['stem'] == scrap_stem:
                        matches.append((scrap_file, target_file))
                        break
        
        return matches

    def merge(self, matches: list) -> None:
        """
        执行文件合并（移动刮削文件到目标文件夹）
        :param matches: 匹配结果列表
        """
        for scrap_file, target_file in matches:
            if self.stop_flag.is_set():
                self.logger.info("合并操作已停止")
                return
            
            # 计算目标路径（保持相对目录结构）
            target_dir = os.path.dirname(target_file['path'])
            dest_path = os.path.join(target_dir, scrap_file['name'])
            
            # 如果目标文件已存在，跳过
            if os.path.exists(dest_path):
                self.logger.warning(f"目标文件已存在，跳过: {dest_path}")
                self.processed_files += 1
                continue
            
            try:
                # 移动文件
                shutil.move(scrap_file['path'], dest_path)
                self.logger.info(f"已移动: {scrap_file['path']} -> {dest_path}")
                self.success_count += 1
                self.processed_files += 1
            except Exception as e:
                self.logger.error(f"移动文件失败: {str(e)}")
                self.error_count += 1
                self.processed_files += 1

    def run(self, callback=None):
        """
        运行完整的合并流程
        :param callback: 回调函数，接收消息字符串
        """
        def send_message(msg):
            self.logger.info(msg)
            if callback:
                callback(msg)
        
        if self.stop_flag.is_set():
            send_message("操作已停止")
            return
        
        send_message(f"开始扫描刮削文件夹: {self.scrap_folder}")
        scrap_files = self.scan(self.scrap_folder)
        
        send_message(f"开始扫描目标文件夹: {self.target_folder}")
        target_files = self.scan(self.target_folder)
        
        self.total_files = len(scrap_files)
        send_message(f"发现 {len(scrap_files)} 个刮削文件, {len(target_files)} 个目标文件")
        
        if self.stop_flag.is_set():
            send_message("操作已停止")
            return
        
        send_message("开始匹配文件...")
        matches = self.match(scrap_files, target_files)
        send_message(f"找到 {len(matches)} 个匹配")
        
        if self.stop_flag.is_set():
            send_message("操作已停止")
            return
        
        send_message("开始合并文件...")
        self.merge(matches)
        
        send_message(f"合并完成: 成功 {self.success_count}, 失败 {self.error_count}, 总计 {self.processed_files}")

    # 兼容旧接口
    def find_matching_video(self, nfo_path: str) -> str:
        """
        查找与nfo文件匹配的视频文件（兼容旧接口）
        """
        nfo_name = os.path.splitext(os.path.basename(nfo_path))[0]
        
        # 扫描目标文件夹获取视频文件
        target_files = self.scan(self.target_folder)
        for file_info in target_files:
            video_name = os.path.splitext(file_info['name'])[0]
            video_ext = os.path.splitext(file_info['name'])[1].lower()
            if video_name == nfo_name and video_ext in ['.mkv', '.ts', '.iso', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv', '.mov', '.vob', '.webm', '.divx', '.3gp', '.rm', '.m4v']:
                return file_info['path']
        return ""

    def move_video_file(self, video_path: str, nfo_path: str) -> bool:
        """
        将视频文件移动到nfo文件所在目录（兼容旧接口）
        """
        try:
            target_dir = os.path.dirname(nfo_path)
            target_path = os.path.join(target_dir, os.path.basename(video_path))
            
            if not os.path.exists(video_path):
                self.logger.error(f"源视频文件不存在: {video_path}")
                return False
            
            if not os.path.exists(target_dir):
                self.logger.error(f"目标目录不存在: {target_dir}")
                return False
            
            if os.path.exists(target_path):
                self.logger.warning(f"目标文件已存在，将被覆盖: {target_path}")
            
            shutil.move(video_path, target_path)
            self.logger.info(f"已移动视频文件到: {target_path}")
            return True
        except Exception as e:
            self.logger.error(f"移动文件时出错: {str(e)}")
            return False
