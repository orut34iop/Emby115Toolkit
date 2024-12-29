import os
import ctypes
import sys
import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from autosync.FileMerger import FileMerger

class MergeFilesTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="视频文件夹中的视频将自动合并到刮削文件夹中")
        desc_label.pack(fill='x', padx=5, pady=5)
        
        # 刮削文件夹选择
        scrap_frame = ttk.LabelFrame(self.frame, text="刮削文件夹", padding=(5, 5, 5, 5))
        scrap_frame.pack(fill='x', padx=5, pady=5)
        
        self.scrap_entry = ttk.Entry(scrap_frame)
        self.scrap_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        # 启用拖放功能
        self.scrap_entry.drop_target_register(DND_FILES)
        self.scrap_entry.dnd_bind('<<Drop>>', self.on_scrap_drop)
        
        def browse_scrap():
            folder = filedialog.askdirectory(title="选择刮削文件夹")
            if folder:
                self.scrap_entry.delete(0, tk.END)
                self.scrap_entry.insert(0, folder)
                self.logger.info(f"已选择刮削文件夹: {folder}")
                self.save_config()

        scrap_browse = ttk.Button(scrap_frame, text="浏览", command=browse_scrap)
        scrap_browse.pack(side='right', padx=5)

        # 视频文件夹选择
        target_frame = ttk.LabelFrame(self.frame, text="视频文件夹", padding=(5, 5, 5, 5))
        target_frame.pack(fill='x', padx=5, pady=5)
        
        self.target_entry = ttk.Entry(target_frame)
        self.target_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        # 启用拖放功能
        self.target_entry.drop_target_register(DND_FILES)
        self.target_entry.dnd_bind('<<Drop>>', self.on_target_drop)
        
        def browse_target():
            folder = filedialog.askdirectory(title="选择视频文件夹")
            if folder:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, folder)
                self.logger.info(f"已选择视频文件夹: {folder}")
                self.save_config()
        
        target_browse = ttk.Button(target_frame, text="浏览", command=browse_target)
        target_browse.pack(side='right', padx=5)

        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        merge_file_btn = ttk.Button(btn_frame, text="合并文件", command=self.merge_file)
        merge_file_btn.pack(side='left', padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(self.frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'merge_file.log')
        self.logger = setup_logger('merge_file', self.log_text, log_file)
        self.logger.info("文件合并标签页初始化完成")
    
    def on_scrap_drop(self, event):
        folder = event.data.strip('{}')
        self.scrap_entry.delete(0, tk.END)
        self.scrap_entry.insert(0, folder)
        self.save_config()
    
    def on_target_drop(self, event):
        folder = event.data.strip('{}')
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, folder)
        self.save_config()
    
    def save_config(self):
        self.config.set('merge_file', 'scrap_folder', self.scrap_entry.get())
        self.config.set('merge_file', 'target_folder', self.target_entry.get())
        self.config.save()
    
    def load_config(self):
        scrap_folder = self.config.get('merge_file', 'scrap_folder', default='')
        target_folder = self.config.get('merge_file', 'target_folder', default='')
        self.scrap_entry.insert(0, scrap_folder)
        self.target_entry.insert(0, target_folder)
    
    def merge_file(self):
        """合并文件"""
        scrap_folder = self.scrap_entry.get()
        target_folder = self.target_entry.get()
        file_merger = FileMerger(scrap_folder, target_folder, self.logger)
        file_merger.run()
        
        # 显示总结信息
        summary = (
            f"删除软链接完成\n"
            #f"总耗时: {time_taken:.2f} 秒\n"
        )
        self.logger.info(summary)

