import logging
import os
import shutil
import threading


class FileMerger:
    """
    文件合并器 - 将元数据文件夹中的文件合并到视频文件夹中
    """

    def __init__(self, metadata_folder: str, target_folder: str, thread_count=4, logger=None):
        """
        初始化FileMerger类
        :param metadata_folder: 元数据文件夹路径（包含 nfo 等元数据文件）
        :param target_folder: 视频文件夹路径
        :param thread_count: 线程数（默认4）
        :param logger: 日志记录器
        """
        self.metadata_folder = metadata_folder
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
        if not os.path.exists(metadata_folder):
            raise FileNotFoundError(f"文件夹不存在: {metadata_folder}")
        if not os.path.exists(target_folder):
            raise FileNotFoundError(f"文件夹不存在: {target_folder}")

    @staticmethod
    def _report_progress(callback, current, total, message):
        if callback is None:
            return

        if total is not None and total > 0:
            callback({'current': current, 'total': total, 'message': message})
        else:
            callback({'message': message})

    def scan(self, folder_path: str, callback=None) -> list:
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
                result.append(
                    {'name': filename, 'path': file_path, 'rel_path': rel_path, 'stem': os.path.splitext(filename)[0]}
                )
            self._report_progress(
                callback,
                len(result),
                None,
                f"扫描 {folder_path}：已找到 {len(result)} 个候选文件",
            )
        return result

    def match(self, metadata_files: list, target_files: list) -> list:
        """
        匹配元数据文件和目标视频文件
        :param metadata_files: 元数据文件夹中的文件列表
        :param target_files: 目标文件夹中的文件列表
        :return: 匹配结果列表，每个元素是 (metadata_file, target_file) 元组
        """
        matches = []

        # 获取目标文件夹中的视频文件stem集合
        video_stems = set()
        for target_file in target_files:
            ext = os.path.splitext(target_file['name'])[1].lower()
            if ext in [
                '.mp4',
                '.mkv',
                '.avi',
                '.ts',
                '.iso',
                '.rmvb',
                '.wmv',
                '.m2ts',
                '.mpg',
                '.flv',
                '.mov',
                '.vob',
                '.webm',
                '.divx',
                '.3gp',
                '.rm',
                '.m4v',
            ]:
                video_stems.add(target_file['stem'])

        # 为每个元数据文件查找匹配的视频文件
        for metadata_file in metadata_files:
            metadata_stem = metadata_file['stem']
            if metadata_stem in video_stems:
                # 找到匹配的视频文件
                for target_file in target_files:
                    if target_file['stem'] == metadata_stem:
                        matches.append((metadata_file, target_file))
                        break

        return matches

    def merge(self, matches: list, callback=None) -> None:
        """
        执行文件合并（移动元数据文件到目标文件夹）
        :param matches: 匹配结果列表
        """
        total = len(matches)
        if total == 0:
            self._report_progress(callback, 0, 100, "没有可合并的匹配文件")
            self.logger.info("没有可合并的匹配文件")
            return

        for metadata_file, target_file in matches:
            if self.stop_flag.is_set():
                self.logger.info("合并操作已停止")
                return

            # 计算目标路径（保持相对目录结构）
            target_dir = os.path.dirname(target_file['path'])
            dest_path = os.path.join(target_dir, metadata_file['name'])

            # 如果目标文件已存在，跳过
            if os.path.exists(dest_path):
                self.logger.warning(f"目标文件已存在，跳过: {dest_path}")
                self.processed_files += 1
                self._report_progress(
                    callback,
                    self.processed_files,
                    total,
                    f"已处理: {self.processed_files}/{total}, 已存在: {dest_path}",
                )
                continue

            try:
                # 移动文件
                shutil.move(metadata_file['path'], dest_path)
                self.logger.info(f"已移动: {metadata_file['path']} -> {dest_path}")
                self.success_count += 1
                self.processed_files += 1
                self._report_progress(
                    callback,
                    self.processed_files,
                    total,
                    f"已处理: {self.processed_files}/{total}, 已移动: {metadata_file['name']}",
                )
            except Exception as e:
                self.logger.error(f"移动文件失败: {str(e)}")
                self.error_count += 1
                self.processed_files += 1
                self._report_progress(
                    callback,
                    self.processed_files,
                    total,
                    f"处理失败: {metadata_file['name']} ({self.processed_files}/{total})",
                )

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

        send_message(f"开始扫描元数据文件夹: {self.metadata_folder}")
        metadata_files = self.scan(self.metadata_folder, callback=callback)

        send_message(f"开始扫描目标文件夹: {self.target_folder}")
        target_files = self.scan(self.target_folder, callback=callback)

        self.total_files = len(metadata_files)
        send_message(f"发现 {len(metadata_files)} 个元数据文件, {len(target_files)} 个目标文件")

        if self.stop_flag.is_set():
            send_message("操作已停止")
            return

        send_message("开始匹配文件...")
        matches = self.match(metadata_files, target_files)
        send_message(f"找到 {len(matches)} 个匹配")

        if self.stop_flag.is_set():
            send_message("操作已停止")
            return

        send_message("开始合并文件...")
        self.merge(matches, callback=callback)

        send_message(f"合并完成: 成功 {self.success_count}, 失败 {self.error_count}, 总计 {self.processed_files}")
