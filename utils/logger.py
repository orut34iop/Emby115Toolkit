import logging
import tkinter as tk
from logging.handlers import RotatingFileHandler
import os
import queue
import threading
from datetime import datetime

class TextHandler(logging.Handler):
    """将日志输出到tkinter的Text控件"""
    
    def __init__(self, text_widget, max_batch_size=10):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        self.text_widget.tag_config('INFO', foreground='black')
        self.text_widget.tag_config('DEBUG', foreground='gray')
        self.text_widget.tag_config('WARNING', foreground='orange')
        self.text_widget.tag_config('ERROR', foreground='red')
        self.text_widget.tag_config('CRITICAL', foreground='red', underline=1)

        self.max_batch_size = max_batch_size
        
        # 使用队列来确保线程安全
        self.queue = queue.Queue()
        self.max_batch_size = max_batch_size
        
        # 定期检查队列并批量更新GUI
        self.text_widget.after(100, self._poll_queue)

    def emit(self, record):
        try:
            msg = self.format(record)
            levelname = record.levelname

            # 将日志消息放入队列中
            self.queue.put((msg, levelname))
        except Exception:
            self.handleError(record)

    def _poll_queue(self):
        try:
            messages = []
            while len(messages) < self.max_batch_size:
                try:
                    msg, levelname = self.queue.get_nowait()
                    messages.append((msg, levelname))
                except queue.Empty:
                    break

            if messages:
                def update_gui():
                    for msg, levelname in messages:
                        self.text_widget.insert(tk.END, msg + '\n', levelname)
                    self.text_widget.see(tk.END)
                    self.text_widget.update_idletasks()  # 强制刷新GUI
                
                # 立即安排GUI更新
                self.text_widget.after_idle(update_gui)
                
                # 标记所有已处理的任务为完成
                for _ in messages:
                    self.queue.task_done()
        finally:
            # 继续定期轮询
            self.text_widget.after(100, self._poll_queue)

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