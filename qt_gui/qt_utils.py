import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox


class _LogEmitter(QObject):
    message = pyqtSignal(str)


class QTextEditLogHandler(logging.Handler):
    """Thread-safe logging handler for QTextEdit widgets."""

    def __init__(self, widget):
        super().__init__()
        self.widget = widget
        self.emitter = _LogEmitter()
        self.emitter.message.connect(self._append_message)

    def emit(self, record):
        try:
            self.emitter.message.emit(self.format(record))
        except Exception:
            self.handleError(record)

    def _append_message(self, message):
        try:
            if self.widget:
                self.widget.append(message)
                scrollbar = self.widget.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except BaseException:
            traceback.print_exc(file=sys.stderr)


def setup_qt_logger(name, text_edit=None, log_file=None):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if text_edit is not None:
        text_handler = QTextEditLogHandler(text_edit)
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def run_with_error_dialog(parent, logger, action, func):
    try:
        return func()
    except Exception as exc:
        if logger:
            logger.error(f"{action}失败: {exc}")
            logger.error(traceback.format_exc())
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.critical(parent, "错误", f"{action}失败:\n{exc}")
        return None
