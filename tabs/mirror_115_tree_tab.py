import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from autosync.TreeMirror import TreeMirror

class Mirror115TreeTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("115目录树镜像标签页初始化完成")
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('mirror_115_tree')
        if config:
            # 加载目标文件
            if 'tree_file' in config:
                tree_file = config['tree_file']
                if not tree_file and tree_file != '':
                    tree_file = os.path.normpath(tree_file)
                self.tree_file_entry.delete(0, tk.END)
                self.tree_file_entry.insert(0, tree_file)
                self.logger.info(f"加载115目录树文件: {tree_file}")
            
            # 加载导出目录
            if 'export_folder' in config:
                export_folder = config['export_folder']
                if not export_folder and export_folder != '':
                    export_folder = os.path.normpath(export_folder)
                self.export_folder_entry.delete(0, tk.END)
                self.export_folder_entry.insert(0, export_folder)
                self.logger.info(f"加载导出镜像文件夹: {export_folder}")
            
            # 加载修复乱码设置
            if 'fix_garbled_text' in config:
                self.fix_garbled_var.set(config['fix_garbled_text'])
                self.logger.info(f"加载乱码修复设置: {config['fix_garbled_text']}")

    def save_config(self):
        """保存当前设置到配置文件"""
        # 更新配置
        tree_file = self.tree_file_entry.get().strip()
        if not tree_file and tree_file != '':
            tree_file = os.path.normpath(tree_file) # 规范化路径
        self.config.set('mirror_115_tree', 'tree_file', tree_file)
    
        export_folder = self.export_folder_entry.get().strip()
        if not export_folder and export_folder != '':
            export_folder = os.path.normpath(export_folder) # 规范化路径
        self.config.set('mirror_115_tree', 'export_folder', export_folder)
    
        self.config.set('mirror_115_tree', 'fix_garbled_text', bool(self.fix_garbled_var.get()))
        
        # 保存到文件
        self.config.save()
        self.logger.info("配置已保存")

    def validate_target_folder(self, path):
        """验证目标文件路径"""
        path = path.strip()
        if not path:
            return True
        if not os.path.exists(path):
            self.logger.warning("无效的文件路径")
            return False
        if not os.path.isfile(path):
            self.logger.warning("所选路径不是文件")
            return False
        return True
        
    def init_ui(self):
        # 使用说明
        desc_label = ttk.Label(self.frame, text="使用说明: 选择或拖拽115导出的目录树文件到输入框即可创建目录树镜像")
        desc_label.pack(fill='x', padx=5, pady=5)
        
        # 目录树文件选择
        tree_frame = ttk.LabelFrame(self.frame, text="115目录树文件", padding=(5, 5, 5, 5))
        tree_frame.pack(fill='x', padx=5, pady=5)
        
        self.tree_file_entry = ttk.Entry(tree_frame)
        self.tree_file_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        # 启用拖放功能
        self.tree_file_entry.drop_target_register(DND_FILES)
        self.tree_file_entry.dnd_bind('<<Drop>>', lambda e: self.on_tree_file_drop(e))
        
        def browse_tree_file():
            file_path = filedialog.askopenfilename(
                title="选择115目录树文件",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if file_path:
                if not file_path and file_path != '':
                    file_path = os.path.normpath(file_path)
                self.tree_file_entry.delete(0, tk.END)
                self.tree_file_entry.insert(0, file_path)
                self.logger.info(f"已选择115目录树文件: {file_path}")
                self.save_config()
        
        tree_browse = ttk.Button(tree_frame, text="浏览", command=browse_tree_file)
        tree_browse.pack(side='right', padx=5)
        
        # 导出镜像文件夹选择
        export_frame = ttk.LabelFrame(self.frame, text="导出镜像文件夹", padding=(5, 5, 5, 5))
        export_frame.pack(fill='x', padx=5, pady=5)
        
        self.export_folder_entry = ttk.Entry(export_frame)
        self.export_folder_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        # 启用拖放功能
        self.export_folder_entry.drop_target_register(DND_FILES)
        self.export_folder_entry.dnd_bind('<<Drop>>', lambda e: self.on_export_folder_drop(e))
        
        def browse_export():
            folder = filedialog.askdirectory(title="选择导出镜像文件夹")
            if folder:
                self.export_folder_entry.delete(0, tk.END)
                self.export_folder_entry.insert(0, folder)
                self.logger.info(f"已选择导出镜像文件夹: {folder}")
                self.save_config()
        
        export_browse = ttk.Button(export_frame, text="浏览", command=browse_export)
        export_browse.pack(side='right', padx=5)

        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        mirror_tree_btn = ttk.Button(btn_frame, text="创建镜像", command=self.mirror_tree)
        mirror_tree_btn.pack(side='left', padx=5)

        # 添加修复乱码勾选框
        self.fix_garbled_var = tk.BooleanVar(value=False)
        
        # 创建勾选框样式
        style = ttk.Style()
        style.configure(
            "Check.TCheckbutton",
            indicatorrelief='flat',
            indicatorcolor='#32CD32',
            indicatordiameter=20,
            font=('Segoe UI', 9)
        )
        style.map(
            "Check.TCheckbutton",
            background=[('active', '#f0f0f0')],
            indicatorcolor=[('selected', '#32CD32'),
                          ('pressed', '#228B22')]
        )
        
        fix_garbled_check = ttk.Checkbutton(
            btn_frame, 
            text="尝试修复异常乱码字符的目录名/文件名",
            variable=self.fix_garbled_var,
            command=self.on_fix_garbled_change,
            style="Check.TCheckbutton",
            takefocus=False
        )
        fix_garbled_check.pack(side='left', padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(self.frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'mirror_115_tree.log')
        self.logger = setup_logger('mirror_115_tree', self.log_text, log_file)
        
    def on_tree_file_drop(self, event):
        """处理目录树文件拖放事件"""
        data = event.data
        if data:
            paths = self.scan_string(data)
            if paths:
                path = paths[0].strip()  # 只取第一个路径
                if os.path.exists(path) and os.path.isfile(path):
                    self.tree_file_entry.delete(0, tk.END)
                    self.tree_file_entry.insert(0, path)
                    self.logger.info(f"已设置115目录树文件: {path}")
                    self.save_config()
                else:
                    self.logger.warning("无效的文件路径")

    def on_export_folder_drop(self, event):
        """处理导出文件夹拖放事件"""
        data = event.data
        if data:
            paths = self.scan_string(data)
            if paths:
                path = paths[0].strip()  # 只取第一个路径
                if os.path.exists(path) and os.path.isdir(path):
                    self.export_folder_entry.delete(0, tk.END)
                    self.export_folder_entry.insert(0, path)
                    self.logger.info(f"已设置导出镜像文件夹: {path}")
                    self.save_config()
                else:
                    self.logger.warning("无效的文件夹路径")

    def validate_and_save_target(self):
        """验证并保存目标文件路径"""
        path = self.target_entry.get().strip()
        if self.validate_target_folder(path):
            self.save_config()

    def on_fix_garbled_change(self):
        """处理修复乱码设置变化"""
        self.save_config()
        self.logger.info(f"乱码修复功能已{'开启' if self.fix_garbled_var.get() else '关闭'}")

    def mirror_tree(self):
        """镜像目录树"""
        tree_file = self.tree_file_entry.get().strip()
        export_folder = self.export_folder_entry.get().strip()
        fix_garbled = self.fix_garbled_var.get()

        # 验证路径
        if not tree_file or not export_folder:
            self.logger.info("提示: 目录树文件或导出文件夹路径为空")
            return

        if not os.path.isfile(tree_file):
            self.logger.error("无效的115目录树文件")
            return

        if not os.path.isdir(export_folder):
            self.logger.error("无效的导出镜像文件夹")
            return

        self.logger.info(f"开始创建目录树镜像")
        self.logger.info(f"目录树文件: {tree_file}")
        self.logger.info(f"导出目录: {export_folder}")
        self.logger.info(f"乱码修复功能: {'开启' if fix_garbled else '关闭'}")

        mirror = TreeMirror(
            tree_file=tree_file,
            export_folder=export_folder,
            fix_garbled=fix_garbled,
            logger=self.logger
        )

        # 运行目录树镜像创建
        time_taken, message = mirror.run()
        
        # 显示总结信息
        summary = (
            f"目录树镜像创建完成\n"
            f"总耗时: {time_taken:.2f} 秒\n"
        )
        self.logger.info(summary)