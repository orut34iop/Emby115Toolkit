#!/usr/bin/env python3
"""
Emby115Toolkit - macOS 专用版本
基于 tkinter，包含 macOS 兼容性修复

修复内容：
- 窗口最大化使用 geometry 替代 fullscreen
- 移除管理员权限检查（macOS 不需要）
- 修复路径处理问题

使用方法：
    python main_mac.py

注意：此版本不包含拖拽功能（tkinterdnd2 在 macOS 上不可用）
      如需拖拽功能，请使用 PyQt5 版本: python qt_main.py
"""

import tkinter as tk
from tkinter import ttk
import os
import sys
import platform
from tabs import (
    ExportSymlinkTab,
    ManipulateFolderTab,
    CheckDuplicateTab,
    MergeFilesTab,
    MergeVersionTab,
    UpdateGenresTab,
    Mirror115TreeTab
)
from utils.logger import setup_logger
from utils.config import Config


class EmbyToolkit:
    """主应用类 - macOS 兼容版本"""

    def __init__(self, root):
        self.root = root
        self.root.title("Emby115Toolkit - macOS Edition")

        # 创建日志目录
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)

        # 设置日志记录器
        self.logger = setup_logger('EmbyToolkit', log_file=os.path.join(self.log_dir, 'app.log'))
        self.logger.info("应用程序启动 (macOS 版本)")

        # 创建选项卡控件
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)

        # 创建各个选项卡
        self.tabs = {
            "导出软链接": ttk.Frame(self.notebook),
            "文件夹操作": ttk.Frame(self.notebook),
            "emby影剧查重": ttk.Frame(self.notebook),
            "文件合并": ttk.Frame(self.notebook),
            "emby合并版本": ttk.Frame(self.notebook),
            "emby更新流派": ttk.Frame(self.notebook),
            "115目录树镜像": ttk.Frame(self.notebook)
        }

        # 添加选项卡到 notebook
        for tab_name, tab_frame in self.tabs.items():
            self.notebook.add(tab_frame, text=tab_name)
            self.logger.info(f"添加选项卡: {tab_name}")

        # 设置窗口大小和位置
        self.root.geometry("800x600")
        self.root.minsize(800, 600)

        # 初始化各个选项卡的内容
        self.init_tabs()

        # 读取上次退出时的选项卡索引
        self.config = Config()
        last_tab_index = self.config.get('last_tab_index', 'index', 0)
        self.notebook.select(last_tab_index)

        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def init_tabs(self):
        """初始化所有标签页"""
        ExportSymlinkTab(self.tabs["导出软链接"], self.log_dir)
        ManipulateFolderTab(self.tabs["文件夹操作"], self.log_dir)
        CheckDuplicateTab(self.tabs["emby影剧查重"], self.log_dir)
        MergeFilesTab(self.tabs["文件合并"], self.log_dir)
        MergeVersionTab(self.tabs["emby合并版本"], self.log_dir)
        UpdateGenresTab(self.tabs["emby更新流派"], self.log_dir)
        Mirror115TreeTab(self.tabs["115目录树镜像"], self.log_dir)
        self.logger.info("所有选项卡初始化完成")

    def on_tab_changed(self, event):
        """处理选项卡切换事件"""
        selected_tab_index = self.notebook.index(self.notebook.select())
        self.config.set('last_tab_index', 'index', selected_tab_index)
        self.config.save()


def force_exit():
    """强制退出"""
    try:
        root.destroy()
        sys.exit(0)
    except SystemExit:
        os._exit(0)


def maximize_window(root):
    """
    macOS 窗口最大化
    使用 geometry 设置窗口大小并居中，而不是使用 fullscreen
    """
    system = platform.system().lower()
    if system == 'windows':
        root.state('zoomed')
    elif system == 'linux':
        root.attributes('-zoomed', True)
    else:  # macOS
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        width = int(screen_width * 0.8)
        height = int(screen_height * 0.8)
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        root.geometry(f"{width}x{height}+{x}+{y}")


def main():
    """主函数"""
    global root
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")

    # 设置最小窗口大小
    root.minsize(800, 600)

    # macOS 窗口最大化
    maximize_window(root)

    app = EmbyToolkit(root)
    root.protocol("WM_DELETE_WINDOW", force_exit)
    root.mainloop()


if __name__ == "__main__":
    main()
