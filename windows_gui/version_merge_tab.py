import os
import tkinter as tk
from tkinter import ttk

from media_server.client import MediaServerClient
from utils.config import Config
from utils.logger import setup_logger

from .base_tab import BaseTab


class VersionMergeTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("合并版本标签页初始化完成")

    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('version_merge')
        if config:
            # 加载服务器类型
            self.server_type_var.set(config.get('server_type', 'emby'))

            # 加载服务器 URL
            if 'server_url' in config:
                self.server_url_entry.delete(0, tk.END)
                self.server_url_entry.insert(0, config['server_url'])
                self.logger.info(f"加载服务器 URL: {config['server_url']}")

            # 加载 API
            if 'api_key' in config:
                self.api_key_entry.delete(0, tk.END)
                self.api_key_entry.insert(0, config['api_key'])
                self.logger.info(f"加载 API: {config['api_key']}")

            username = config.get('username') or self.config.get('genre_update', 'username', '')
            self.username_entry.delete(0, tk.END)
            self.username_entry.insert(0, username)

    def save_config(self):
        """保存当前设置到配置文件"""
        # 更新配置
        self.config.set('version_merge', 'server_url', self.server_url_entry.get().strip())
        self.config.set('version_merge', 'api_key', self.api_key_entry.get().strip())
        self.config.set('version_merge', 'username', self.username_entry.get().strip())
        self.config.set('version_merge', 'server_type', self.server_type_var.get())

        # 保存到文件
        self.config.save()
        self.logger.info("配置已保存")

    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="使用说明: 合并媒体库中相同tmdbid的电影")
        desc_label.pack(fill='x', padx=5, pady=5)

        # 服务器类型
        server_type_frame = ttk.LabelFrame(self.frame, text="服务器类型", padding=(5, 5, 5, 5))
        server_type_frame.pack(fill='x', padx=5, pady=5)

        self.server_type_var = tk.StringVar(value='emby')
        ttk.Radiobutton(
            server_type_frame, text="Emby", variable=self.server_type_var, value="emby", command=self.save_config
        ).pack(side='left', padx=5)
        ttk.Radiobutton(
            server_type_frame,
            text="Jellyfin",
            variable=self.server_type_var,
            value="jellyfin",
            command=self.save_config,
        ).pack(side='left', padx=5)

        # URL 输入框
        server_url_frame = ttk.LabelFrame(self.frame, text="服务器地址", padding=(5, 5, 5, 5))
        server_url_frame.pack(fill='x', padx=5, pady=5)

        self.server_url_entry = ttk.Entry(server_url_frame)
        self.server_url_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.server_url_entry.bind('<FocusOut>', lambda e: self.save_config())

        # API 输入框
        api_key_frame = ttk.LabelFrame(self.frame, text="API Key", padding=(5, 5, 5, 5))
        api_key_frame.pack(fill='x', padx=5, pady=5)

        self.api_key_entry = ttk.Entry(api_key_frame)
        self.api_key_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.api_key_entry.bind('<FocusOut>', lambda e: self.save_config())

        username_frame = ttk.LabelFrame(self.frame, text="用户名", padding=(5, 5, 5, 5))
        username_frame.pack(fill='x', padx=5, pady=5)
        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.username_entry.bind('<FocusOut>', lambda e: self.save_config())

        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)

        self.merge_versions_btn = ttk.Button(btn_frame, text="开始合并", command=self.merge_versions)
        self.merge_versions_btn.pack(side='left', padx=5)
        self.create_stop_button(btn_frame)
        self.register_task_buttons(self.merge_versions_btn)

        self.progress_frame, self.progress_bar = self.create_progress_frame(self.frame)
        self.progress_frame.pack(fill='x', padx=5, pady=5)

        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'version_merge.log')
        self.logger = setup_logger('version_merge', self.log_text, log_file)

    def merge_versions(self):
        server_url = self.server_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        username = self.username_entry.get().strip()
        server_type = self.server_type_var.get()

        if not server_url or not api_key or (server_type == 'jellyfin' and not username):
            self.logger.warning("服务器地址、API密钥或 Jellyfin 用户名为空")
            return

        def task():
            self.logger.info(f"开始合并版本: 服务器类型={server_type}, URL={server_url}")
            media_server_client = self.track_worker(
                MediaServerClient(
                    server_url=server_url,
                    api_key=api_key,
                    username=username,
                    server_type=server_type,
                    logger=self.logger,
                )
            )
            try:
                worker_thread = media_server_client.merge_versions(lambda message: self.logger.info(message))
                if worker_thread:
                    worker_thread.join()
            except RuntimeError as e:
                self.logger.error(str(e))

        self.start_background_task("合并版本", task)
