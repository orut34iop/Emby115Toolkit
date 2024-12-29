import logging
import tkinter as tk
from logging.handlers import RotatingFileHandler
import os
import queue
import threading
from datetime import datetime

class TextHandler(logging.Handler):
    """将日志输出到tkinter的Text控件"""
    
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        self.text_widget.tag_config('INFO', foreground='black')
        self.text_widget.tag_config('DEBUG', foreground='gray')
        self.text_widget.tag_config('WARNING', foreground='orange')
        self.text_widget.tag_config('ERROR', foreground='red')
        self.text_widget.tag_config('CRITICAL', foreground='red', underline=1)
        self.lock = threading.Lock()
        self.queue = queue.Queue()
        
        # 定期检查队列并更新GUI
        self.text_widget.after(100, self._poll_queue)

    def emit(self, record):
        msg = self.format(record)
        self.queue.put((msg, record.levelname))

    def _poll_queue(self):
        try:
            messages = []
            while True:
                try:
                    msg, levelname = self.queue.get_nowait()
                    messages.append((msg, levelname))
                except queue.Empty:
                    break

            if messages:
                def update_gui():
                    with self.lock:
                        for msg, levelname in messages:
                            self.text_widget.insert(tk.END, msg + '\n', levelname)
                        self.text_widget.see(tk.END)
                self.text_widget.after_idle(update_gui)
        finally:
            self.text_widget.after(50, self._poll_queue)

def setup_logger(name, text_widget=None, log_file=None):
    """设置日志系统
    
    Args:
        name: 日志器名称
        text_widget: tkinter的Text控件，用于显示日志
        log_file: 日志文件路径，如果为None则不输出到文件
    
    Returns:
        logger: 配置好的日志器实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 如果提供了text_widget，添加TextHandler
    if text_widget:
        text_handler = TextHandler(text_widget)
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)
    
    # 如果提供了log_file，添加FileHandler
    if log_file:
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
