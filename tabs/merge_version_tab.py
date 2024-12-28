from tkinter import ttk
from .base_tab import BaseTab

class MergeVersionTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.init_ui()
        
    def init_ui(self):
        # 创建基本组件
        widgets = self.create_basic_widgets()
        
        # 添加版本选项
        version_frame = ttk.LabelFrame(self.frame, text="版本选项", padding=(5, 5, 5, 5))
        version_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)
        
        self.logger = widgets['logger']
        self.logger.info("合并版本标签页初始化完成")
