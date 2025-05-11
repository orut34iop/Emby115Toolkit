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
        # 编辑后自动保存
        self.scrap_entry.bind('<FocusOut>', lambda e: self.save_config())
        self.scrap_entry.bind('<Return>', lambda e: self.save_config())
        
        # 启用拖放功能
        self.scrap_entry.drop_target_register(DND_FILES)
        self.scrap_entry.dnd_bind('<<Drop>>', self.on_scrap_drop)
        
        def browse_scrap():
            folder = filedialog.askdirectory(title="选择刮削文件夹")
            if folder:
                folder = os.path.normpath(folder)
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
        # 编辑后自动保存
        self.target_entry.bind('<FocusOut>', lambda e: self.save_config())
        self.target_entry.bind('<Return>', lambda e: self.save_config())
        
        # 启用拖放功能
        self.target_entry.drop_target_register(DND_FILES)
        self.target_entry.dnd_bind('<<Drop>>', self.on_target_drop)
        
        def browse_target():
            folder = filedialog.askdirectory(title="选择视频文件夹")
            if folder:
                folder = os.path.normpath(folder)
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

        # 添加115防封勾选框
        self.protect_115_var = tk.BooleanVar(value=False)
        
        # 创建勾选框样式
        style = ttk.Style()
        style.configure(
            "Check.TCheckbutton",
            indicatorrelief='flat',  # 扁平化效果
            indicatorcolor='#32CD32',  # 设置为绿色
            indicatordiameter=20,  # 指示器大小
            font=('Segoe UI', 9)  # 使用系统字体
        )
        style.map(
            "Check.TCheckbutton",
            background=[('active', '#f0f0f0')],  # 鼠标悬停时的背景色
            indicatorcolor=[('selected', '#32CD32'),  # 选中时的颜色
                          ('pressed', '#228B22')]  # 按下时的颜色
        )
        
        protect_115_check = ttk.Checkbutton(
            btn_frame, 
            text="开启115 防封",
            variable=self.protect_115_var,
            command=self.save_config,
            style="Check.TCheckbutton",
            takefocus=False  # 禁用焦点
        )
        protect_115_check.pack(side='left', padx=5)

        # 文件操作时间间隔设置
        op_interval_label = ttk.Label(btn_frame, text="文件操作时间间隔(秒):")
        op_interval_label.pack(side='left', padx=5)
        
        self.op_interval_spinbox = ttk.Spinbox(
            btn_frame, from_=0, to=60, width=10, command=self.save_config, state='readonly'
        )
        self.op_interval_spinbox.set(4)  # 默认值为4秒
        self.op_interval_spinbox.pack(side='left', padx=5)
        self.op_interval_spinbox.bind('<FocusOut>', lambda e: self.save_config())

        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'merge_file.log')
        self.logger = setup_logger('merge_file', self.log_text, log_file)
        self.logger.info("文件合并标签页初始化完成")
    
    def on_scrap_drop(self, event):
        folder = event.data.strip('{}')
        folder = os.path.normpath(folder)
        self.scrap_entry.delete(0, tk.END)
        self.scrap_entry.insert(0, folder)
        self.save_config()
    
    def on_target_drop(self, event):
        folder = event.data.strip('{}')
        folder = os.path.normpath(folder)
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, folder)
        self.save_config()
    
    def save_config(self):
        # 更新配置
        scrap_folder = self.scrap_entry.get().strip()
        scrap_folder = os.path.normpath(scrap_folder) # 规范化路径
        self.config.set('merge_file', 'scrap_folder', scrap_folder)
        # 更新配置
        target_folder = self.target_entry.get().strip()
        target_folder = os.path.normpath(target_folder) # 规范化路径
        self.config.set('merge_file', 'target_folder', target_folder)
        # 保存115防封设置
        self.config.set('merge_file', 'enable_115_protect', bool(self.protect_115_var.get()))
        self.config.set('merge_file', 'op_interval_sec', int(self.op_interval_spinbox.get()))
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
        
        # 加载115防封设置
        enable_115_protect = self.config.get('merge_file', 'enable_115_protect', default=False)
        self.protect_115_var.set(enable_115_protect)
        self.logger.info(f"加载115防封设置: {enable_115_protect}")

        # 加载文件操作时间间隔
        op_interval_sec = self.config.get('merge_file', 'op_interval_sec', default='4')
        self.op_interval_spinbox.set(op_interval_sec)
        self.logger.info(f"加载文件操作时间间隔(秒): {op_interval_sec}")
    
    def merge_file(self):
        """合并文件"""
        scrap_folder = self.scrap_entry.get()
        target_folder = self.target_entry.get()
        enable_115_protect = self.protect_115_var.get()  # 获取115防封设置
        op_interval_sec = self.op_interval_spinbox.get()  # 获取115防封设置
        
        # 检查文件路径权限
        if not os.access(scrap_folder, os.R_OK):
            self.logger.error(f"没有读取权限: {scrap_folder}")
            return
        if not os.access(target_folder, os.R_OK):
            self.logger.error(f"没有读取权限: {target_folder}")
            return
        
        # 记录115防封状态
        self.logger.info(f"115防封状态: {'开启' if enable_115_protect else '关闭'}")
        
        file_merger = FileMerger(scrap_folder, target_folder, enable_115_protect,op_interval_sec, self.logger)
        file_merger.run()