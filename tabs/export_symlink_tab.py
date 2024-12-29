import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from autosync.MetadataCopyer import MetadataCopyer
from autosync.SymlinkCreator import SymlinkCreator


class ExportSymlinkTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("导出软链接标签页初始化完成")
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('export_symlink')
        if config:
            # 加载线程数
            if 'thread_count' in config:
                self.thread_spinbox.set(config['thread_count'])
                self.logger.info(f"加载线程数: {config['thread_count']}")
            
            # 加载目标文件夹
            if 'target_folder' in config:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, config['target_folder'])
                self.logger.info(f"加载目标文件夹: {config['target_folder']}")
            
            # 加载链接文件夹列表
            if 'link_folders' in config and config['link_folders']:
                self.link_text.delete('1.0', tk.END)
                self.link_text.insert('1.0', '\n'.join(config['link_folders']))
                self.logger.info(f"加载链接文件夹列表: {config['link_folders']}")
            
            # 加载后缀设置
            if 'link_suffixes' in config:
                self.link_suffix_entry.delete(0, tk.END)
                self.link_suffix_entry.insert(0, ';'.join(config['link_suffixes']))
                self.logger.info(f"加载软链接后缀: {config['link_suffixes']}")
            
            if 'meta_suffixes' in config:
                self.meta_suffix_entry.delete(0, tk.END)
                self.meta_suffix_entry.insert(0, ';'.join(config['meta_suffixes']))
                self.logger.info(f"加载元数据后缀: {config['meta_suffixes']}")
    
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
        self.logger.info("配置已保存")

    def validate_target_folder(self, path):
        """验证目标文件夹路径"""
        path = path.strip()
        if not path:
            return True
        if not os.path.exists(path):
            self.logger.warning("无效的路径")
            return False
        if not os.path.isdir(path):
            self.logger.warning("所选路径不是目录")
            return False
        return True
        
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
        
        # 启用拖放功能
        self.target_entry.drop_target_register(DND_FILES)
        self.target_entry.dnd_bind('<<Drop>>', lambda e: self.on_target_drop(e))
        
        def browse_target():
            folder = filedialog.askdirectory(title="选择目标文件夹")
            if folder:
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, folder)
                self.logger.info(f"已选择目标文件夹: {folder}")
                self.save_config()
        
        target_browse = ttk.Button(target_frame, text="浏览", command=browse_target)
        target_browse.pack(side='right', padx=5)
        
        # 验证目标文件夹
        self.target_entry.bind('<FocusOut>', lambda e: self.validate_and_save_target())
        
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
        
        sync_all_btn = ttk.Button(btn_frame, text="一键全同步", command=self.sync_all)
        sync_all_btn.pack(side='left', padx=5)
        
        create_link_btn = ttk.Button(btn_frame, text="创建软链接", command=self.create_symlink)
        create_link_btn.pack(side='left', padx=5)
        
        download_meta_btn = ttk.Button(btn_frame, text="下载元数据", command=self.download_metadata)
        download_meta_btn.pack(side='left', padx=5)
        
        copy_version_btn = ttk.Button(btn_frame, text="复制到剪贴版")
        copy_version_btn.pack(side='left', padx=5)
        
        def clear_list():
            self.link_text.delete('1.0', tk.END)
            self.save_config()
            self.logger.info("已清空文件夹列表")
            
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
        
    def on_text_modified(self):
        """处理文本修改事件"""
        if self.link_text.edit_modified():
            self.save_config()
            self.link_text.edit_modified(False)

    def sync_all(self):

        link_folders = self.config.get('export_symlink', 'link_folders')
        target_folder = self.config.get('export_symlink', 'target_folder')
        num_threads = self.config.get('export_symlink', 'thread_count')
        allowed_extensions = tuple(self.config.get('export_symlink', 'meta_suffixes')) 
        soft_link_extensions = tuple(self.config.get('export_symlink', 'link_suffixes')) 

        # 获取路径列表
        if not link_folders or not link_folders[0]:
            self.logger.info("提示", "源目录路径列表为空")
            return
                
        total_time = 0
        total_copied = 0
        total_existing = 0

        self.logger.info("开始一键全同步")

        # 处理每个源文件夹
        for source_path in link_folders:
            if not source_path.strip():
                continue
                
            copyer = MetadataCopyer(
                source_folder=source_path.strip(),
                target_folder=target_folder,
                allowed_extensions=allowed_extensions,
                num_threads=num_threads,
                logger=self.logger  # 传递logger
            )
            
            # 运行元数据复制
            time_taken, message = copyer.run()
            total_time += time_taken
            total_copied += copyer.copied_metadatas
            total_existing += copyer.existing_links
        
        # 显示总结信息
        summary = (
            f"元数据同步完成\n"
            f"总耗时: {total_time:.2f} 秒\n"
            f"总处理文件数: {total_copied + total_existing}\n"
            f"新复制文件数: {total_copied}\n"
            f"跳过文件数: {total_existing}"
        )

        self.logger.info(summary)

        total_time = 0
        total_created_links = 0

        # 每个源文件夹创建符号链接
        for source_path in link_folders:
            if not source_path.strip():
                continue
                
            creater = SymlinkCreator(
                source_folder=source_path.strip(),
                target_folder=target_folder,
                allowed_extensions=soft_link_extensions,
                num_threads=num_threads,
                logger=self.logger  # 传递logger
            )
            
            # 运行符号链接创建
            time_taken, message = creater.run()
            total_time += time_taken
            total_created_links += creater.created_links
        
        # 显示总结信息
        summary = (
            f"符号链接创建完成\n"
            f"总耗时: {total_time:.2f} 秒\n"
            f"总创建符号链接文件数: {total_created_links}\n"
        )
        self.logger.info(summary)


        self.logger.info("一键全同步完成")

    def create_symlink(self):
        link_folders = self.config.get('export_symlink', 'link_folders')
        target_folder = self.config.get('export_symlink', 'target_folder')
        num_threads = self.config.get('export_symlink', 'thread_count')
        soft_link_extensions = tuple(self.config.get('export_symlink', 'link_suffixes')) 

        # 获取路径列表
        if not link_folders or not link_folders[0]:
            self.logger.info("提示", "源目录路径列表为空")
            return

        total_time = 0
        total_created_links = 0

        self.logger.info("开始创建软链接")

        # 每个源文件夹创建符号链接
        for source_path in link_folders:
            if not source_path.strip():
                continue
                
            creater = SymlinkCreator(
                source_folder=source_path.strip(),
                target_folder=target_folder,
                allowed_extensions=soft_link_extensions,
                num_threads=num_threads,
                logger=self.logger  # 传递logger
            )
            
            # 运行符号链接创建
            time_taken, message = creater.run()
            total_time += time_taken
            total_created_links += creater.created_links
        
        # 显示总结信息
        summary = (
            f"符号链接创建完成\n"
            f"总耗时: {total_time:.2f} 秒\n"
            f"总创建符号链接文件数: {total_created_links}\n"
        )
        self.logger.info(summary)

        self.logger.info("创建软链接完成")

    def download_metadata(self):
        link_folders = self.config.get('export_symlink', 'link_folders')
        target_folder = self.config.get('export_symlink', 'target_folder')
        num_threads = self.config.get('export_symlink', 'thread_count')
        allowed_extensions = tuple(self.config.get('export_symlink', 'meta_suffixes')) 

        # 获取路径列表
        if not link_folders or not link_folders[0]:
            self.logger.info("提示", "源目录路径列表为空")
            return

        total_time = 0
        total_copied = 0
        total_existing = 0

        self.logger.info("开始下载元数据")

        # 处理每个源文件夹
        for source_path in link_folders:
            if not source_path.strip():
                continue
                
            copyer = MetadataCopyer(
                source_folder=source_path.strip(),
                target_folder=target_folder,
                allowed_extensions=allowed_extensions,
                num_threads=num_threads,
                logger=self.logger  # 传递logger
            )
            
            # 运行元数据复制
            time_taken, message = copyer.run()
            total_time += time_taken
            total_copied += copyer.copied_metadatas
            total_existing += copyer.existing_links
        
        # 显示总结信息
        summary = (
            f"元数据下载完成\n"
            f"总耗时: {total_time:.2f} 秒\n"
            f"总处理文件数: {total_copied + total_existing}\n"
            f"新复制文件数: {total_copied}\n"
            f"跳过文件数: {total_existing}"
        )
        self.logger.info(summary)

        self.logger.info("下载元数据完成")
