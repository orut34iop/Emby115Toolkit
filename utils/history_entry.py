import tkinter as tk
from tkinter import ttk, filedialog
from tkinterdnd2 import DND_FILES
import os


class HistoryEntry:
    """带历史记录下拉功能的输入框组件"""
    
    def __init__(self, parent, config, config_section, config_key, 
                 label_text=None, is_file=False, file_types=None, **entry_kwargs):
        """
        初始化历史记录输入框
        
        Args:
            parent: 父容器
            config: Config配置对象
            config_section: 配置节名称
            config_key: 配置键名
            label_text: LabelFrame的标题
            is_file: 是否为文件选择（默认为文件夹选择）
            file_types: 文件选择对话框的文件类型
            **entry_kwargs: Entry的其他参数
        """
        self.config = config
        self.config_section = config_section
        self.config_key = config_key
        self.is_file = is_file
        self.file_types = file_types or [("所有文件", "*.*")]
        
        # 创建框架
        if label_text:
            self.frame = ttk.LabelFrame(parent, text=label_text, padding=(5, 5, 5, 5))
        else:
            self.frame = ttk.Frame(parent)
        
        # 创建Combobox（带下拉功能的输入框）
        self.combobox = ttk.Combobox(self.frame, **entry_kwargs)
        self.combobox.pack(side='left', fill='x', expand=True, padx=(5, 5))
        
        # 设置Combobox为可编辑
        self.combobox['state'] = 'normal'
        
        # 创建浏览按钮
        def browse():
            if is_file:
                path = filedialog.askopenfilename(
                    title=f"选择{label_text or '文件'}",
                    filetypes=self.file_types
                )
            else:
                path = filedialog.askdirectory(title=f"选择{label_text or '文件夹'}")
            
            if path:
                path = os.path.normpath(path)
                self.set(path)
                self._save_history(path)
                if self.on_change:
                    self.on_change(path)
        
        browse_btn = ttk.Button(self.frame, text="浏览", command=browse)
        browse_btn.pack(side='right', padx=5)
        
        # 拖放功能
        self.combobox.drop_target_register(DND_FILES)
        self.combobox.dnd_bind('<<Drop>>', self._on_drop)
        
        # 事件绑定
        self.combobox.bind('<FocusOut>', self._on_focus_out)
        self.combobox.bind('<Return>', self._on_return)
        
        # 变更回调
        self.on_change = None
        
        # 加载历史记录
        self._load_history()
    
    def _on_drop(self, event):
        """处理拖放事件"""
        data = event.data
        if data:
            paths = self._parse_paths(data)
            if paths:
                path = paths[0].strip()
                if self.is_file:
                    if os.path.exists(path) and os.path.isfile(path):
                        self.set(path)
                        self._save_history(path)
                        if self.on_change:
                            self.on_change(path)
                else:
                    if os.path.exists(path) and os.path.isdir(path):
                        self.set(path)
                        self._save_history(path)
                        if self.on_change:
                            self.on_change(path)
    
    def _parse_paths(self, input_string):
        """解析拖拽数据中的路径"""
        result = []
        i = 0
        while i < len(input_string):
            if input_string[i] == '{':
                i += 1
                start = i
                while i < len(input_string) and input_string[i] != '}':
                    i += 1
                path = os.path.normpath(input_string[start:i])
                result.append(path)
                i += 1
            else:
                start = i
                while i < len(input_string) and input_string[i] != ' ':
                    i += 1
                path = os.path.normpath(input_string[start:i])
                result.append(path)
            
            if i < len(input_string) and input_string[i] == ' ':
                i += 1
        
        return [path for path in result if path.strip()]
    
    def _on_focus_out(self, event=None):
        """失去焦点时保存"""
        current = self.get().strip()
        if current:
            self._save_history(current)
        if self.on_change:
            self.on_change(current)
    
    def _on_return(self, event=None):
        """按下回车时保存"""
        self._on_focus_out(event)
    
    def _get_history_key(self):
        """获取历史记录在配置中的键名"""
        return f"{self.config_key}_history"
    
    def _load_history(self):
        """加载历史记录到Combobox"""
        history = self.config.get(self.config_section, self._get_history_key(), default=[])
        if isinstance(history, list):
            self.combobox['values'] = history
            # 如果有历史记录，显示第一个
            if history:
                current = self.config.get(self.config_section, self.config_key, default='')
                self.combobox.set(current)
    
    def _save_history(self, path):
        """保存路径到历史记录（最多5条）"""
        if not path:
            return
        
        path = os.path.normpath(path)
        
        # 获取现有历史记录
        history = self.config.get(self.config_section, self._get_history_key(), default=[])
        if not isinstance(history, list):
            history = []
        
        # 如果路径已存在，先移除它（以便移到最前面）
        if path in history:
            history.remove(path)
        
        # 添加到列表开头
        history.insert(0, path)
        
        # 只保留最近5条
        history = history[:5]
        
        # 保存到配置
        self.config.set(self.config_section, self._get_history_key(), history)
        self.config.set(self.config_section, self.config_key, path)
        self.config.save()
        
        # 更新Combobox的值
        self.combobox['values'] = history
    
    def get(self):
        """获取当前值"""
        return self.combobox.get()
    
    def set(self, value):
        """设置当前值"""
        self.combobox.set(value)
    
    def delete(self, first, last):
        """删除文本（兼容Entry接口）"""
        self.combobox.delete(first, last)
    
    def insert(self, index, value):
        """插入文本（兼容Entry接口）"""
        self.combobox.insert(index, value)
    
    def bind(self, event, callback):
        """绑定事件（兼容Entry接口）"""
        return self.combobox.bind(event, callback)
    
    def pack(self, **kwargs):
        """打包布局"""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """网格布局"""
        self.frame.grid(**kwargs)
    
    def drop_target_register(self, *args):
        """拖放注册（兼容Entry接口）"""
        return self.combobox.drop_target_register(*args)
    
    def dnd_bind(self, *args):
        """拖放绑定（兼容Entry接口）"""
        return self.combobox.dnd_bind(*args)
