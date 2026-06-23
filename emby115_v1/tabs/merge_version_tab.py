import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from emby115_v1.utils.logger import setup_logger
from emby115_v1.utils.config import Config
from emby115_v1.emby.EmbyOperator import EmbyOperator

class MergeVersionTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("合并版本标签页初始化完成")
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('merge_version')
        if config:   
            # 加载服务器类型
            self.server_type_var.set(config.get('server_type', 'emby'))

            # 加载服务器 URL
            if 'emby_url' in config:
                self.emby_url_entry.delete(0, tk.END)
                self.emby_url_entry.insert(0, config['emby_url'])
                self.logger.info(f"加载服务器 URL: {config['emby_url']}")
            
            # 加载 API
            if 'emby_api' in config:
                self.emby_api_entry.delete(0, tk.END)
                self.emby_api_entry.insert(0, config['emby_api'])
                self.logger.info(f"加载 API: {config['emby_api']}")
    
    def save_config(self):
        """保存当前设置到配置文件"""
        # 更新配置
        self.config.set('merge_version', 'emby_url', self.emby_url_entry.get().strip())
        self.config.set('merge_version', 'emby_api', self.emby_api_entry.get().strip())
        self.config.set('merge_version', 'server_type', self.server_type_var.get())
        
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
            server_type_frame,
            text="Emby",
            variable=self.server_type_var,
            value="emby",
            command=self.save_config
        ).pack(side='left', padx=5)
        ttk.Radiobutton(
            server_type_frame,
            text="Jellyfin",
            variable=self.server_type_var,
            value="jellyfin",
            command=self.save_config
        ).pack(side='left', padx=5)
        
        # URL 输入框
        emby_url_frame = ttk.LabelFrame(self.frame, text="服务器地址", padding=(5, 5, 5, 5))
        emby_url_frame.pack(fill='x', padx=5, pady=5)
        
        self.emby_url_entry = ttk.Entry(emby_url_frame)
        self.emby_url_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.emby_url_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        # API 输入框
        emby_api_frame = ttk.LabelFrame(self.frame, text="API Key", padding=(5, 5, 5, 5))
        emby_api_frame.pack(fill='x', padx=5, pady=5)
        
        self.emby_api_entry = ttk.Entry(emby_api_frame)
        self.emby_api_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.emby_api_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        merge_version_btn = ttk.Button(btn_frame, text="开始合并", command=self.merge_version)
        merge_version_btn.pack(side='left', padx=5)
        
        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'merge_version.log')
        self.logger = setup_logger('merge_version', self.log_text, log_file)

    def merge_version(self):
        server_url = self.emby_url_entry.get().strip()
        api_key = self.emby_api_entry.get().strip()
        server_type = self.server_type_var.get()
        
        if not server_url or not api_key:
            self.logger.warning("服务器地址或API密钥为空")
            return
        
        self.logger.info(f"开始合并版本: 服务器类型={server_type}, URL={server_url}")
            
        embyOperator = EmbyOperator(
            server_url=server_url,
            api_key=api_key,
            server_type=server_type,
            logger=self.logger  # 传递logger
        )
        
        def on_check_complete(message):
            pass
            #self.logger.info(message)
        
        try:
            embyOperator.merge_versions(on_check_complete)
        except RuntimeError as e:
            self.logger.error(str(e))
