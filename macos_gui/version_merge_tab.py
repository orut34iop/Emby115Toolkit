"""
合并版本标签页 - macOS PyQt5 版本
"""

import os
import sys

from PyQt5.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macos_gui.qt_utils import run_with_error_dialog, setup_qt_logger
from macos_gui.task_helpers import BackgroundTaskMixin
from media_server.client import MediaServerClient
from utils.config import Config


class VersionMergeTab(BackgroundTaskMixin, QWidget):
    """合并版本标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self._init_task_state()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 媒体服务器设置
        server_group = QGroupBox("媒体服务器设置")
        server_layout = QVBoxLayout()

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("服务器类型："))
        self.radio_emby = QRadioButton("Emby")
        self.radio_jellyfin = QRadioButton("Jellyfin")
        self.radio_emby.setChecked(True)
        self.server_type_group = QButtonGroup(self)
        self.server_type_group.addButton(self.radio_emby)
        self.server_type_group.addButton(self.radio_jellyfin)
        type_layout.addWidget(self.radio_emby)
        type_layout.addWidget(self.radio_jellyfin)
        type_layout.addStretch()
        server_layout.addLayout(type_layout)

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

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_merge = QPushButton("开始合并版本")
        self.btn_merge.clicked.connect(self.merge_versions)
        btn_layout.addWidget(self.btn_merge)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_background_task)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._register_task_buttons(self.btn_merge)

        layout.addWidget(self._create_progress_group())
        layout.addWidget(self._create_log_group(), 1)

        self.logger = setup_qt_logger('version_merge', self.log_text, os.path.join(self.log_dir, 'version_merge.log'))
        self.load_config()
        self.edit_url.textChanged.connect(self.save_config)
        self.edit_api.textChanged.connect(self.save_config)
        self.radio_emby.toggled.connect(self.save_config)
        self.radio_jellyfin.toggled.connect(self.save_config)

    def load_config(self):
        self.edit_url.setText(self.config.get('version_merge', 'server_url', ''))
        self.edit_api.setText(self.config.get('version_merge', 'api_key', ''))
        server_type = self.config.get('version_merge', 'server_type', 'emby')
        self.radio_jellyfin.setChecked(server_type == 'jellyfin')
        self.radio_emby.setChecked(server_type != 'jellyfin')

    def save_config(self):
        self.config.set('version_merge', 'server_url', self.edit_url.text().strip())
        self.config.set('version_merge', 'api_key', self.edit_api.text().strip())
        self.config.set('version_merge', 'server_type', self.selected_server_type())
        self.config.save()

    def selected_server_type(self):
        return 'jellyfin' if self.radio_jellyfin.isChecked() else 'emby'

    def merge_versions(self):
        return run_with_error_dialog(self, self.logger, "合并版本", self._merge_versions)

    def _merge_versions(self):
        server_url = self.edit_url.text().strip()
        api_key = self.edit_api.text().strip()
        server_type = self.selected_server_type()

        if not server_url or not api_key:
            QMessageBox.warning(self, "警告", "请先填写服务器地址和 API Key")
            return

        def task():
            self.logger.info(f"开始合并版本，服务器类型: {server_type}")
            operator = self._track_worker(
                MediaServerClient(server_url=server_url, api_key=api_key, logger=self.logger, server_type=server_type)
            )
            worker_thread = operator.merge_versions(lambda payload: self._task_signals.progress.emit(payload))
            if worker_thread:
                worker_thread.join()

        self._start_background_task("合并版本", task)
