import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from emby.EmbyOperator import EmbyOperator

class CheckDuplicateTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("emby影剧查重标签页初始化完成")
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('check_duplicate')
        if config:
            # 加载目标文件夹
            if 'target_folder' in config:
                target_folder = config['target_folder']
                if not target_folder and target_folder != '':
                    target_folder = os.path.normpath(target_folder)
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, target_folder)
                self.logger.info(f"加载目标文件夹: {target_folder}")
            
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
        target_folder = self.target_entry.get().strip()
        if not target_folder and target_folder != '':
            target_folder = os.path.normpath(target_folder) # 规范化路径
        self.config.set('check_duplicate', 'target_folder', target_folder)
        self.config.set('check_duplicate', 'emby_url', self.emby_url_entry.get().strip())
        self.config.set('check_duplicate', 'emby_api', self.emby_api_entry.get().strip())
        
        # 保存到文件
        self.config.save()
        self.logger.info("配置已保存")
        
    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="使用说明: 选择文件夹并输入Emby URL和API密钥进行查重")
        desc_label.pack(fill='x', padx=5, pady=5)
        
        # 目标文件夹选择
        target_frame = ttk.LabelFrame(self.frame, text="目标文件夹", padding=(5, 5, 5, 5))
        target_frame.pack(fill='x', padx=5, pady=5)
        
        self.target_entry = ttk.Entry(target_frame)
        self.target_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        # 启用拖放功能
        self.target_entry.drop_target_register(DND_FILES)
        self.target_entry.dnd_bind('<<Drop>>', lambda e: self.on_target_drop(e))
        
        def browse_target():
            folder = filedialog.askdirectory(title="选择目标文件夹")   
            if folder:
                #规范化路径
                if not folder and folder != '':
                    folder = os.path.normpath(folder)
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, folder)
                self.logger.info(f"已选择目标文件夹: {folder}")
                self.save_config()
        
        target_browse = ttk.Button(target_frame, text="浏览", command=browse_target)
        target_browse.pack(side='right', padx=5)
        
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
        
        check_duplicate_btn = ttk.Button(btn_frame, text="开始查重", command=self.check_duplicate)
        check_duplicate_btn.pack(side='left', padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(self.frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'check_duplicate.log')
        self.logger = setup_logger('check_duplicate', self.log_text, log_file)
        self.logger.info("emby影剧查重标签页初始化完成")
        
    def on_target_drop(self, event):
        """处理目标文件夹拖放事件"""
        data = event.data
        if data:
            paths = self.scan_string(data)
            if paths:
                path = paths[0].strip()  # 只取第一个路径
                if os.path.exists(path) and os.path.isdir(path):
                    self.target_entry.delete(0, tk.END)
                    self.target_entry.insert(0, path)
                    self.logger.info(f"已设置目标文件夹: {path}")
                    self.save_config()
                else:
                    self.logger.warning("无效的目标文件夹路径")

    def validate_and_save_target(self):
        """验证并保存目标文件夹路径"""
        path = self.target_entry.get().strip()
        if self.validate_target_folder(path):
            self.save_config()

    def check_duplicate(self):
        target_folder = self.target_entry.get().strip()
        server_url = self.emby_url_entry.get().strip()
        api_key = self.emby_api_entry.get().strip()
        
        if not target_folder or not server_url or not api_key:
            self.logger.warning("目标文件夹、Emby URL或API密钥为空")
            return
        
        self.logger.info(f"开始查重: 目标文件夹={target_folder}, Emby URL={server_url}, Emby API={api_key}")
        
        # 查重逻辑
        # ...实现查重的逻辑...
            
        embyOperator = EmbyOperator(
            server_url=server_url,
            api_key=api_key,
            logger=self.logger  # 传递logger
        )
        
        def on_check_complete(total_time, message):
            summary = (
                f"影剧查重完成\n"
                f"总耗时: {total_time:.2f} 秒\n"
                f"{message}"
            )
            self.logger.info(summary)
        
        # 运行查重
        embyOperator.check_duplicate(target_folder, on_check_complete)
