#!/usr/bin/env python3
"""
PyQt5 版本启动入口
提供原生 macOS 拖拽支持
"""

import sys
import os
import logging
import threading
import traceback
from logging.handlers import RotatingFileHandler

PYQT_UNSUPPORTED_MESSAGE = "qt_main.py 仅支持 macOS；Windows 请使用 tkinter 版本：python main.py；Linux 不再支持。"

if sys.platform != 'darwin' and __name__ == '__main__':
    print(PYQT_UNSUPPORTED_MESSAGE)
    sys.exit(1)

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _setup_runtime_logging():
    """Write PyQt lifecycle and uncaught exception details to a file."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("qt_runtime")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "qt_runtime.log"),
        maxBytes=1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "未捕获异常:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )

    def handle_thread_exception(args):
        logger.critical(
            "线程未捕获异常:\n%s",
            "".join(
                traceback.format_exception(
                    args.exc_type,
                    args.exc_value,
                    args.exc_traceback,
                )
            ),
        )

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception
    return logger


def main():
    """主函数"""
    if sys.platform != 'darwin':
        print(PYQT_UNSUPPORTED_MESSAGE)
        sys.exit(1)

    logger = _setup_runtime_logging()
    logger.info("PyQt入口启动: %s", sys.argv)

    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import qInstallMessageHandler
        from qt_gui.main_window import MainWindow

        def qt_message_handler(mode, context, message):
            logger.warning("Qt消息[%s]: %s", mode, message)

        qInstallMessageHandler(qt_message_handler)

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # 设置应用信息
        app.setApplicationName("Emby115Toolkit")
        app.setApplicationDisplayName("Emby115Toolkit - PyQt5")
        app.lastWindowClosed.connect(lambda: logger.info("Qt lastWindowClosed"))
        app.aboutToQuit.connect(lambda: logger.info("Qt aboutToQuit"))

        window = MainWindow()
        window.show()
        logger.info("主窗口已显示")

        exit_code = app.exec_()
        logger.info("Qt事件循环退出: exit_code=%s", exit_code)
        sys.exit(exit_code)

    except ImportError as e:
        logger.exception("无法导入 PyQt5 模块")
        print(f"错误: 无法导入 PyQt5 模块: {e}")
        print("\n请安装 PyQt5:")
        print("  pip install PyQt5")
        sys.exit(1)
    except Exception:
        logger.exception("PyQt入口异常退出")
        raise

if __name__ == '__main__':
    main()
