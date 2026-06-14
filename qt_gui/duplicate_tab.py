"""
Emby影剧查重标签页 - PyQt5 版本
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
from emby.EmbyOperator import EmbyOperator
from qt_gui.qt_utils import run_with_error_dialog, setup_qt_logger


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


class DuplicateTab(QWidget):
    """Emby影剧查重标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Emby 服务器设置
        server_group = QGroupBox("Emby 服务器设置")
        server_layout = QVBoxLayout()

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("服务器地址："))
        self.edit_url = QLineEdit()
        self.edit_url.setPlaceholderText("http://localhost:8096")
        url_layout.addWidget(self.edit_url)
        server_layout.addLayout(url_layout)

        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API Key："))
        self.edit_api = QLineEdit()
        api_layout.addWidget(self.edit_api)
        server_layout.addLayout(api_layout)

        server_group.setLayout(server_layout)
        layout.addWidget(server_group)

        # 目标文件夹
        folder_group = QGroupBox("目标文件夹")
        folder_layout = QVBoxLayout()

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("扫描文件夹："))
        self.target_edit = DropLineEdit()
        target_layout.addWidget(self.target_edit)

        self.btn_browse = QPushButton("浏览")
        self.btn_browse.clicked.connect(self.browse_folder)
        target_layout.addWidget(self.btn_browse)

        folder_layout.addLayout(target_layout)

        # 选项
        self.chk_delete_nfo = QCheckBox("删除重复的 nfo 文件")
        folder_layout.addWidget(self.chk_delete_nfo)

        self.chk_delete_folder = QCheckBox("删除重复文件所在的文件夹")
        folder_layout.addWidget(self.chk_delete_folder)

        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_check = QPushButton("开始查重")
        self.btn_check.clicked.connect(self.check_duplicate)
        btn_layout.addWidget(self.btn_check)
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

        self.logger = setup_qt_logger(
            'check_duplicate',
            self.log_text,
            os.path.join(self.log_dir, 'check_duplicate.log')
        )
        self.load_config()
        self.target_edit.textChanged.connect(self.save_config)
        self.edit_url.textChanged.connect(self.save_config)
        self.edit_api.textChanged.connect(self.save_config)
        self.chk_delete_nfo.stateChanged.connect(self.save_config)
        self.chk_delete_folder.stateChanged.connect(self.save_config)

    def load_config(self):
        self.target_edit.setText(self.config.get('check_duplicate', 'target_folder', ''))
        self.edit_url.setText(self.config.get('check_duplicate', 'emby_url', ''))
        self.edit_api.setText(self.config.get('check_duplicate', 'emby_api', ''))
        self.chk_delete_nfo.setChecked(self.config.get('check_duplicate', 'delete_nfo', False))
        self.chk_delete_folder.setChecked(self.config.get('check_duplicate', 'delete_nfo_folder', False))

    def save_config(self):
        self.config.set('check_duplicate', 'target_folder', self.target_edit.text().strip())
        self.config.set('check_duplicate', 'emby_url', self.edit_url.text().strip())
        self.config.set('check_duplicate', 'emby_api', self.edit_api.text().strip())
        self.config.set('check_duplicate', 'delete_nfo', self.chk_delete_nfo.isChecked())
        self.config.set('check_duplicate', 'delete_nfo_folder', self.chk_delete_folder.isChecked())
        self.config.save()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.target_edit.setText(folder)

    def check_duplicate(self):
        return run_with_error_dialog(self, self.logger, "Emby影剧查重", self._check_duplicate)

    def _check_duplicate(self):
        folder = self.target_edit.text()
        if not folder:
            QMessageBox.warning(self, "警告", "请先选择文件夹")
            return
        if not os.path.isdir(folder):
            QMessageBox.warning(self, "警告", "请选择有效的文件夹")
            return

        server_url = self.edit_url.text().strip()
        api_key = self.edit_api.text().strip()
        if not server_url or not api_key:
            QMessageBox.warning(self, "警告", "请先填写 Emby 服务器地址和 API Key")
            return

        self.logger.info("开始查重...")
        operator = EmbyOperator(
            server_url=server_url,
            api_key=api_key,
            delete_nfo=self.chk_delete_nfo.isChecked(),
            delete_nfo_folder=self.chk_delete_folder.isChecked(),
            logger=self.logger
        )
        operator.check_duplicate(folder, lambda message: self.logger.info(message))
