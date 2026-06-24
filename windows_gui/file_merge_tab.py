import os
import tkinter as tk
from tkinter import ttk

from services.file_merger import FileMerger
from utils.config import Config
from utils.history_entry import HistoryEntry
from utils.logger import setup_logger

from .base_tab import BaseTab


class FileMergeTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()

    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="视频文件夹中的视频将自动合并到元数据文件夹中")
        desc_label.pack(fill='x', padx=5, pady=5)

        # 元数据文件夹选择（带历史记录）
        self.metadata_entry = HistoryEntry(
            self.frame, self.config, 'file_merge', 'metadata_folder', label_text="元数据文件夹"
        )
        self.metadata_entry.pack(fill='x', padx=5, pady=5)
        self.metadata_entry.on_change = lambda path: self.save_config()

        # 视频文件夹选择（带历史记录）
        self.target_entry = HistoryEntry(
            self.frame, self.config, 'file_merge', 'target_folder', label_text="视频文件夹"
        )
        self.target_entry.pack(fill='x', padx=5, pady=5)
        self.target_entry.on_change = lambda path: self.save_config()

        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)

        merge_files_btn = ttk.Button(btn_frame, text="合并文件", command=self.merge_files)
        merge_files_btn.pack(side='left', padx=5)

        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'file_merge.log')
        self.logger = setup_logger('file_merge', self.log_text, log_file)
        self.logger.info("文件合并标签页初始化完成")

    def on_metadata_drop(self, event):
        """处理元数据文件夹拖放事件（HistoryEntry已内置拖放功能）"""
        pass

    def on_target_drop(self, event):
        """处理视频文件夹拖放事件（HistoryEntry已内置拖放功能）"""
        pass

    def save_config(self):
        # 更新配置
        metadata_folder = self.metadata_entry.get().strip()
        if metadata_folder and metadata_folder != '':
            metadata_folder = os.path.normpath(metadata_folder)  # 规范化路径
        self.config.set('file_merge', 'metadata_folder', metadata_folder)
        # 更新配置
        target_folder = self.target_entry.get().strip()
        if target_folder and target_folder != '':
            target_folder = os.path.normpath(target_folder)  # 规范化路径
        self.config.set('file_merge', 'target_folder', target_folder)
        self.config.save()

    def load_config(self):
        metadata_folder = self.config.get('file_merge', 'metadata_folder', default='')
        if metadata_folder and metadata_folder != '':
            metadata_folder = os.path.normpath(metadata_folder)
        target_folder = self.config.get('file_merge', 'target_folder', default='')
        if target_folder and target_folder != '':
            target_folder = os.path.normpath(target_folder)
        # 先清空再设置值，避免插入到现有内容前面
        self.metadata_entry.delete(0, tk.END)
        self.metadata_entry.insert(0, metadata_folder)
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, target_folder)

    def merge_files(self):
        """合并文件"""
        metadata_folder = self.metadata_entry.get()
        target_folder = self.target_entry.get()

        # 检查文件路径权限
        if not os.access(metadata_folder, os.R_OK):
            self.logger.error(f"没有读取权限: {metadata_folder}")
            return
        if not os.access(target_folder, os.R_OK):
            self.logger.error(f"没有读取权限: {target_folder}")
            return

        file_merger = FileMerger(metadata_folder, target_folder, self.logger)
        file_merger.run()
