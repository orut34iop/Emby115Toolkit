import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os
from .base_tab import BaseTab
from utils.logger import setup_logger
from utils.config import Config
from autosync.SymlinkDeleter import SymlinkDeleter

class DeleteSymlinkTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.config = Config()
        self.init_ui()
        self.load_config()
        self.logger.info("删除软链接标签页初始化完成")
        
    def load_config(self):
        """从配置文件加载设置"""
        config = self.config.get('delete_symlink')
        if config:
            # 加载目标文件夹
            if 'target_folder' in config:
                target_folder = config['target_folder']
                target_folder = os.path.normpath(target_folder)
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, target_folder)
                self.logger.info(f"加载目标文件夹: {target_folder}")
    
    def save_config(self):
        """保存当前设置到配置文件"""
        # 更新配置
        target_folder = self.target_entry.get().strip()
        target_folder = os.path.normpath(target_folder) # 规范化路径
        self.config.set('delete_symlink', 'target_folder', target_folder)
        
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
        desc_label = ttk.Label(self.frame, text="使用说明: 选择或拖拽文件夹到输入框即可删除软链接")
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
                folder = os.path.normpath(folder)
                self.target_entry.delete(0, tk.END)
                self.target_entry.insert(0, folder)
                self.logger.info(f"已选择目标文件夹: {folder}")
                self.save_config()
        
        target_browse = ttk.Button(target_frame, text="浏览", command=browse_target)
        target_browse.pack(side='right', padx=5)
        
        # 验证目标文件夹
        self.target_entry.bind('<FocusOut>', lambda e: self.validate_and_save_target())
        
        # 操作按钮组
        btn_frame = ttk.LabelFrame(self.frame, text="操作", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        delete_symlink_btn = ttk.Button(btn_frame, text="删除软链接", command=self.delete_symlink)
        delete_symlink_btn.pack(side='left', padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(self.frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'delete_symlink.log')
        self.logger = setup_logger('delete_symlink', self.log_text, log_file)
        self.logger.info("删除软链接标签页初始化完成")
        
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

    def delete_symlink(self):
        target_folder = self.config.get('delete_symlink', 'target_folder')

        # 获取路径
        if not target_folder:
            self.logger.info("提示", "目标文件夹路径为空")
            return

        self.logger.info(f"开始删除软链接: {target_folder}")

        deleter = SymlinkDeleter(
            target_folder=target_folder,
            logger=self.logger  # 传递logger
        )

        # 运行软链接删除
        time_taken, message = deleter.run()
        
        # 显示总结信息
        summary = (
            f"删除软链接完成\n"
            f"总耗时: {time_taken:.2f} 秒\n"
        )
        self.logger.info(summary)

