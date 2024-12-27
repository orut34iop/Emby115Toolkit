import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkthemes import ThemedTk
import os

class EmbyToolkit:
    def __init__(self, root):
        self.root = root
        self.root.title("Emby115Toolkit")
        
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
        
        return {
            'path_entry': path_entry,
            'browse_btn': browse_btn,
            'start_btn': start_btn,
            'stop_btn': stop_btn,
            'log_text': log_text
        }

    def init_export_symlink_tab(self):
        frame = self.tabs["导出软链接"]
        widgets = self.create_basic_widgets(frame)
        # 添加源目录选择
        source_frame = ttk.LabelFrame(frame, text="源目录", padding=(5, 5, 5, 5))
        source_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_delete_symlink_tab(self):
        frame = self.tabs["删除软链接"]
        widgets = self.create_basic_widgets(frame)
        # 添加删除条件选择
        options_frame = ttk.LabelFrame(frame, text="删除选项", padding=(5, 5, 5, 5))
        options_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_check_duplicate_tab(self):
        frame = self.tabs["检查去重"]
        widgets = self.create_basic_widgets(frame)
        # 添加检查选项
        check_frame = ttk.LabelFrame(frame, text="检查选项", padding=(5, 5, 5, 5))
        check_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_merge_files_tab(self):
        frame = self.tabs["文件合并"]
        widgets = self.create_basic_widgets(frame)
        # 添加合并选项
        merge_frame = ttk.LabelFrame(frame, text="合并选项", padding=(5, 5, 5, 5))
        merge_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_export_library_tab(self):
        frame = self.tabs["导出库文件"]
        widgets = self.create_basic_widgets(frame)
        # 添加导出选项
        export_frame = ttk.LabelFrame(frame, text="导出选项", padding=(5, 5, 5, 5))
        export_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_merge_version_tab(self):
        frame = self.tabs["合并版本"]
        widgets = self.create_basic_widgets(frame)
        # 添加版本选项
        version_frame = ttk.LabelFrame(frame, text="版本选项", padding=(5, 5, 5, 5))
        version_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

    def init_update_category_tab(self):
        frame = self.tabs["更新类别"]
        widgets = self.create_basic_widgets(frame)
        # 添加类别选项
        category_frame = ttk.LabelFrame(frame, text="类别选项", padding=(5, 5, 5, 5))
        category_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)

def main():
    root = ThemedTk(theme="arc")  # 使用更现代的主题
    app = EmbyToolkit(root)
    root.mainloop()

if __name__ == "__main__":
    main()
