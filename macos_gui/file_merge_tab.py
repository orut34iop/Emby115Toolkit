"""
文件合并标签页 - macOS PyQt5 版本
"""

import os
import sys

from PyQt5.QtWidgets import (
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
from services.file_merger import FileMerger
from utils.config import Config


class DropLineEdit(QLineEdit):
    """支持拖拽的输入框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖拽文件夹到这里")

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


class FileMergeTab(QWidget):
    """文件合并标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 元数据文件夹
        metadata_group = QGroupBox("元数据文件夹")
        metadata_layout = QHBoxLayout()
        metadata_layout.addWidget(QLabel("元数据文件夹："))
        self.metadata_edit = DropLineEdit()
        metadata_layout.addWidget(self.metadata_edit)
        self.btn_browse_metadata = QPushButton("浏览")
        self.btn_browse_metadata.clicked.connect(lambda: self.browse_folder(self.metadata_edit))
        metadata_layout.addWidget(self.btn_browse_metadata)
        metadata_group.setLayout(metadata_layout)
        layout.addWidget(metadata_group)

        # 视频文件文件夹
        video_group = QGroupBox("视频文件文件夹")
        video_layout = QHBoxLayout()
        video_layout.addWidget(QLabel("视频文件夹："))
        self.video_edit = DropLineEdit()
        video_layout.addWidget(self.video_edit)
        self.btn_browse_video = QPushButton("浏览")
        self.btn_browse_video.clicked.connect(lambda: self.browse_folder(self.video_edit))
        video_layout.addWidget(self.btn_browse_video)
        video_group.setLayout(video_layout)
        layout.addWidget(video_group)

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_merge = QPushButton("开始合并")
        self.btn_merge.clicked.connect(self.merge_files)
        btn_layout.addWidget(self.btn_merge)
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

        self.logger = setup_qt_logger('file_merge', self.log_text, os.path.join(self.log_dir, 'file_merge.log'))
        self.load_config()
        self.metadata_edit.textChanged.connect(self.save_config)
        self.video_edit.textChanged.connect(self.save_config)

    def browse_folder(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            edit.setText(folder)

    def load_config(self):
        self.metadata_edit.setText(self.config.get('file_merge', 'metadata_folder', ''))
        self.video_edit.setText(self.config.get('file_merge', 'target_folder', ''))
    def save_config(self):
        self.config.set('file_merge', 'metadata_folder', self.metadata_edit.text().strip())
        self.config.set('file_merge', 'target_folder', self.video_edit.text().strip())
        self.config.save()

    def merge_files(self):
        return run_with_error_dialog(self, self.logger, "文件合并", self._merge_files)

    def _merge_files(self):
        metadata_folder = self.metadata_edit.text().strip()
        video_folder = self.video_edit.text().strip()

        if not metadata_folder or not os.path.isdir(metadata_folder):
            QMessageBox.warning(self, "警告", "请先选择有效的元数据文件夹")
            return
        if not video_folder or not os.path.isdir(video_folder):
            QMessageBox.warning(self, "警告", "请先选择有效的视频文件夹")
            return

        self.logger.info("开始合并文件...")
        merger = FileMerger(metadata_folder=metadata_folder, target_folder=video_folder, logger=self.logger)
        merger.run(lambda message: self.logger.info(message))
