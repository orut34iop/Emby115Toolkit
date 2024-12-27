import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkthemes import ThemedTk
import os
from utils.logger import setup_logger
import logging

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
        self.init_export_symlink_tab()
        self.init_delete_symlink_tab()
        self.init_check_duplicate_tab()
        self.init_merge_files_tab()
        self.init_export_library_tab()
        self.init_merge_version_tab()
        self.init_update_category_tab()

    def create_basic_widgets(self, frame, browse_type='directory'):
        """创建基本的UI组件"""
        # 创建文件/目录选择区域
        path_frame = ttk.LabelFrame(frame, text="路径选择", padding=(5, 5, 5, 5))
        path_frame.pack(fill='x', padx=5, pady=5)
        
        path_entry = ttk.Entry(path_frame)
        path_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        def browse():
            if browse_type == 'directory':
                path = filedialog.askdirectory(title="选择目录")
            else:
                path = filedialog.askopenfilename(title="选择文件")
            if path:
                path_entry.delete(0, tk.END)
                path_entry.insert(0, path)
        
        browse_btn = ttk.Button(path_frame, text="浏览", command=browse)
        browse_btn.pack(side='right', padx=(5, 5))
        
        # 创建操作按钮区域
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        start_btn = ttk.Button(button_frame, text="开始")
        start_btn.pack(side='left', padx=5)
        
        stop_btn = ttk.Button(button_frame, text="停止")
        stop_btn.pack(side='left', padx=5)
        
        # 创建日志区域
        log_frame = ttk.LabelFrame(frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        log_text = tk.Text(log_frame, height=10, wrap='word')
        log_text.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=log_text.yview)
        scrollbar.pack(side='right', fill='y')
        log_text.configure(yscrollcommand=scrollbar.set)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, f'{frame.winfo_name()}.log')
        logger = setup_logger(frame.winfo_name(), log_text, log_file)
        
        return {
            'path_entry': path_entry,
            'browse_btn': browse_btn,
            'start_btn': start_btn,
            'stop_btn': stop_btn,
            'log_text': log_text,
            'logger': logger
        }

    def init_export_symlink_tab(self):
        frame = self.tabs["导出软链接"]
        frame.winfo_name = lambda: "export_symlink"
        
        # 使用说明
        desc_label = ttk.Label(frame, text="使用说明: 将文件夹拖拽到输入框即可生成软链接表（自动忽略重复路径）")
        desc_label.pack(fill='x', padx=5, pady=5)
        
        # 链接文件夹选择
        link_frame = ttk.LabelFrame(frame, text="链接文件夹", padding=(5, 5, 5, 5))
        link_frame.pack(fill='x', padx=5, pady=5)
        
        link_text = tk.Text(link_frame, height=4, wrap='none')
        link_text.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        link_scroll = ttk.Scrollbar(link_frame, orient='vertical', command=link_text.yview)
        link_scroll.pack(side='right', fill='y')
        link_text.configure(yscrollcommand=link_scroll.set)
        
        link_browse = ttk.Button(link_frame, text="浏览")
        link_browse.pack(side='right', padx=5)
        
        # 目标文件夹选择
        target_frame = ttk.LabelFrame(frame, text="目标文件夹", padding=(5, 5, 5, 5))
        target_frame.pack(fill='x', padx=5, pady=5)
        
        target_entry = ttk.Entry(target_frame)
        target_entry.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        target_browse = ttk.Button(target_frame, text="浏览")
        target_browse.pack(side='right', padx=5)
        
        # 同步线程数选择
        thread_frame = ttk.Frame(frame)
        thread_frame.pack(fill='x', padx=5, pady=5)
        
        thread_label = ttk.Label(thread_frame, text="同步线程数:")
        thread_label.pack(side='left', padx=5)
        
        thread_spinbox = ttk.Spinbox(thread_frame, from_=1, to=16, width=10)
        thread_spinbox.set(4)  # 默认值
        thread_spinbox.pack(side='left', padx=5)
        
        # 后缀设置
        suffix_frame = ttk.Frame(frame)
        suffix_frame.pack(fill='x', padx=5, pady=5)
        
        # 软链接后缀
        link_suffix_label = ttk.Label(suffix_frame, text="软链接后缀:")
        link_suffix_label.pack(side='left', padx=5)
        
        link_suffix_entry = ttk.Entry(suffix_frame)
        link_suffix_entry.insert(0, ".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm")
        link_suffix_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        # 元数据后缀
        meta_suffix_label = ttk.Label(suffix_frame, text="元数据后缀:")
        meta_suffix_label.pack(side='left', padx=5)
        
        meta_suffix_entry = ttk.Entry(suffix_frame)
        meta_suffix_entry.insert(0, ".nfo;.jpg;.png;.svg;.ass;.srt;.sup")
        meta_suffix_entry.pack(side='left', fill='x', expand=True, padx=5)
        
        # 操作按钮组
        btn_frame = ttk.LabelFrame(frame, text="开始同步", padding=(5, 5, 5, 5))
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        sync_all_btn = ttk.Button(btn_frame, text="一键全同步")
        sync_all_btn.pack(side='left', padx=5)
        
        create_link_btn = ttk.Button(btn_frame, text="创建软链接")
        create_link_btn.pack(side='left', padx=5)
        
        download_meta_btn = ttk.Button(btn_frame, text="下载元数据")
        download_meta_btn.pack(side='left', padx=5)
        
        copy_version_btn = ttk.Button(btn_frame, text="复制到剪贴版")
        copy_version_btn.pack(side='left', padx=5)
        
        clear_list_btn = ttk.Button(btn_frame, text="清空文件夹列表")
        clear_list_btn.pack(side='left', padx=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(frame, text="日志", padding=(5, 5, 5, 5))
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        log_text = tk.Text(log_frame, height=10, wrap='word')
        log_text.pack(side='left', fill='both', expand=True)
        
        log_scroll = ttk.Scrollbar(log_frame, orient='vertical', command=log_text.yview)
        log_scroll.pack(side='right', fill='y')
        log_text.configure(yscrollcommand=log_scroll.set)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, 'export_symlink.log')
        logger = setup_logger('export_symlink', log_text, log_file)
        logger.info("导出软链接标签页初始化完成")

    def init_delete_symlink_tab(self):
        frame = self.tabs["删除软链接"]
        frame.winfo_name = lambda: "delete_symlink"
        widgets = self.create_basic_widgets(frame)
        widgets['logger'].info("删除软链接标签页初始化完成")
        # 添加删除条件选择
        options_frame = ttk.LabelFrame(frame, text="删除选项", padding=(5, 5, 5, 5))
        options_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_check_duplicate_tab(self):
        frame = self.tabs["检查去重"]
        frame.winfo_name = lambda: "check_duplicate"
        widgets = self.create_basic_widgets(frame)
        widgets['logger'].info("检查去重标签页初始化完成")
        # 添加检查选项
        check_frame = ttk.LabelFrame(frame, text="检查选项", padding=(5, 5, 5, 5))
        check_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_merge_files_tab(self):
        frame = self.tabs["文件合并"]
        frame.winfo_name = lambda: "merge_files"
        widgets = self.create_basic_widgets(frame)
        widgets['logger'].info("文件合并标签页初始化完成")
        # 添加合并选项
        merge_frame = ttk.LabelFrame(frame, text="合并选项", padding=(5, 5, 5, 5))
        merge_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_export_library_tab(self):
        frame = self.tabs["导出库文件"]
        frame.winfo_name = lambda: "export_library"
        widgets = self.create_basic_widgets(frame)
        widgets['logger'].info("导出库文件标签页初始化完成")
        # 添加导出选项
        export_frame = ttk.LabelFrame(frame, text="导出选项", padding=(5, 5, 5, 5))
        export_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_merge_version_tab(self):
        frame = self.tabs["合并版本"]
        frame.winfo_name = lambda: "merge_version"
        widgets = self.create_basic_widgets(frame)
        widgets['logger'].info("合并版本标签页初始化完成")
        # 添加版本选项
        version_frame = ttk.LabelFrame(frame, text="版本选项", padding=(5, 5, 5, 5))
        version_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_update_category_tab(self):
        frame = self.tabs["更新类别"]
        frame.winfo_name = lambda: "update_category"
        widgets = self.create_basic_widgets(frame)
        widgets['logger'].info("更新类别标签页初始化完成")
        # 添加类别选项
        category_frame = ttk.LabelFrame(frame, text="类别选项", padding=(5, 5, 5, 5))
        category_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

def main():
    root = ThemedTk(theme="arc")  # 使用更现代的主题
    app = EmbyToolkit(root)
    root.mainloop()

if __name__ == "__main__":
    main()
