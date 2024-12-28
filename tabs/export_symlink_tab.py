import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config

class ExportSymlinkTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('export_symlink')
        if config:
            # 加载线程数
            if 'thread_count' in config:
                self.thread_spinbox.set(config['thread_count'])
            
            # 加载目标文件夹
            if 'target_folder' in config:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, config['target_folder'])
            
            # 加载链接文件夹列表
            if 'link_folders' in config and config['link_folders']:
                self.link_text.delete('1.0', tk.END)
                self.link_text.insert('1.0', '\n'.join(config['link_folders']))
            
            # 加载后缀设置
            if 'link_suffixes' in config:
                self.link_suffix_entry.delete(0, tk.END)
                self.link_suffix_entry.insert(0, ';'.join(config['link_suffixes']))
            
            if 'meta_suffixes' in config:
                self.meta_suffix_entry.delete(0, tk.END)
                self.meta_suffix_entry.insert(0, ';'.join(config['meta_suffixes']))
    
    def save_config(self):
        """保存当前设置到配置文件"""
        # 获取链接文件夹列表
        link_folders = [path.strip() for path in self.link_text.get('1.0', tk.END).strip().split('\n') if path.strip()]
        
        # 获取后缀列表
        link_suffixes = [suffix.strip() for suffix in self.link_suffix_entry.get().split(';') if suffix.strip()]
        meta_suffixes = [suffix.strip() for suffix in self.meta_suffix_entry.get().split(';') if suffix.strip()]
        
        # 更新配置
        self.config.set('export_symlink', 'link_folders', link_folders)
        self.config.set('export_symlink', 'target_folder', self.target_entry.get().strip())
        self.config.set('export_symlink', 'thread_count', int(self.thread_spinbox.get()))
        self.config.set('export_symlink', 'link_suffixes', link_suffixes)
        self.config.set('export_symlink', 'meta_suffixes', meta_suffixes)
        
        # 保存到文件
        self.config.save()
        
    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="使用说明: 将文件夹拖拽到输入框即可生成软链接表（自动忽略重复路径）")
        desc_label.pack(fill='x', padx=5, pady=5)
        
        # 链接文件夹选择
        link_frame = ttk.LabelFrame(self.frame, text="链接文件夹", padding=(5, 5, 5, 5))
        link_frame.pack(fill='x', padx=5, pady=5)
        
        self.link_text = tk.Text(link_frame, height=4, wrap='none')
        self.link_text.pack(fill='x', expand=True, padx=5)
        self.link_text.bind('<<Modified>>', lambda e: self.on_text_modified())
        
        # 启用拖放功能
        self.link_text.drop_target_register(DND_FILES)
        self.link_text.dnd_bind('<<Drop>>', lambda e: self.on_folder_drop(e, self.link_text))
        
        def browse_folders():
            folder = filedialog.askdirectory(title="选择文件夹")
            if folder:
                # 获取当前已有的路径
                current_paths = set()
                if self.link_text.get('1.0', tk.END).strip():
                    current_paths = set(self.link_text.get('1.0', tk.END).strip().split('\n'))
                
                # 检查是否重复
                if folder not in current_paths:
                    if current_paths:  # 如果已经有内容，添加换行
                        self.link_text.insert(tk.END, '\n')
                    self.link_text.insert(tk.END, folder)
                    self.logger.info("成功添加文件夹")
                else:
                    self.logger.info("文件夹已存在，未添加重复路径")
        
        link_browse = ttk.Button(link_frame, text="浏览", command=browse_folders)
        link_browse.pack(padx=5, pady=(5,0))
        
        # 目标文件夹选择
        target_frame = ttk.LabelFrame(self.frame, text="目标文件夹", padding=(5, 5, 5, 5))
        target_frame.pack(fill='x', padx=5, pady=5)
        
        self.target_entry = ttk.Entry(target_frame)
        self.target_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        self.target_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        target_browse = ttk.Button(target_frame, text="浏览")
        target_browse.pack(side='right', padx=5)
        
        # 同步线程数选择
        thread_frame = ttk.Frame(self.frame)
        thread_frame.pack(fill='x', padx=5, pady=5)
        
        thread_label = ttk.Label(thread_frame, text="同步线程数:")
        thread_label.pack(side='left', padx=5)
        
        self.thread_spinbox = ttk.Spinbox(thread_frame, from_=1, to=16, width=10)
        self.thread_spinbox.set(4)  # 默认值
        self.thread_spinbox.pack(side='left', padx=5)
        self.thread_spinbox.bind('<FocusOut>', lambda e: self.save_config())
        
        # 后缀设置
        suffix_frame = ttk.Frame(self.frame)
        suffix_frame.pack(fill='x', padx=5, pady=5)
        
        # 软链接后缀
        link_suffix_label = ttk.Label(suffix_frame, text="软链接后缀:")
        link_suffix_label.pack(side='left', padx=5)
        
        self.link_suffix_entry = ttk.Entry(suffix_frame)
        self.link_suffix_entry.insert(0, ".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm")
        self.link_suffix_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.link_suffix_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        # 元数据后缀
        meta_suffix_label = ttk.Label(suffix_frame, text="元数据后缀:")
        meta_suffix_label.pack(side='left', padx=5)
        
        self.meta_suffix_entry = ttk.Entry(suffix_frame)
        self.meta_suffix_entry.insert(0, ".nfo;.jpg;.png;.svg;.ass;.srt;.sup")
        self.meta_suffix_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.meta_suffix_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="开始同步", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        sync_all_btn = ttk.Button(btn_frame, text="一键全同步")
        sync_all_btn.pack(side='left', padx=5)
        
        create_link_btn = ttk.Button(btn_frame, text="创建软链接")
        create_link_btn.pack(side='left', padx=5)
        
        download_meta_btn = ttk.Button(btn_frame, text="下载元数据")
        download_meta_btn.pack(side='left', padx=5)
        
        copy_version_btn = ttk.Button(btn_frame, text="复制到剪贴版")
        copy_version_btn.pack(side='left', padx=5)
        
        def clear_list():
            self.link_text.delete('1.0', tk.END)
            self.save_config()
            
        clear_list_btn = ttk.Button(btn_frame, text="清空文件夹列表", command=clear_list)
        clear_list_btn.pack(side='left', padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(self.frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'export_symlink.log')
        self.logger = setup_logger('export_symlink', self.log_text, log_file)
        self.logger.info("导出软链接标签页初始化完成")
        
    def on_text_modified(self):
        """处理文本修改事件"""
        if self.link_text.edit_modified():
            self.save_config()
            self.link_text.edit_modified(False)
