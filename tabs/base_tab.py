import tkinter as tk
from tkinter import ttk, filedialog
import os
from utils.logger import setup_logger

class BaseTab:
    def __init__(self, frame, log_dir):
        self.frame = frame
        self.log_dir = log_dir
        
    def create_basic_widgets(self, browse_type='directory'):
        """创建基本的UI组件"""
        # 创建文件/目录选择区域
        path_frame = ttk.LabelFrame(self.frame, text="路径选择", padding=(5, 5, 5, 5))
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
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        start_btn = ttk.Button(button_frame, text="开始")
        start_btn.pack(side='left', padx=5)
        
        stop_btn = ttk.Button(button_frame, text="停止")
        stop_btn.pack(side='left', padx=5)
        
        # 创建日志区域
        log_frame, log_text = self.create_log_frame(self.frame)
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 设置日志系统
        log_file = os.path.join(self.log_dir, f'{self.frame.winfo_name()}.log')
        logger = setup_logger(self.frame.winfo_name(), log_text, log_file)
        
        return {
            'path_entry': path_entry,
            'browse_btn': browse_btn,
            'start_btn': start_btn,
            'stop_btn': stop_btn,
            'log_text': log_text,
            'logger': logger
        }

    def create_log_frame(self, parent, text="日志"):
        """创建带滚动条的日志框架"""
        log_frame = ttk.LabelFrame(parent, text=text, padding=(5, 5, 5, 5))
        
        # 创建文本框架
        text_frame = ttk.Frame(log_frame)
        text_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        
        # 创建文本框并配置滚动条
        log_text = tk.Text(text_frame, height=10, wrap='word')
        log_text.pack(side='left', fill='both', expand=True)
        
        # 绑定滚动条
        log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=log_text.yview)
        
        # 配置自动滚动
        def on_log_change(event):
            log_text.see(tk.END)
            log_text.update_idletasks()
            
        log_text.bind('<<Modified>>', on_log_change)
        
        return log_frame, log_text

    def scan_string(self, input_string):
        """解析拖拽数据中的路径"""
        result = []
        i = 0
        while i < len(input_string):
            if input_string[i] == '{':
                i += 1
                start = i
                while i < len(input_string) and input_string[i] != '}':
                    i += 1
                #规范化路径
                path = os.path.normpath(input_string[start:i])
                result.append(path)
                i += 1
            else:
                start = i
                while i < len(input_string) and input_string[i] != ' ':
                    i += 1
                #规范化路径
                path = os.path.normpath(input_string[start:i])
                result.append(path)

            if i < len(input_string) and input_string[i] == ' ':
                i += 1

        return [path for path in result if path.strip()]

    def on_folder_drop(self, event, text_widget):
        """处理文件夹拖放事件"""
        data = event.data
        if data:
            # 获取当前已有的路径
            current_paths = set()
            if text_widget.get('1.0', tk.END).strip():
                current_paths = set(text_widget.get('1.0', tk.END).strip().split('\n'))
            
            # Windows路径处理
            folder_paths = self.scan_string(data)
            paths = [path for path in folder_paths if path not in current_paths]

            # 处理新拖入的路径
            added_count = 0
            for path in paths:
                path = path.strip()
                if os.path.isdir(path):
                    # 检查是否重复
                    if path not in current_paths:
                        if current_paths:  # 如果已经有内容，添加换行
                            text_widget.insert(tk.END, '\n')
                        text_widget.insert(tk.END, path)
                        current_paths.add(path)
                        added_count += 1
            
            # 显示添加结果
            if added_count > 0:
                self.logger.info(f"成功添加 {added_count} 个文件夹")
            else:
                self.logger.info("没有新的文件夹被添加（可能是重复路径或非文件夹）")
