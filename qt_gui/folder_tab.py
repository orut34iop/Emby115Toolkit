"""
文件夹操作标签页 - PyQt5 版本
"""

import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QFileDialog, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


class FolderTab(QWidget):
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
        self.combo_op.addItems([
            "删除软链接",
            "删除所有视频文件",
            "检查刮削数据完整性"
        ])
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

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.target_edit.setText(folder)

    def execute(self):
        folder = self.target_edit.text()
        if not folder:
            QMessageBox.warning(self, "警告", "请先选择文件夹")
            return

        operation = self.combo_op.currentText()
        self.log_text.append(f"执行操作: {operation}")
        self.log_text.append(f"目标文件夹: {folder}")
        # 实际执行逻辑在这里实现
