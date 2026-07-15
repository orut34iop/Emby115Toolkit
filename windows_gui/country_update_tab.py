"""更新地区标签页 - Windows tkinter 版本。"""

import os
import tkinter as tk
from tkinter import ttk

from media_server.client import MediaServerClient
from utils.config import Config
from utils.logger import setup_logger

from .base_tab import BaseTab


class CountryUpdateTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.media_server_client = None
        self.active_task = None
        self.init_ui()
        self.load_config()
        self.logger.info("更新地区标签页初始化完成")

    def load_config(self):
        config = self.config.get('country_update') or {}
        if not all(config.get(key) for key in ('server_url', 'api_key', 'username')):
            config = self.config.get('genre_update') or config

        self.server_type_var.set(config.get('server_type', 'emby'))
        self.server_url_entry.delete(0, tk.END)
        self.server_url_entry.insert(0, config.get('server_url', ''))
        self.api_key_entry.delete(0, tk.END)
        self.api_key_entry.insert(0, config.get('api_key', ''))
        self.username_entry.delete(0, tk.END)
        self.username_entry.insert(0, config.get('username', ''))

    def save_config(self):
        self.config.set('country_update', 'server_url', self.server_url_entry.get().strip())
        self.config.set('country_update', 'api_key', self.api_key_entry.get().strip())
        self.config.set('country_update', 'username', self.username_entry.get().strip())
        self.config.set('country_update', 'server_type', self.server_type_var.get())
        self.config.save()

    def init_ui(self):
        desc_label = ttk.Label(self.frame, text="使用说明: 统一媒体库中的制片国家/地区为简体中文")
        desc_label.pack(fill='x', padx=5, pady=5)

        server_type_frame = ttk.LabelFrame(self.frame, text="服务器类型", padding=(5, 5, 5, 5))
        server_type_frame.pack(fill='x', padx=5, pady=5)
        self.server_type_var = tk.StringVar(value='emby')
        ttk.Radiobutton(
            server_type_frame,
            text="Emby",
            variable=self.server_type_var,
            value="emby",
            command=self.save_config,
        ).pack(side='left', padx=5)
        ttk.Radiobutton(
            server_type_frame,
            text="Jellyfin",
            variable=self.server_type_var,
            value="jellyfin",
            command=self.save_config,
        ).pack(side='left', padx=5)

        server_url_frame = ttk.LabelFrame(self.frame, text="服务器地址", padding=(5, 5, 5, 5))
        server_url_frame.pack(fill='x', padx=5, pady=5)
        self.server_url_entry = ttk.Entry(server_url_frame)
        self.server_url_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.server_url_entry.bind('<FocusOut>', lambda _event: self.save_config())

        api_key_frame = ttk.LabelFrame(self.frame, text="API Key", padding=(5, 5, 5, 5))
        api_key_frame.pack(fill='x', padx=5, pady=5)
        self.api_key_entry = ttk.Entry(api_key_frame)
        self.api_key_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.api_key_entry.bind('<FocusOut>', lambda _event: self.save_config())

        username_frame = ttk.LabelFrame(self.frame, text="用户名", padding=(5, 5, 5, 5))
        username_frame.pack(fill='x', padx=5, pady=5)
        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.username_entry.bind('<FocusOut>', lambda _event: self.save_config())

        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        self.update_countries_btn = ttk.Button(
            btn_frame,
            text="更新所有地区为简体中文",
            command=self.update_countries,
        )
        self.update_countries_btn.pack(side='left', padx=5)
        self.stop_countries_btn = ttk.Button(
            btn_frame,
            text="停止",
            command=self.stop_update,
            state=tk.DISABLED,
        )
        self.stop_countries_btn.pack(side='left', padx=5)

        self.progress_frame, self.progress_bar = self.create_progress_frame(self.frame)
        self.progress_frame.pack(fill='x', padx=5, pady=5)
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        self.logger = setup_logger(
            'country_update',
            self.log_text,
            os.path.join(self.log_dir, 'country_update.log'),
        )

    def update_countries(self):
        if self.active_task and self.active_task.is_alive():
            self.logger.warning("已有地区更新任务正在运行")
            return

        server_url = self.server_url_entry.get().strip()
        api_key = self.api_key_entry.get().strip()
        username = self.username_entry.get().strip()
        server_type = self.server_type_var.get()
        if not server_url or not api_key or not username:
            self.logger.warning("服务器地址、用户名或API密钥为空")
            return

        self.logger.info(f"开始更新地区: 服务器类型={server_type}, URL={server_url}, 用户名={username}")
        media_server_client = MediaServerClient(
            server_url=server_url,
            api_key=api_key,
            username=username,
            server_type=server_type,
            logger=self.logger,
        )

        try:
            task = media_server_client.update_countries()
        except RuntimeError as error:
            self.logger.error(str(error))
            return

        if task and hasattr(task, 'is_alive'):
            self.media_server_client = media_server_client
            self.active_task = task
            self._set_running(True)
            self._poll_task()

    def stop_update(self):
        if self.media_server_client and self.active_task and self.active_task.is_alive():
            self.media_server_client.request_stop()
            self.stop_countries_btn.config(state=tk.DISABLED)
            self.logger.info("正在停止地区更新，请等待当前请求结束...")
        else:
            self.logger.warning("当前没有正在运行的地区更新任务")

    def _set_running(self, running):
        self.update_countries_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_countries_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        if running:
            self.progress_bar.start(10)
        else:
            self.progress_bar.stop()
            self.progress_bar.config(value=0)

    def _poll_task(self):
        if self.active_task and self.active_task.is_alive():
            self.frame.after(500, self._poll_task)
            return

        self.active_task = None
        self.media_server_client = None
        self._set_running(False)
        self.logger.info("更新地区后台任务结束")
