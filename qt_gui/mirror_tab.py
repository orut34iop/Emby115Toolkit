"""
115目录树镜像标签页 - PyQt5 版本
"""

import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QFileDialog, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config


class DropLineEdit(QLineEdit):
    """支持拖拽的输入框"""

    def __init__(self, parent=None, accept_files=False):
        super().__init__(parent)
        self.accept_files = accept_files
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖拽到这里，或点击浏览按钮")

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
            if self.accept_files or os.path.isdir(path):
                self.setText(path)
                break


class MirrorTab(QWidget):
    """115目录树镜像标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 树文件
        tree_group = QGroupBox("115目录树文件")
        tree_layout = QHBoxLayout()
        tree_layout.addWidget(QLabel("树文件："))
        self.tree_edit = DropLineEdit(accept_files=True)
        tree_layout.addWidget(self.tree_edit)
        self.btn_browse_tree = QPushButton("浏览")
        self.btn_browse_tree.clicked.connect(self.browse_tree_file)
        tree_layout.addWidget(self.btn_browse_tree)
        tree_group.setLayout(tree_layout)
        layout.addWidget(tree_group)

        # 导出文件夹
        export_group = QGroupBox("导出文件夹")
        export_layout = QHBoxLayout()
        export_layout.addWidget(QLabel("导出到："))
        self.export_edit = DropLineEdit()
        export_layout.addWidget(self.export_edit)
        self.btn_browse_export = QPushButton("浏览")
        self.btn_browse_export.clicked.connect(self.browse_export_folder)
        export_layout.addWidget(self.btn_browse_export)
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # 选项
        self.chk_fix_garbled = QCheckBox("修复乱码")
        layout.addWidget(self.chk_fix_garbled)

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_mirror = QPushButton("开始镜像")
        self.btn_mirror.clicked.connect(self.start_mirror)
        btn_layout.addWidget(self.btn_mirror)
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

    def browse_tree_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择树文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if file:
            self.tree_edit.setText(file)

    def browse_export_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择导出文件夹")
        if folder:
            self.export_edit.setText(folder)

    def start_mirror(self):
        tree_file = self.tree_edit.text()
        export_folder = self.export_edit.text()

        if not tree_file or not os.path.exists(tree_file):
            QMessageBox.warning(self, "警告", "请先选择有效的树文件")
            return

        if not export_folder:
            QMessageBox.warning(self, "警告", "请先选择导出文件夹")
            return

        self.log_text.append(f"开始镜像...")
        self.log_text.append(f"树文件: {tree_file}")
        self.log_text.append(f"导出到: {export_folder}")
        # 实际镜像逻辑在这里实现
