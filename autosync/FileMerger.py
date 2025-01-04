import os
import time
import threading
import logging
import shutil
from utils.logger import setup_logger
from utils.listdir import list_files

class FileMerger:
    def __init__(self, metadata_folder_path: str, video_folder_path: str,enable_115_protect=False, op_interval_sec=0,  logger=None):
        """
        初始化FileMerger类
        :param metadata_folder_path: 包含nfo文件夹路径
        :param video_folder_path: 包含视频文件夹路径
        """
        self.metadata_folder_path = metadata_folder_path
        self.video_folder_path = video_folder_path
        self.enable_115_protect = enable_115_protect
        self.op_interval_sec = op_interval_sec
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger
        
        # 验证文件存在
        if not os.path.exists(metadata_folder_path):
            raise FileNotFoundError(f"文件不存在: {metadata_folder_path}")
        if not os.path.exists(video_folder_path):
            raise FileNotFoundError(f"文件不存在: {video_folder_path}")

    
    def find_matching_video(self, nfo_path: str) -> str:
        """
        查找与nfo文件匹配的视频文件
        :param nfo_path: nfo文件的绝对路径
        :return: 匹配的视频文件路径，如果没找到返回空字符串
        """
        # 获取不带后缀的文件名
        nfo_name = os.path.splitext(os.path.basename(nfo_path))[0]
        
        # 在视频文件列表中查找匹配的文件
        for video_path in self.video_files:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            video_ext = os.path.splitext(video_path)[1].lower()

            # 检查文件名是否匹配且扩展名是.mkv或.ts
            if video_name == nfo_name and video_ext in ['.mkv', '.ts', '.iso', '.mp4', '.avi', '.rmvb', '.wmv', '.m2ts', '.mpg', '.flv', '.mov', '.vob', '.webm', '.divx', '.3gp', '.rm']:
                return video_path
                
        return ""

    def move_video_file(self, video_path: str, nfo_path: str) -> bool:
        """
        将视频文件移动到nfo文件所在目录
        :param video_path: 视频文件路径
        :param nfo_path: nfo文件路径
        :return: 是否移动成功
        """
        try:
            # 获取目标目录（nfo文件所在目录）
            target_dir = os.path.dirname(nfo_path)
            # 构建目标文件路径
            target_path = os.path.join(target_dir, os.path.basename(video_path))
            
            # 检查源文件是否存在
            if not os.path.exists(video_path):
                self.logger.error(f"源视频文件不存在: {video_path}")
                return False
                
            # 检查目标目录是否存在
            if not os.path.exists(target_dir):
                self.logger.error(f"目标目录不存在: {target_dir}")
                return False
            
            # 检查目标文件是否已存在
            if os.path.exists(target_path):
                self.logger.warning(f"目标文件已存在，将被覆盖: {target_path}")
                
            # 移动文件
            shutil.move(video_path, target_path)
            self.logger.info(f"已移动视频文件到: {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"移动文件时出错: {str(e)}")
            return False
    
    def run(self):
        """
        运行同步处理,返回处理时间和消息
        """
        result = {'total_time': 0, 'message': ''}
        
        def run_in_thread():
            self.logger.info("开始处理文件匹配...")
            match_count = 0
            move_count = 0
            start_time = time.time()

            try:
                
                # 遍历文件夹并保存刮削文件夹里的元文件列表
                self.logger.info(f"开始扫描{self.metadata_folder_path}文件夹...")
                file_count, _, metadata_file_output_path = list_files(self.metadata_folder_path, enable_115_protect=self.enable_115_protect, logger=self.logger)
                self.logger.info(f"共发现 {file_count} 个文件")
                if file_count == 0:
                    message = f"元数据文件夹为空: {self.metadata_folder_path}"
                    return
                if metadata_file_output_path:
                    self.logger.info(f"元文件列表已保存到: {metadata_file_output_path}")

                if self.enable_115_protect:
                    time.sleep(self.op_interval_sec)
                
                # 遍历文件夹并保存文件列表
                self.logger.info(f"开始扫描{self.video_folder_path}文件夹...")
                file_count, _, video_files_output_path = list_files(self.video_folder_path, enable_115_protect=self.enable_115_protect, logger=self.logger)
                self.logger.info(f"共发现 {file_count} 个文件")
                if file_count == 0:
                    message = f"视频文件夹为空: {self.video_folder_path}"
                    return
                if video_files_output_path:
                    self.logger.info(f"视频文件列表已保存到: {video_files_output_path}")

                # 读取视频文件列表
                with open(video_files_output_path, 'r', encoding='utf-8') as f:
                    self.video_files = f.readlines()
                # 去除每行末尾的换行符
                self.video_files = [line.strip() for line in self.video_files]
                
                logging.info(f"已加载视频文件列表，共 {len(self.video_files)} 个文件")

                # 读取元文件列表
                with open(metadata_file_output_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        file_path = line.strip()
                        
                        # 检查是否是nfo文件
                        if file_path.lower().endswith('.nfo'):
                            # 查找匹配的视频文件
                            matching_video = self.find_matching_video(file_path)
                            
                            if matching_video:
                                match_count += 1
                                self.logger.info(f"找到匹配:")
                                self.logger.info(f"  NFO: {file_path}")
                                self.logger.info(f"  视频: {matching_video}")
                                
                                # 移动视频文件
                                if self.move_video_file(matching_video, file_path):
                                    move_count += 1
                                logging.info("-" * 50)

                                if self.enable_115_protect:
                                    time.sleep(self.op_interval_sec)  # 防止115服务器检测
                
                message = f"处理完成，共找到 {match_count} 个匹配，成功移动 {move_count} 个文件"
                
            except Exception as e:
                self.logger.error(f"处理过程出错: {str(e)}")
                message = f"处理过程出错: {str(e)}"

            finally:
                end_time = time.time()
                total_time = end_time - start_time
                self.logger.info(message)
                self.logger.info('合并文件结束')
                return

        thread = threading.Thread(target=run_in_thread)
        thread.start()
