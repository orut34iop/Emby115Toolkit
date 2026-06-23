"""
文件合并标签页 - PyQt5 版本
"""

import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QFileDialog, QMessageBox, QSpinBox, QCheckBox
)
from PyQt5.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from emby115_v1.utils.config import Config
from emby115_v1.autosync.FileMerger import FileMerger
from emby115_v1.qt_gui.qt_utils import run_with_error_dialog, setup_qt_logger


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


class MergeTab(QWidget):
    """文件合并标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 刮削数据文件夹
        scrap_group = QGroupBox("刮削数据文件夹")
        scrap_layout = QHBoxLayout()
        scrap_layout.addWidget(QLabel("刮削文件夹："))
        self.scrap_edit = DropLineEdit()
        scrap_layout.addWidget(self.scrap_edit)
        self.btn_browse_scrap = QPushButton("浏览")
        self.btn_browse_scrap.clicked.connect(lambda: self.browse_folder(self.scrap_edit))
        scrap_layout.addWidget(self.btn_browse_scrap)
        scrap_group.setLayout(scrap_layout)
        layout.addWidget(scrap_group)

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

        # 设置
        settings_group = QGroupBox("设置")
        settings_layout = QVBoxLayout()

        self.chk_protect = QCheckBox("开启115防封")
        settings_layout.addWidget(self.chk_protect)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("操作间隔(秒)："))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(0, 60)
        self.spin_interval.setValue(4)
        interval_layout.addWidget(self.spin_interval)
        interval_layout.addStretch()
        settings_layout.addLayout(interval_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

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

        self.logger = setup_qt_logger(
            'merge_file',
            self.log_text,
            os.path.join(self.log_dir, 'merge_file.log')
        )
        self.load_config()
        self.scrap_edit.textChanged.connect(self.save_config)
        self.video_edit.textChanged.connect(self.save_config)
        self.chk_protect.stateChanged.connect(self.save_config)
        self.spin_interval.valueChanged.connect(self.save_config)

    def browse_folder(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            edit.setText(folder)

    def load_config(self):
        self.scrap_edit.setText(self.config.get('merge_file', 'scrap_folder', ''))
        self.video_edit.setText(self.config.get('merge_file', 'target_folder', ''))
        self.chk_protect.setChecked(self.config.get('merge_file', 'enable_115_protect', False))
        self.spin_interval.setValue(self.config.get('merge_file', 'op_interval_sec', 4))

    def save_config(self):
        self.config.set('merge_file', 'scrap_folder', self.scrap_edit.text().strip())
        self.config.set('merge_file', 'target_folder', self.video_edit.text().strip())
        self.config.set('merge_file', 'enable_115_protect', self.chk_protect.isChecked())
        self.config.set('merge_file', 'op_interval_sec', self.spin_interval.value())
        self.config.save()

    def merge_files(self):
        return run_with_error_dialog(self, self.logger, "文件合并", self._merge_files)

    def _merge_files(self):
        scrap_folder = self.scrap_edit.text().strip()
        video_folder = self.video_edit.text().strip()

        if not scrap_folder or not os.path.isdir(scrap_folder):
            QMessageBox.warning(self, "警告", "请先选择有效的刮削文件夹")
            return
        if not video_folder or not os.path.isdir(video_folder):
            QMessageBox.warning(self, "警告", "请先选择有效的视频文件夹")
            return

        self.logger.info("开始合并文件...")
        merger = FileMerger(
            scrap_folder=scrap_folder,
            target_folder=video_folder,
            logger=self.logger
        )
        merger.run(lambda message: self.logger.info(message))
