import tkinter as tk
from tkinter import ttk
#from ttkthemes import ThemedTk
#from tkinterdnd2 import TkinterDnD
import os
import sys
import platform  # 添加在文件开头的import部分
from tabs import (
    ExportSymlinkTab,
    ManipulateFolderTab,
    CheckDuplicateTab,
    MergeFilesTab,
    MergeVersionTab,
    UpdateGenresTab,
    Mirror115TreeTab  # 添加新的导入
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
            "文件夹操作": ttk.Frame(self.notebook),
            "emby影剧查重": ttk.Frame(self.notebook),
            "文件合并": ttk.Frame(self.notebook),
            "emby合并版本": ttk.Frame(self.notebook),
            "emby更新流派": ttk.Frame(self.notebook),
            "115目录树镜像": ttk.Frame(self.notebook)  # 添加新的tab页
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
        ManipulateFolderTab(self.tabs["文件夹操作"], self.log_dir)
        CheckDuplicateTab(self.tabs["emby影剧查重"], self.log_dir)
        MergeFilesTab(self.tabs["文件合并"], self.log_dir)
        MergeVersionTab(self.tabs["emby合并版本"], self.log_dir)
        UpdateGenresTab(self.tabs["emby更新流派"], self.log_dir)
        Mirror115TreeTab(self.tabs["115目录树镜像"], self.log_dir)  # 添加新的tab页初始化
        self.logger.info("所有选项卡初始化完成")

    def on_tab_changed(self, event):
        """处理选项卡切换事件"""
        selected_tab_index = self.notebook.index(self.notebook.select())
        self.config.set('last_tab_index', 'index', selected_tab_index)
        self.config.save()

def force_exit():
    '''
    sys.exit() 通常会允许Python执行清理操作，
    但在多线程环境中，它并不总是能立即终止所有线程。
    如果希望快速退出，可以在捕获到 SystemExit 异常时调用 os._exit()。
    '''
    try:
        root.destroy() # 销毁Tkinter窗口
        sys.exit(0)# 退出Python解释器,以确保多线程环境下的立即中止退出
    except SystemExit:
        os._exit(0) 

def maximize_window(root):
    """跨平台窗口最大化"""
    system = platform.system().lower()
    if system == 'windows':
        root.state('zoomed')
    elif system == 'linux':
        root.attributes('-zoomed', True)
    else:  # macOS或其他系统
        root.attributes('-fullscreen', True)

def main():
    global root
    root = tk.Tk()  # 使用标准Tkinter的Tk作为根窗口类
    #style = ttk.Style(root)
    #style.theme_use("clam")  # 使用clam主题，因为不能同时使用ThemedTk
    
    # 设置最小窗口大小
    root.minsize(800, 600)
    
    # 使用跨平台窗口最大化函数
    maximize_window(root)
    
    app = EmbyToolkit(root)
    root.protocol("WM_DELETE_WINDOW", force_exit)  # 设置关闭窗口时的回调函数
    root.mainloop()

if __name__ == "__main__":
    main()
