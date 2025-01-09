import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from emby.EmbyOperator import EmbyOperator

class MergeVersionTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("emby合并版本标签页初始化完成")
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('merge_version')
        if config:   
            # 加载Emby URL
            if 'emby_url' in config:
                self.emby_url_entry.delete(0, tk.END)
                self.emby_url_entry.insert(0, config['emby_url'])
                self.logger.info(f"加载Emby URL: {config['emby_url']}")
            
            # 加载Emby API
            if 'emby_api' in config:
                self.emby_api_entry.delete(0, tk.END)
                self.emby_api_entry.insert(0, config['emby_api'])
                self.logger.info(f"加载Emby API: {config['emby_api']}")
    
    def save_config(self):
        """保存当前设置到配置文件"""
        # 更新配置
        self.config.set('merge_version', 'emby_url', self.emby_url_entry.get().strip())
        self.config.set('merge_version', 'emby_api', self.emby_api_entry.get().strip())
        
        # 保存到文件
        self.config.save()
        self.logger.info("配置已保存")
        
    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="使用说明: 自动合并Emby库中的电影")
        desc_label.pack(fill='x', padx=5, pady=5)
        
        # Emby URL 输入框
        emby_url_frame = ttk.LabelFrame(self.frame, text="Emby URL", padding=(5, 5, 5, 5))
        emby_url_frame.pack(fill='x', padx=5, pady=5)
        
        self.emby_url_entry = ttk.Entry(emby_url_frame)
        self.emby_url_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.emby_url_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        # Emby API 输入框
        emby_api_frame = ttk.LabelFrame(self.frame, text="Emby API", padding=(5, 5, 5, 5))
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
        
        if not server_url or not api_key:
            self.logger.warning("Emby URL或API密钥为空")
            return
        
        self.logger.info(f"开始合并版本: Emby URL={server_url}, Emby API={api_key}")
            
        embyOperator = EmbyOperator(
            server_url=server_url,
            api_key=api_key,
            logger=self.logger  # 传递logger
        )
        
        def on_check_complete(message):
            self.logger.info(message)
        
        # 运行查重
        embyOperator.merge_versions(on_check_complete)
