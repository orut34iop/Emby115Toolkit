import os
import ctypes
import sys
import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from utils.history_entry import HistoryEntry
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
        
        # 刮削文件夹选择（带历史记录）
        self.scrap_entry = HistoryEntry(
            self.frame, 
            self.config, 
            'merge_file', 
            'scrap_folder',
            label_text="刮削文件夹"
        )
        self.scrap_entry.pack(fill='x', padx=5, pady=5)
        self.scrap_entry.on_change = lambda path: self.save_config()

        # 视频文件夹选择（带历史记录）
        self.target_entry = HistoryEntry(
            self.frame, 
            self.config, 
            'merge_file', 
            'target_folder',
            label_text="视频文件夹"
        )
        self.target_entry.pack(fill='x', padx=5, pady=5)
        self.target_entry.on_change = lambda path: self.save_config()

        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        merge_file_btn = ttk.Button(btn_frame, text="合并文件", command=self.merge_file)
        merge_file_btn.pack(side='left', padx=5)

        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'merge_file.log')
        self.logger = setup_logger('merge_file', self.log_text, log_file)
        self.logger.info("文件合并标签页初始化完成")
    
    def on_scrap_drop(self, event):
        """处理刮削文件夹拖放事件（HistoryEntry已内置拖放功能）"""
        pass
    
    def on_target_drop(self, event):
        """处理视频文件夹拖放事件（HistoryEntry已内置拖放功能）"""
        pass
    
    def save_config(self):
        # 更新配置
        scrap_folder = self.scrap_entry.get().strip()
        scrap_folder = os.path.normpath(scrap_folder) # 规范化路径
        self.config.set('merge_file', 'scrap_folder', scrap_folder)
        # 更新配置
        target_folder = self.target_entry.get().strip()
        target_folder = os.path.normpath(target_folder) # 规范化路径
        self.config.set('merge_file', 'target_folder', target_folder)
        self.config.save()
    
    def load_config(self):
        scrap_folder = self.config.get('merge_file', 'scrap_folder', default='')
        if not scrap_folder and scrap_folder != '':
            scrap_folder = os.path.normpath(scrap_folder)
        target_folder = self.config.get('merge_file', 'target_folder', default='')
        if not target_folder and target_folder != '':
            target_folder = os.path.normpath(target_folder)
        self.scrap_entry.insert(0, scrap_folder)
        self.target_entry.insert(0, target_folder)
    
    def merge_file(self):
        """合并文件"""
        scrap_folder = self.scrap_entry.get()
        target_folder = self.target_entry.get()
        
        # 检查文件路径权限
        if not os.access(scrap_folder, os.R_OK):
            self.logger.error(f"没有读取权限: {scrap_folder}")
            return
        if not os.access(target_folder, os.R_OK):
            self.logger.error(f"没有读取权限: {target_folder}")
            return
        
        file_merger = FileMerger(scrap_folder, target_folder, self.logger)
        file_merger.run()