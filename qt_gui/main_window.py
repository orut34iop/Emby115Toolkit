"""
PyQt5 主窗口
替代 tkinter 的 EmbyToolkit
"""

import sys
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTextEdit,
    QLineEdit, QSpinBox, QCheckBox, QGroupBox,
    QFileDialog, QMessageBox, QProgressBar,
    QSplitter, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QDragEnterEvent, QDropEvent

# 导入原有的业务逻辑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from utils.logger import setup_logger


class LogHandler:
    """日志处理器，将日志输出到 QTextEdit"""
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def info(self, msg):
        self._append_log("INFO", msg)

    def error(self, msg):
        self._append_log("ERROR", msg)

    def warning(self, msg):
        self._append_log("WARN", msg)

    def _append_log(self, level, msg):
        """追加日志到文本框"""
        from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_text = f"{timestamp} - {level} - {msg}\n"

        # 使用 QMetaObject.invokeMethod 确保线程安全
        if self.text_edit:
            self.text_edit.append(log_text)
            # 自动滚动到底部
            scrollbar = self.text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)

        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("Emby115Toolkit - PyQt5 Edition")
        self.setMinimumSize(1000, 700)

        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # 创建标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 初始化各个标签页
        self.init_tabs()

        # 恢复上次选择的标签页
        last_tab = self.config.get('last_tab_index', 'index', 0)
        self.tabs.setCurrentIndex(last_tab)

        # 绑定标签页切换事件
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # 设置窗口大小
        self.resize(1200, 800)
        self.center_window()

    def center_window(self):
        """窗口居中"""
        from PyQt5.QtWidgets import QDesktopWidget

        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def init_tabs(self):
        """初始化标签页"""
        from .export_tab import ExportTab
        from .folder_tab import FolderTab
        from .duplicate_tab import DuplicateTab
        from .merge_tab import MergeTab
        from .version_tab import VersionTab
        from .genres_tab import GenresTab
        from .mirror_tab import MirrorTab

        # 导出软链接
        self.export_tab = ExportTab(self.log_dir)
        self.tabs.addTab(self.export_tab, "导出软链接")

        # 文件夹操作
        self.folder_tab = FolderTab(self.log_dir)
        self.tabs.addTab(self.folder_tab, "文件夹操作")

        # Emby影剧查重
        self.duplicate_tab = DuplicateTab(self.log_dir)
        self.tabs.addTab(self.duplicate_tab, "Emby影剧查重")

        # 文件合并
        self.merge_tab = MergeTab(self.log_dir)
        self.tabs.addTab(self.merge_tab, "文件合并")

        # Emby合并版本
        self.version_tab = VersionTab(self.log_dir)
        self.tabs.addTab(self.version_tab, "Emby合并版本")

        # Emby更新流派
        self.genres_tab = GenresTab(self.log_dir)
        self.tabs.addTab(self.genres_tab, "Emby更新流派")

        # 115目录树镜像
        self.mirror_tab = MirrorTab(self.log_dir)
        self.tabs.addTab(self.mirror_tab, "115目录树镜像")

    def on_tab_changed(self, index):
        """标签页切换事件"""
        self.config.set('last_tab_index', 'index', index)
        self.config.save()

    def closeEvent(self, event):
        """关闭事件"""
        # 保存配置
        self.config.save()
        event.accept()


def main():
    """主函数"""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
