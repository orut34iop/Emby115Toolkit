import os
import tkinter as tk
from tkinter import ttk

from media_server.client import MediaServerClient
from utils.config import Config
from utils.logger import setup_logger

from .base_tab import BaseTab


class GenreUpdateTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("更新流派标签页初始化完成")

    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('genre_update')
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

            # 加载用户名
            if 'username' in config:
                self.username_entry.delete(0, tk.END)
                self.username_entry.insert(0, config['username'])
                self.logger.info(f"加载用户名: {config['username']}")

    def save_config(self):
        """保存当前设置到配置文件"""
        # 更新配置
        self.config.set('genre_update', 'server_url', self.server_url_entry.get().strip())
        self.config.set('genre_update', 'api_key', self.api_key_entry.get().strip())
        self.config.set('genre_update', 'username', self.username_entry.get().strip())
        self.config.set('genre_update', 'server_type', self.server_type_var.get())
        # 保存到文件
        self.config.save()
        self.logger.info("配置已保存")

    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="使用说明: 把媒体库中的影剧英文流派名称转成中文")
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

        # User Name 输入框
        username_frame = ttk.LabelFrame(self.frame, text="用户名", padding=(5, 5, 5, 5))
        username_frame.pack(fill='x', padx=5, pady=5)

        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.username_entry.bind('<FocusOut>', lambda e: self.save_config())

        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)

        update_genres_btn = ttk.Button(btn_frame, text="更新所有流派为中文", command=self.update_genres)
        update_genres_btn.pack(side='left', padx=5)

        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'genre_update.log')
        self.logger = setup_logger('genre_update', self.log_text, log_file)

    def update_genres(self):
        server_url = self.server_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        username = self.username_entry.get().strip()
        server_type = self.server_type_var.get()

        if not server_url or not api_key or not username:
            self.logger.warning("服务器地址、用户名或API密钥为空")
            return

        self.logger.info(f"开始更新流派: 服务器类型={server_type}, URL={server_url}, 用户名={username}")

        media_server_client = MediaServerClient(
            server_url=server_url,
            api_key=api_key,
            username=username,
            server_type=server_type,
            logger=self.logger,  # 传递logger
        )

        def on_check_complete(message):
            self.logger.info("更新流派结束")

        try:
            media_server_client.update_genres(on_check_complete)
        except RuntimeError as e:
            self.logger.error(str(e))
