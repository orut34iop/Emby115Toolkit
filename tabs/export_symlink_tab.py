import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
import ctypes
import sys
import threading
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
            
            # 加载文件操作时间间隔
            if 'op_interval_sec' in config:
                self.op_interval_spinbox.set(config['op_interval_sec'])
                self.logger.info(f"加载文件操作时间间隔(秒): {config['op_interval_sec']}")

            # 加载目标文件夹
            if 'target_folder' in config:
                target_folder = config['target_folder']
                if not target_folder and target_folder != '':  # 空字符串也是有效路径
                    target_folder = os.path.normpath(target_folder)

                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, target_folder)
                self.logger.info(f"加载目标文件夹: {target_folder}")
            
            # 加载链接文件夹列表
            if 'link_folders' in config and config['link_folders']:
                # 规范化每个链接文件夹路径
                normalized_link_folders = [os.path.normpath(path) for path in config['link_folders']]
                self.link_text.delete('1.0', tk.END)
                self.link_text.insert('1.0', '\n'.join(normalized_link_folders))
                self.logger.info(f"加载链接文件夹列表: {normalized_link_folders}")
            
            # 加载后缀设置
            if 'link_suffixes' in config:
                self.link_suffix_entry.delete(0, tk.END)
                self.link_suffix_entry.insert(0, ';'.join(config['link_suffixes']))
                self.logger.info(f"加载软链接后缀: {config['link_suffixes']}")
            
            if 'meta_suffixes' in config:
                self.meta_suffix_entry.delete(0, tk.END)
                self.meta_suffix_entry.insert(0, ';'.join(config['meta_suffixes']))
                self.logger.info(f"加载元数据后缀: {config['meta_suffixes']}")
            
            # 加载115防封设置
            if 'enable_115_protect' in config:
                self.protect_115_var.set(config['enable_115_protect'])
                self.logger.info(f"加载115防封设置: {config['enable_115_protect']}")
            
            # 加载替换文件路径设置
            if 'replace_file_path' in config:
                self.replace_path_var.set(config['replace_file_path'])
                self.logger.info(f"加载替换文件路径设置: {config['replace_file_path']}")
            
            # 加载原路径和替换路径
            if 'original_path' in config:
                self.original_path_entry.delete(0, tk.END)
                self.original_path_entry.insert(0, config['original_path'])
                self.logger.info(f"加载原路径: {config['original_path']}")
            
            if 'replace_path' in config:
                self.replace_path_entry.delete(0, tk.END)
                self.replace_path_entry.insert(0, config['replace_path'])
                self.logger.info(f"加载替换路径: {config['replace_path']}")
    
    def save_config(self):
        """保存当前设置到配置文件"""
        # 获取链接文件夹列表
        link_folders = [
            os.path.normpath(source_path.strip()) # 规范化路径
            for source_path in self.link_text.get('1.0', tk.END).strip().split('\n') 
            if source_path.strip()
        ]
        
        # 获取后缀列表
        link_suffixes = [suffix.strip() for suffix in self.link_suffix_entry.get().split(';') if suffix.strip()]
        meta_suffixes = [suffix.strip() for suffix in self.meta_suffix_entry.get().split(';') if suffix.strip()]
        
        # 更新配置
        self.config.set('export_symlink', 'link_folders', link_folders)
        target_folder = self.target_entry.get().strip()
        if not target_folder and target_folder != '':
            target_folder = os.path.normpath(target_folder) # 规范化路径

        self.config.set('export_symlink', 'target_folder', target_folder)
        self.config.set('export_symlink', 'thread_count', int(self.thread_spinbox.get()))
        self.config.set('export_symlink', 'op_interval_sec', int(self.op_interval_spinbox.get()))
        self.config.set('export_symlink', 'link_suffixes', link_suffixes)
        self.config.set('export_symlink', 'meta_suffixes', meta_suffixes)
        self.config.set('export_symlink', 'enable_115_protect', bool(self.protect_115_var.get()))
        self.config.set('export_symlink', 'replace_file_path', bool(self.replace_path_var.get()))
        self.config.set('export_symlink', 'original_path', self.original_path_entry.get().strip())
        self.config.set('export_symlink', 'replace_path', self.replace_path_entry.get().strip())
        
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
                #规范化路径
                folder = os.path.normpath(folder)
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, folder)
                self.logger.info(f"已选择目标文件夹: {folder}")
                self.save_config()
        
        target_browse = ttk.Button(target_frame, text="浏览", command=browse_target)
        target_browse.pack(side='right', padx=5)
        
        # 添加替换文件路径设置框架
        replace_path_frame = ttk.LabelFrame(self.frame, text="文件路径替换设置", padding=(5, 5, 5, 5))
        replace_path_frame.pack(fill='x', padx=5, pady=5)
        
        # 替换文件路径勾选框和输入框的容器
        replace_path_container = ttk.Frame(replace_path_frame)
        replace_path_container.pack(fill='x', padx=5, pady=2)
        
        self.replace_path_var = tk.BooleanVar(value=False)
        replace_path_check = ttk.Checkbutton(
            replace_path_container, 
            text="替换文件路径",
            variable=self.replace_path_var,
            command=self.on_replace_path_change,
            style="Check.TCheckbutton",
            takefocus=False
        )
        replace_path_check.pack(side='left', padx=(0, 20))

        # 原路径输入框 - 在勾选框右侧
        ttk.Label(replace_path_container, text="原路径:").pack(side='left', padx=(0, 5))
        self.original_path_entry = ttk.Entry(replace_path_container, width=35)
        self.original_path_entry.pack(side='left', padx=(0, 20))
        
        # 替换路径输入框 - 在原路径输入框右侧
        ttk.Label(replace_path_container, text="替换路径:").pack(side='left', padx=(0, 5))
        self.replace_path_entry = ttk.Entry(replace_path_container, width=35)
        self.replace_path_entry.pack(side='left')

        # 绑定输入框的FocusOut事件来保存配置
        self.original_path_entry.bind('<FocusOut>', lambda e: self.save_config())
        self.replace_path_entry.bind('<FocusOut>', lambda e: self.save_config())

        # 验证目标文件夹
        self.target_entry.bind('<FocusOut>', lambda e: self.validate_and_save_target())
        
        # 115防封和时间间隔设置 - 使用LabelFrame包装
        protect_frame = ttk.LabelFrame(self.frame, text="115防封设置", padding=(5, 5, 5, 5))
        protect_frame.pack(fill='x', padx=5, pady=5)
        
        # 115防封设置容器
        protect_container = ttk.Frame(protect_frame)
        protect_container.pack(fill='x', padx=5, pady=2)
        
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
            protect_container, 
            text="开启115 防封",
            variable=self.protect_115_var,
            command=self.save_config,
            style="Check.TCheckbutton",
            takefocus=False  # 禁用焦点
        )
        protect_115_check.pack(side='left', padx=5)

        # 文件操作时间间隔设置
        op_interval_label = ttk.Label(protect_container, text="文件操作时间间隔(秒):")
        op_interval_label.pack(side='left', padx=5)
        
        self.op_interval_spinbox = ttk.Spinbox(
            protect_container, from_=0, to=60, width=10, command=self.save_config, state='readonly'
        )
        self.op_interval_spinbox.set(4)  # 默认值为4秒
        self.op_interval_spinbox.pack(side='left', padx=5)
        self.op_interval_spinbox.bind('<FocusOut>', lambda e: self.save_config())

        # 创建同步设置框架
        sync_settings_frame = ttk.LabelFrame(self.frame, text="同步设置", padding=(5, 5, 5, 5))
        sync_settings_frame.pack(fill='x', padx=5, pady=5)
        
        # 同步线程数设置
        thread_container = ttk.Frame(sync_settings_frame)
        thread_container.pack(fill='x', padx=5, pady=2)
        
        thread_label = ttk.Label(thread_container, text="同步线程数:")
        thread_label.pack(side='left', padx=5)
        
        self.thread_spinbox = ttk.Spinbox(thread_container, from_=1, to=16, width=10)
        self.thread_spinbox.set(4)  # 默认值
        self.thread_spinbox.pack(side='left', padx=5)
        self.thread_spinbox.bind('<FocusOut>', lambda e: self.save_config())

        # 后缀设置容器
        suffix_container = ttk.Frame(sync_settings_frame)
        suffix_container.pack(fill='x', padx=5, pady=2)
        
        # 软链接后缀
        link_suffix_label = ttk.Label(suffix_container, text="软链接后缀:")
        link_suffix_label.pack(side='left', padx=5)
        
        self.link_suffix_entry = ttk.Entry(suffix_container)
        self.link_suffix_entry.insert(0, ".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm")
        self.link_suffix_entry.pack(side='left', fill='x', expand=True, padx=5)
        self.link_suffix_entry.bind('<FocusOut>', lambda e: self.save_config())
        
        # 元数据后缀
        meta_suffix_label = ttk.Label(suffix_container, text="元数据后缀:")
        meta_suffix_label.pack(side='left', padx=5)
        
        self.meta_suffix_entry = ttk.Entry(suffix_container)
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
        
        def clear_list():
            self.link_text.delete('1.0', tk.END)
            self.save_config()
            self.logger.info("已清空文件夹列表")
            
        clear_list_btn = ttk.Button(btn_frame, text="清空文件夹列表", command=clear_list)
        clear_list_btn.pack(side='left', padx=5)
        
        # 日志区域
        self.log_frame, self.log_text = self.create_log_frame(self.frame)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)

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
        """执行全同步操作:下载元数据和创建软链接"""
        try:
            # 检查管理员权限
            if not self.is_admin():
                self.logger.info("需要管理员权限，正在切换到管理员权限...")
                self.run_as_admin()
                return

            # 获取配置
            config = self.validate_sync_config()
            if not config:
                return

            source_folders, target_folder, num_threads, allowed_extensions, enable_115_protect, op_interval_sec, replace_file_path = config

            # 开始同步流程
            self.logger.info("=== 开始全同步操作 ===")
            self.logger.info(f"源文件夹: {source_folders}")
            self.logger.info(f"目标文件夹: {target_folder}")
            self.logger.info(f"线程数: {num_threads}")
            self.logger.info(f"允许的扩展名: {allowed_extensions}")
            self.logger.info(f"115防封选项: {enable_115_protect}")
            self.logger.info(f"文件操作间隔时间(秒): {op_interval_sec}")
            self.logger.info(f"替换文件路径选项: {replace_file_path}")
        
            # 创建元数据复制器
            copyer = MetadataCopyer(
                source_folders=source_folders,
                target_folder=target_folder,
                allowed_extensions=allowed_extensions,
                num_threads=num_threads,
                enable_115_protect=enable_115_protect,
                op_interval_sec = op_interval_sec,
                logger=self.logger
            )

            def on_sync_all_complete(message):
                """元数据下载完成后的回调"""
                self.logger.info("=== 元数据下载完成 ===")
                self.logger.info(message)
                self.create_symlink()  # 继续创建软链接

            # 运行元数据复制
            copyer.run(on_sync_all_complete)

        except Exception as e:
            self.logger.error(f"全同步操作发生错误: {str(e)}")
        
    def validate_sync_config(self):
        """验证同步配置"""
        source_folders = self.config.get('export_symlink', 'link_folders')
        target_folder = self.config.get('export_symlink', 'target_folder')
        num_threads = self.config.get('export_symlink', 'thread_count')
        allowed_extensions = tuple(self.config.get('export_symlink', 'meta_suffixes'))
        enable_115_protect = self.config.get('export_symlink', 'enable_115_protect')
        op_interval_sec = self.config.get('export_symlink', 'op_interval_sec')
        replace_file_path = self.config.get('export_symlink', 'replace_file_path')

        # 验证源文件夹
        if not source_folders or not source_folders[0]:
            self.logger.error("错误: 源目录路径列表为空")
            return None

        # 验证目标文件夹
        if not target_folder:
            self.logger.error("错误: 目标文件夹未设置")
            return None
            
        # 验证目标文件夹是否存在
        if not os.path.exists(target_folder):
            self.logger.error(f"错误: 目标文件夹不存在: {target_folder}")
            return None

        return source_folders, target_folder, num_threads, allowed_extensions, enable_115_protect,op_interval_sec, replace_file_path

    def create_symlink(self):
        source_folders = self.config.get('export_symlink', 'link_folders')
        target_folder = self.config.get('export_symlink', 'target_folder')
        num_threads = self.config.get('export_symlink', 'thread_count')
        soft_link_extensions = tuple(self.config.get('export_symlink', 'link_suffixes')) 
        enable_115_protect = self.config.get('export_symlink', 'enable_115_protect')
        op_interval_sec = self.config.get('export_symlink', 'op_interval_sec')

        # 获取路径列表
        if not source_folders or not source_folders[0]:
            self.logger.info("提示", "源目录路径列表为空")
            return

        if not self.is_admin():
            self.logger.info("需要管理员权限，正在切换到管理员权限...")
            self.run_as_admin()
            return

        self.logger.info("开始创建软链接")

        creater = SymlinkCreator(
            source_folders=source_folders,
            target_folder=target_folder,
            allowed_extensions=soft_link_extensions,
            num_threads=num_threads,
			enable_115_protect = enable_115_protect,
            op_interval_sec = op_interval_sec,
            logger=self.logger  # 传递logger
        )

        def on_create_symlink_complete(message):
            self.logger.info(message)

        # 运行元数据复制
        creater.run(on_create_symlink_complete)


 

    def is_admin(self):
        """检查是否为管理员权限"""
        try:
            #如果当前处于调试模式下,不切换管理员模式
            if sys.gettrace():
                return True
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def run_as_admin(self):
        """以管理员权限重新运行"""
        # params = ' '.join([f'"{arg}"' if ' ' in arg else arg for arg in sys.argv])
        # ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        # return False
        sys.exit()

    def download_metadata(self):
        source_folders = self.config.get('export_symlink', 'link_folders')
        target_folder = self.config.get('export_symlink', 'target_folder')
        num_threads = self.config.get('export_symlink', 'thread_count')
        allowed_extensions = tuple(self.config.get('export_symlink', 'meta_suffixes')) 
        enable_115_protect = self.config.get('export_symlink', 'enable_115_protect')
        op_interval_sec = self.config.get('export_symlink', 'op_interval_sec')

        # 获取路径列表
        if not source_folders or not source_folders[0]:
            self.logger.info("提示", "源目录路径列表为空")
            return



        self.logger.info("开始下载元数据")
    
        copyer = MetadataCopyer(
            source_folders=source_folders,
            target_folder=target_folder,
            allowed_extensions=allowed_extensions,
            num_threads=num_threads,
            enable_115_protect = enable_115_protect,
            op_interval_sec = op_interval_sec,
            logger=self.logger  # 传递logger
        )

        def on_download_metadata_complete(message):
            self.logger.info(message)

        # 运行元数据复制
        copyer.run(on_download_metadata_complete)

    def on_replace_path_change(self):
        """处理替换文件路径设置变化"""
        self.save_config()
        self.logger.info(f"替换文件路径功能已{'开启' if self.replace_path_var.get() else '关闭'}")
