import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
from tkinterdnd2 import TkinterDnD
import os
from tabs import (
    ExportSymlinkTab,
    DeleteSymlinkTab,
    CheckDuplicateTab,
    MergeFilesTab,
    ExportLibraryTab,
    MergeVersionTab,
    UpdateCategoryTab
)
from utils.logger import setup_logger  # 导入日志设置函数
from utils.config import Config  # 导入配置管理类

class EmbyToolkit:
    def __init__(self, root):
        self.root = root
        self.root.title("Emby115Toolkit")
        
        # 创建日志目录
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 设置日志记录器
        self.logger = setup_logger('EmbyToolkit', log_file=os.path.join(self.log_dir, 'app.log'))
        self.logger.info("应用程序启动")
        
        # 创建选项卡控件
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # 创建各个选项卡
        self.tabs = {
            "导出软链接": ttk.Frame(self.notebook),
            "删除软链接": ttk.Frame(self.notebook),
            "emby影剧查重": ttk.Frame(self.notebook),
            "文件合并": ttk.Frame(self.notebook),
            "导出库文件": ttk.Frame(self.notebook),
            "emby合并版本": ttk.Frame(self.notebook),
            "emby更新流派": ttk.Frame(self.notebook)
        }
        
        # 添加选项卡到notebook
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
        last_tab_index = self.config.get('last_tab_index','index', 0)
        self.notebook.select(last_tab_index)

        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def init_tabs(self):
        """初始化所有标签页"""
        # 为每个标签页创建对应的类实例
        ExportSymlinkTab(self.tabs["导出软链接"], self.log_dir)
        DeleteSymlinkTab(self.tabs["删除软链接"], self.log_dir)
        CheckDuplicateTab(self.tabs["emby影剧查重"], self.log_dir)
        MergeFilesTab(self.tabs["文件合并"], self.log_dir)
        ExportLibraryTab(self.tabs["导出库文件"], self.log_dir)
        MergeVersionTab(self.tabs["emby合并版本"], self.log_dir)
        UpdateCategoryTab(self.tabs["emby更新流派"], self.log_dir)
        self.logger.info("所有选项卡初始化完成")

    def on_tab_changed(self, event):
        """处理选项卡切换事件"""
        selected_tab_index = self.notebook.index(self.notebook.select())
        self.config.set('last_tab_index', 'index', selected_tab_index)
        self.config.save()

def main():
    root = TkinterDnD.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")  # 使用clam主题，因为不能同时使用ThemedTk
    app = EmbyToolkit(root)
    root.mainloop()

if __name__ == "__main__":
    main()
