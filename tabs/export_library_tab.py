from tkinter import ttk
from .base_tab import BaseTab

class ExportLibraryTab(BaseTab):
    def __init__(self, frame, log_dir):
        super().__init__(frame, log_dir)
        self.init_ui()
        
    def init_ui(self):
        # 创建基本组件
        widgets = self.create_basic_widgets()
        
        # 添加导出选项
        export_frame = ttk.LabelFrame(self.frame, text="导出选项", padding=(5, 5, 5, 5))
        export_frame.pack(fill='x', padx=5, pady=5, before=widgets['log_text'].master)
        
        self.logger = widgets['logger']
        self.logger.info("导出库文件标签页初始化完成")
