import logging
import os
import threading
import time
import urllib.parse

symlink_name_dict = {"symlink": "软链接", "strm": "strm文件"}


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
        symlink_size=0,
        enable_115_protect=False,
        op_interval_sec=0,
        cloud_type=None,
        cloud_root_path=None,
        cloud_url=None,
        progress_interval=100,
        progress_seconds=2.0,
        logger=None,
    ):
        """
        初始化 SymlinkCreator
        progress_interval/progress_seconds 控制扫描和创建阶段的进度日志频率。
        """
        self.link_folders = link_folders or []
        self.target_folder = target_folder
        self.symlink_mode = symlink_mode
        self.thread_count = thread_count
        self.enable_replace_path = enable_replace_path
        self.original_path = original_path
        self.replace_path = replace_path
        self.only_tvshow_nfo = only_tvshow_nfo
        self.allowed_extensions = self._normalize_extensions(allowed_extensions or ('.mp4', '.mkv', '.avi', '.ts'))
        self.symlink_size = symlink_size
        self.enable_115_protect = enable_115_protect
        self.op_interval_sec = op_interval_sec
        self.cloud_type = cloud_type
        self.cloud_root_path = cloud_root_path
        self.cloud_url = cloud_url
        self.progress_interval = progress_interval
        self.progress_seconds = progress_seconds

        self.logger = logger or logging.getLogger(__name__)

        # 计数器
        self.total_files = 0
        self.processed_files = 0
        self.success_count = 0
        self.error_count = 0
        self.created_links = 0
        self.existing_links = 0
        self.scanned_files = 0
        self.matched_files = 0
        self._last_scan_total_files = 0

        # 停止标志
        self.stop_flag = threading.Event()

        self._counter_lock = threading.Lock()

        # 验证 symlink_mode
        if symlink_mode not in ('symlink', 'strm'):
            raise ValueError(f"无效的 symlink_mode: {symlink_mode}，必须是 'symlink' 或 'strm'")

        self.symlink_name = symlink_name_dict.get(self.symlink_mode, '链接')

    def _should_log_progress(self, count: int, last_progress_time: float) -> bool:
        if count <= 0:
            return False

        try:
            progress_interval = int(self.progress_interval or 0)
        except (TypeError, ValueError):
            progress_interval = 0

        if progress_interval > 0 and count % progress_interval == 0:
            return True

        try:
            progress_seconds = float(self.progress_seconds or 0)
        except (TypeError, ValueError):
            progress_seconds = 0

        return progress_seconds > 0 and time.monotonic() - last_progress_time >= progress_seconds

    def _normalize_extensions(self, extensions):
        if isinstance(extensions, str):
            extensions = [extensions]

        normalized = []
        for extension in extensions:
            extension = str(extension).strip().lower()
            if not extension:
                continue
            if not extension.startswith("."):
                extension = f".{extension}"
            normalized.append(extension)
        return tuple(normalized)

    def _protect_interval(self) -> None:
        """115 防封模式下，在文件操作之间加入间隔。"""
        if not self.enable_115_protect:
            return

        try:
            interval = float(self.op_interval_sec or 0)
        except (TypeError, ValueError):
            interval = 0

        if interval > 0:
            time.sleep(interval)

    def scan(self, folder_path: str) -> list:
        """
        扫描文件夹，返回文件列表
        :param folder_path: 要扫描的文件夹路径
        :return: 文件列表，每个元素是包含 name, path, is_symlink 的字典
        """
        result = []
        scanned_count = 0
        last_progress_time = time.monotonic()
        if not os.path.exists(folder_path):
            self._last_scan_total_files = scanned_count
            return result

        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                # 跳过符号链接
                if os.path.islink(file_path):
                    continue
                scanned_count += 1
                ext = os.path.splitext(filename)[1].lower()

                if not self.allowed_extensions or ext in self.allowed_extensions:
                    rel_path = os.path.relpath(file_path, folder_path)
                    result.append(
                        {
                            'name': filename,
                            'path': file_path,
                            'rel_path': rel_path,
                            'stem': os.path.splitext(filename)[0],
                            'ext': ext,
                        }
                    )

                if self._should_log_progress(scanned_count, last_progress_time):
                    self.logger.info(
                        f"扫描进度: 已扫描 {scanned_count} 个文件，匹配 {len(result)} 个{self.symlink_name}候选"
                    )
                    last_progress_time = time.monotonic()
        self._last_scan_total_files = scanned_count
        return result

    def create(self, files: list, target_folder: str) -> None:
        """
        创建符号链接或 strm 文件
        :param files: 源文件列表
        :param target_folder: 目标文件夹
        """
        total = len(files)
        if total == 0:
            self.logger.info(f"没有匹配的{self.symlink_name}候选，跳过创建")
            return

        self.logger.info(f"待创建{self.symlink_name}候选: {total} 个")
        last_progress_time = time.monotonic()

        for index, file_info in enumerate(files, start=1):
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

            if index == total or self._should_log_progress(index, last_progress_time):
                self.logger.info(
                    f"创建进度: {index}/{total}，"
                    f"新建 {self.created_links}，"
                    f"已存在 {self.existing_links}，"
                    f"失败 {self.error_count}"
                )
                last_progress_time = time.monotonic()

    def _create_symlink(self, src: str, dst: str) -> None:
        """创建符号链接"""
        try:
            # 路径替换
            link_src = src
            if self.enable_replace_path and self.original_path and self.replace_path:
                link_src = src.replace(self.original_path, self.replace_path)

            if os.path.lexists(dst):
                with self._counter_lock:
                    self.existing_links += 1
                    self.processed_files += 1
                self.logger.info(f"软链接已存在，跳过: {dst}")
                return

            os.symlink(link_src, dst)
            with self._counter_lock:
                self.created_links += 1
                self.success_count += 1
                self.processed_files += 1
            self.logger.info(f"创建软链接: {dst} -> {link_src}")
            self._protect_interval()
        except Exception as e:
            with self._counter_lock:
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

            if os.path.lexists(strm_path):
                with self._counter_lock:
                    self.existing_links += 1
                    self.processed_files += 1
                self.logger.info(f"strm 文件已存在，跳过: {strm_path}")
                return

            with open(strm_path, 'w') as f:
                f.write(content)
            with self._counter_lock:
                self.created_links += 1
                self.success_count += 1
                self.processed_files += 1
            self.logger.info(f"创建 strm 文件: {strm_path}")
            self._protect_interval()
        except Exception as e:
            with self._counter_lock:
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

        send_message(
            f"准备创建{self.symlink_name}: 源目录 {len(self.link_folders)} 个，"
            f"目标目录 {self.target_folder}，后缀 {', '.join(self.allowed_extensions)}"
        )

        for source_folder in self.link_folders:
            if self.stop_flag.is_set():
                send_message("操作已停止")
                return

            if not os.path.exists(source_folder):
                self.logger.warning(f"源文件夹不存在: {source_folder}")
                continue

            send_message(f"扫描源文件夹: {source_folder}")
            files = self.scan(source_folder)
            scanned_count = self._last_scan_total_files
            self.total_files += len(files)
            self.scanned_files += scanned_count
            self.matched_files += len(files)
            send_message(f"扫描 {scanned_count} 个文件，匹配 {len(files)} 个{self.symlink_name}候选")

            if self.stop_flag.is_set():
                send_message("操作已停止")
                return

            send_message("开始创建链接...")
            self.create(files, self.target_folder)
            total_created += self.created_links
            total_existing += self.existing_links

        message = (
            f"创建{self.symlink_name}完成\n"
            f"扫描文件: {self.scanned_files}\n"
            f"匹配文件: {self.matched_files}\n"
            f"共创建: {self.success_count}\n"
            f"已存在: {self.existing_links}\n"
            f"失败: {self.error_count}"
        )
        send_message(message)
