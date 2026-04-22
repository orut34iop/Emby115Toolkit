"""
utils/logger.py 单元测试
"""
import os
import logging

import pytest

from utils.logger import TextHandler, setup_logger


class TestTextHandler:
    def test_queues_message(self, mock_tk_text):
        handler = TextHandler(mock_tk_text)
        handler.setLevel(logging.DEBUG)
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        handler.emit(record)
        # 验证消息进入队列
        assert not handler.queue.empty()
        queued = handler.queue.get_nowait()
        assert "test message" in queued[0]
        assert queued[1] == "INFO"

    def test_does_not_crash_without_widget(self):
        """验证不依赖真实 tkinter widget"""
        mock_widget = type("MockWidget", (), {
            "after": lambda *a, **k: None,
            "tag_config": lambda *a, **k: None,
        })()
        handler = TextHandler(mock_widget)
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0,
            msg="msg", args=(), exc_info=None,
        )
        handler.emit(record)
        assert not handler.queue.empty()


class TestSetupLogger:
    def test_returns_logger(self):
        logger = setup_logger("test_logger_name")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger_name"

    def test_with_text_widget(self, mock_tk_text):
        logger = setup_logger("test_with_widget", text_widget=mock_tk_text)
        assert any(isinstance(h, TextHandler) for h in logger.handlers)

    def test_with_log_file(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        logger = setup_logger("test_with_file", log_file=log_file)
        assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers)
        assert os.path.exists(log_file)

    def test_no_handlers_when_no_args(self):
        logger = setup_logger("test_no_handlers", text_widget=None, log_file=None)
        assert len(logger.handlers) == 0
