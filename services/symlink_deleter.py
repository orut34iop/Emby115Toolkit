import logging
import os
import threading
import time

from utils.service_messages import SYMLINK_NAME_BY_MODE


class SymlinkDeleter:
    def __init__(
        self,
        target_folder,
        logger=None,  # 添加logger参数
    ):
        self.target_folder = target_folder
        self.logger = logger or logging.getLogger(__name__)  # 使用传递的logger
        self.symlink_name = SYMLINK_NAME_BY_MODE.get("symlink")
        self.stop_flag = threading.Event()

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
        self.logger.info(f"已请求停止删除{self.symlink_name}")

    def run(self, callback=None):
        deleted_links = 0
        total_links = 0
        links = []
        start_time = time.time()
        self.logger.info(f"开始删除{self.symlink_name}...")

        # 遍历目录中的所有文件
        for root, _, files in os.walk(self.target_folder):
            if self.stop_flag.is_set():
                self.logger.info(f"删除{self.symlink_name}操作已停止")
                break

            for file in files:
                if self.stop_flag.is_set():
                    self.logger.info(f"删除{self.symlink_name}操作已停止")
                    break

                file_path = os.path.join(root, file)
                # 检查是否为符号链接
                if os.path.islink(file_path):
                    links.append(file_path)

        if callback:
            self._report_progress(callback, 0, len(links), f"开始删除{self.symlink_name}：共 {len(links)} 个")

        for index, file_path in enumerate(links, start=1):
            if self.stop_flag.is_set():
                self.logger.info(f"删除{self.symlink_name}操作已停止")
                break

            try:
                total_links += 1
                # 删除符号链接
                os.unlink(file_path)
                deleted_links += 1
                self.logger.info(f"已删除符号链接：{file_path}")
                if callback:
                    self._report_progress(callback, index, len(links), f"已删除 {index}/{len(links)}: {file_path}")
            except PermissionError:
                self.logger.error(f"错误：无法删除符号链接 {file_path}，权限不足。")
            except Exception as e:
                self.logger.error(f"错误：删除符号链接 {file_path} 时发生错误：{e}")

        end_time = time.time()
        total_time = end_time - start_time
        title = f"删除{self.symlink_name}已停止" if self.stop_flag.is_set() else f"删除{self.symlink_name}完成"
        message = f"{title}:总耗时 {total_time:.2f} 秒, 共处理{self.symlink_name}数：{total_links}个，共删除{self.symlink_name}数：{deleted_links}，共跳过{self.symlink_name}数：{total_links - deleted_links}"
        self.logger.info(title)
        self.logger.info(message)
        return total_time, message
