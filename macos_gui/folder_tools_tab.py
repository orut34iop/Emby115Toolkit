"""
文件夹操作标签页 - macOS PyQt5 版本
"""

import os
import sys

from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macos_gui.qt_utils import run_with_error_dialog, setup_qt_logger
from media_server.client import MediaServerClient
from services.symlink_deleter import SymlinkDeleter
from utils.config import Config


class DropLineEdit(QLineEdit):
    """支持拖拽的输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖拽文件夹到这里，或点击浏览按钮")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e0f0ff; border: 2px dashed #0078d4;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.setText(path)
                break


class FolderToolsTab(QWidget):
    """文件夹操作标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 目标文件夹
        folder_group = QGroupBox("目标文件夹")
        folder_layout = QVBoxLayout()

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标文件夹："))
        self.target_edit = DropLineEdit()
        target_layout.addWidget(self.target_edit)

        self.btn_browse = QPushButton("浏览")
        self.btn_browse.clicked.connect(self.browse_folder)
        target_layout.addWidget(self.btn_browse)

        folder_layout.addLayout(target_layout)

        # 操作选择
        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("操作："))
        self.combo_op = QComboBox()
        self.combo_op.addItems(["删除软链接", "删除所有视频文件", "检查刮削数据完整性"])
        op_layout.addWidget(self.combo_op)
        op_layout.addStretch()
        folder_layout.addLayout(op_layout)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_execute = QPushButton("开始执行")
        self.btn_execute.clicked.connect(self.execute)
        btn_layout.addWidget(self.btn_execute)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()

        self.logger = setup_qt_logger('folder_tools', self.log_text, os.path.join(self.log_dir, 'folder_tools.log'))
        self.target_edit.setText(self.config.get('folder_tools', 'target_folder', ''))
        self.target_edit.textChanged.connect(self.save_config)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.target_edit.setText(folder)

    def save_config(self):
        self.config.set('folder_tools', 'target_folder', self.target_edit.text().strip())
        self.config.save()

    def execute(self):
        return run_with_error_dialog(self, self.logger, "执行文件夹操作", self._execute)

    def _execute(self):
        folder = self.target_edit.text()
        if not folder:
            QMessageBox.warning(self, "警告", "请先选择文件夹")
            return
        if not os.path.isdir(folder):
            QMessageBox.warning(self, "警告", "请选择有效的文件夹")
            return

        operation = self.combo_op.currentText()
        self.logger.info(f"执行操作: {operation}")
        self.logger.info(f"目标文件夹: {folder}")

        if operation == "删除软链接":
            deleter = SymlinkDeleter(target_folder=folder, logger=self.logger)
            _, message = deleter.run()
            self.logger.info(message)
        elif operation == "删除所有视频文件":
            MediaServerClient(logger=self.logger).clear_files_by_type(
                folder, 'VIDEO', lambda message: self.logger.info(message)
            )
        elif operation == "检查刮削数据完整性":
            MediaServerClient(logger=self.logger).check_metadata_integrity(
                folder, lambda message: self.logger.info(message)
            )
