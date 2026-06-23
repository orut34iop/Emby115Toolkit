"""
utils.logger 模块单元测试
"""
import pytest
import os
import logging
import tempfile
import time
from unittest.mock import MagicMock, patch


class TestSetupLogger:
    """测试 setup_logger 函数"""

    def test_setup_logger_basic(self):
        """测试基础 logger 创建"""
        from utils.logger import setup_logger

        logger = setup_logger('test_basic')

        assert isinstance(logger, logging.Logger)
        assert logger.name == 'test_basic'
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 0

    def test_setup_logger_with_log_file(self, temp_dir):
        """测试带文件 handler 的 logger"""
        from utils.logger import setup_logger

        log_file = os.path.join(temp_dir, 'test.log')
        logger = setup_logger('test_file', log_file=log_file)

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

        # 验证可以写入日志
        logger.info('test message')
        assert os.path.exists(log_file)

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'test message' in content

    def test_setup_logger_creates_log_directory(self, temp_dir):
        """测试自动创建日志目录"""
        from utils.logger import setup_logger

        log_dir = os.path.join(temp_dir, 'nested', 'log', 'dir')
        log_file = os.path.join(log_dir, 'app.log')

        logger = setup_logger('test_dir', log_file=log_file)
        logger.info('directory test')

        assert os.path.isdir(log_dir)
        assert os.path.exists(log_file)

    def test_setup_logger_formatter(self, temp_dir):
        """测试日志格式"""
        from utils.logger import setup_logger

        log_file = os.path.join(temp_dir, 'format.log')
        logger = setup_logger('test_format', log_file=log_file)
        logger.info('format test')

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 验证格式包含时间、级别和消息
        assert 'INFO' in content
        assert 'format test' in content
        assert '-' in content  # 格式分隔符

    def test_setup_logger_file_rotation(self, temp_dir):
        """测试日志文件轮转"""
        from utils.logger import setup_logger

        log_file = os.path.join(temp_dir, 'rotate.log')
        logger = setup_logger('test_rotate', log_file=log_file)

        handler = logger.handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == 1024 * 1024  # 1MB
        assert handler.backupCount == 5
        assert handler.encoding == 'utf-8'

    def test_setup_logger_different_levels(self, temp_dir):
        """测试不同日志级别"""
        from utils.logger import setup_logger

        log_file = os.path.join(temp_dir, 'levels.log')
        logger = setup_logger('test_levels', log_file=log_file)

        logger.debug('debug msg')
        logger.info('info msg')
        logger.warning('warning msg')
        logger.error('error msg')

        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'debug msg' in content
        assert 'info msg' in content
        assert 'warning msg' in content
        assert 'error msg' in content


import tkinter as tk


class TestTextHandler:
    """测试 TextHandler 类"""

    @pytest.fixture
    def mock_text_widget(self):
        """创建模拟的 tkinter Text 控件"""
        widget = MagicMock()
        widget.after = MagicMock()
        widget.after_idle = MagicMock()
        widget.tag_config = MagicMock()
        widget.insert = MagicMock()
        widget.see = MagicMock()
        widget.update_idletasks = MagicMock()
        return widget

    def test_text_handler_init(self, mock_text_widget):
        """测试 TextHandler 初始化"""
        from utils.logger import TextHandler

        handler = TextHandler(mock_text_widget)

        assert handler.text_widget == mock_text_widget
        assert handler.max_batch_size == 10
        assert handler.queue is not None

        # 验证标签配置
        mock_text_widget.tag_config.assert_any_call('INFO', foreground='black')
        mock_text_widget.tag_config.assert_any_call('DEBUG', foreground='gray')
        mock_text_widget.tag_config.assert_any_call('WARNING', foreground='orange')
        mock_text_widget.tag_config.assert_any_call('ERROR', foreground='red')
        mock_text_widget.tag_config.assert_any_call('CRITICAL', foreground='red', underline=1)

        # 验证 after 被调用启动轮询
        mock_text_widget.after.assert_called_once_with(100, handler._poll_queue)

    def test_text_handler_emit(self, mock_text_widget):
        """测试 emit 方法将消息放入队列"""
        from utils.logger import TextHandler
        import logging

        handler = TextHandler(mock_text_widget)
        handler.setFormatter(logging.Formatter('%(message)s'))

        record = logging.LogRecord(
            name='test', level=logging.INFO, pathname='', lineno=0,
            msg='test message', args=(), exc_info=None
        )
        handler.emit(record)

        # 验证消息在队列中
        msg, level = handler.queue.get_nowait()
        assert 'test message' in msg
        assert level == 'INFO'

    def test_text_handler_emit_different_levels(self, mock_text_widget):
        """测试不同级别的日志 emit"""
        from utils.logger import TextHandler
        import logging

        handler = TextHandler(mock_text_widget)
        handler.setFormatter(logging.Formatter('%(message)s'))

        levels = [
            (logging.DEBUG, 'DEBUG'),
            (logging.WARNING, 'WARNING'),
            (logging.ERROR, 'ERROR'),
            (logging.CRITICAL, 'CRITICAL'),
        ]

        for level, levelname in levels:
            record = logging.LogRecord(
                name='test', level=level, pathname='', lineno=0,
                msg=f'{levelname} msg', args=(), exc_info=None
            )
            handler.emit(record)

            msg, msg_level = handler.queue.get_nowait()
            assert msg_level == levelname

    def test_text_handler_poll_queue_empty(self, mock_text_widget):
        """测试轮询空队列"""
        from utils.logger import TextHandler

        handler = TextHandler(mock_text_widget)

        # 清空 after 调用记录
        mock_text_widget.after.reset_mock()

        # 轮询空队列
        handler._poll_queue()

        # 验证没有调用 insert（队列为空）
        mock_text_widget.insert.assert_not_called()
        # 验证重新安排了轮询
        assert mock_text_widget.after.called

    def test_text_handler_poll_queue_with_messages(self, mock_text_widget):
        """测试轮询有消息的队列"""
        from utils.logger import TextHandler

        handler = TextHandler(mock_text_widget)

        # 放入消息
        handler.queue.put(('msg1', 'INFO'))
        handler.queue.put(('msg2', 'ERROR'))

        # 清空 after 调用记录
        mock_text_widget.after.reset_mock()

        handler._poll_queue()

        # 验证 GUI 更新被安排
        assert mock_text_widget.after_idle.called

        # 执行实际的 GUI 更新
        update_call = mock_text_widget.after_idle.call_args
        if update_call:
            update_func = update_call[0][0]
            update_func()

            # 验证消息被插入到 Text 控件
            assert mock_text_widget.insert.call_count == 2
            mock_text_widget.insert.assert_any_call(tk.END, 'msg1\n', 'INFO')
            mock_text_widget.insert.assert_any_call(tk.END, 'msg2\n', 'ERROR')
            mock_text_widget.see.assert_called_with(tk.END)

    def test_text_handler_batch_processing(self, mock_text_widget):
        """测试批量处理消息"""
        from utils.logger import TextHandler

        handler = TextHandler(mock_text_widget, max_batch_size=3)

        # 放入超过批量大小的消息
        for i in range(5):
            handler.queue.put((f'msg{i}', 'INFO'))

        mock_text_widget.after.reset_mock()
        handler._poll_queue()

        # 只处理了 max_batch_size 条
        update_call = mock_text_widget.after_idle.call_args
        if update_call:
            update_func = update_call[0][0]
            update_func()
            assert mock_text_widget.insert.call_count == 3

    def test_text_handler_custom_max_batch_size(self, mock_text_widget):
        """测试自定义批量大小"""
        from utils.logger import TextHandler

        handler = TextHandler(mock_text_widget, max_batch_size=5)
        assert handler.max_batch_size == 5

    def test_setup_logger_with_text_widget(self, mock_text_widget):
        """测试带 text_widget 的 setup_logger"""
        import tkinter as tk
        from utils.logger import setup_logger

        # 需要 tk.END 作为常量
        with patch('utils.logger.tk.END', tk.END):
            logger = setup_logger('test_text_widget', text_widget=mock_text_widget)

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.Handler)

        logger.info('widget test')

        # 消息应该被放入队列
        handler = logger.handlers[0]
        assert not handler.queue.empty()
