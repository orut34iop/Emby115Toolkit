"""
macOS PyQt5 主窗口。
替代 Windows tkinter 的 EmbyToolkit。
"""

import os
import sys

from PyQt5.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# 导入原有的业务逻辑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config


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
        self.setWindowTitle("Emby115Toolkit - macOS PyQt5 Edition")
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
        last_tab = self.config.get('ui_state', 'selected_tab_index', 0)
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
        from .file_merge_tab import FileMergeTab
        from .folder_tools_tab import FolderToolsTab
        from .genre_update_tab import GenreUpdateTab
        from .symlink_export_tab import SymlinkExportTab
        from .tree_mirror_tab import TreeMirrorTab
        from .version_merge_tab import VersionMergeTab

        # 导出软链接
        self.symlink_export_tab = SymlinkExportTab(self.log_dir)
        self.tabs.addTab(self.symlink_export_tab, "导出软链接")

        # 文件夹操作
        self.folder_tools_tab = FolderToolsTab(self.log_dir)
        self.tabs.addTab(self.folder_tools_tab, "文件夹操作")

        # 文件合并
        self.file_merge_tab = FileMergeTab(self.log_dir)
        self.tabs.addTab(self.file_merge_tab, "文件合并")

        # 合并版本
        self.version_merge_tab = VersionMergeTab(self.log_dir)
        self.tabs.addTab(self.version_merge_tab, "合并版本")

        # 更新流派
        self.genre_update_tab = GenreUpdateTab(self.log_dir)
        self.tabs.addTab(self.genre_update_tab, "更新流派")

        # 115目录树镜像
        self.tree_mirror_tab = TreeMirrorTab(self.log_dir)
        self.tabs.addTab(self.tree_mirror_tab, "115目录树镜像")

    def on_tab_changed(self, index):
        """标签页切换事件"""
        self.config.set('ui_state', 'selected_tab_index', index)
        self.config.save()

    def closeEvent(self, event):
        """关闭事件"""
        if (
            hasattr(self, "symlink_export_tab")
            and hasattr(self.symlink_export_tab, "is_task_running")
            and self.symlink_export_tab.is_task_running()
        ):
            reply = QMessageBox.question(
                self,
                "任务正在运行",
                "导出/全同步任务正在运行，关闭会中断任务，是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return

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
