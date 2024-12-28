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

class EmbyToolkit:
    def __init__(self, root):
        self.root = root
        self.root.title("Emby115Toolkit")
        
        # 创建日志目录
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建选项卡控件
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # 创建各个选项卡
        self.tabs = {
            "导出软链接": ttk.Frame(self.notebook),
            "删除软链接": ttk.Frame(self.notebook),
            "检查去重": ttk.Frame(self.notebook),
            "文件合并": ttk.Frame(self.notebook),
            "导出库文件": ttk.Frame(self.notebook),
            "合并版本": ttk.Frame(self.notebook),
            "更新类别": ttk.Frame(self.notebook)
        }
        
        # 添加选项卡到notebook
        for tab_name, tab_frame in self.tabs.items():
            self.notebook.add(tab_frame, text=tab_name)
            
        # 设置窗口大小和位置
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # 初始化各个选项卡的内容
        self.init_tabs()

    def init_tabs(self):
        """初始化所有标签页"""
        # 为每个标签页创建对应的类实例
        ExportSymlinkTab(self.tabs["导出软链接"], self.log_dir)
        DeleteSymlinkTab(self.tabs["删除软链接"], self.log_dir)
        CheckDuplicateTab(self.tabs["检查去重"], self.log_dir)
        MergeFilesTab(self.tabs["文件合并"], self.log_dir)
        ExportLibraryTab(self.tabs["导出库文件"], self.log_dir)
        MergeVersionTab(self.tabs["合并版本"], self.log_dir)
        UpdateCategoryTab(self.tabs["更新类别"], self.log_dir)

def main():
    root = TkinterDnD.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")  # 使用clam主题，因为不能同时使用ThemedTk
    app = EmbyToolkit(root)
    root.mainloop()

if __name__ == "__main__":
    main()
