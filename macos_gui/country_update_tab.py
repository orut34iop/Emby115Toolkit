"""更新地区标签页 - macOS PyQt5 版本。"""

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


class CountryUpdateTab(BackgroundTaskMixin, QWidget):
    """更新制片国家/地区标签页。"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self._init_task_state()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

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

        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("用户名："))
        self.edit_user = QLineEdit()
        user_layout.addWidget(self.edit_user)
        server_layout.addLayout(user_layout)

        server_group.setLayout(server_layout)
        layout.addWidget(server_group)

        mode_group = QGroupBox("扫描模式")
        mode_layout = QHBoxLayout()
        self.radio_incremental = QRadioButton("快速增量（推荐）")
        self.radio_full_scan = QRadioButton("完整扫描修复")
        self.radio_incremental.setChecked(True)
        self.scan_mode_group = QButtonGroup(self)
        self.scan_mode_group.addButton(self.radio_incremental)
        self.scan_mode_group.addButton(self.radio_full_scan)
        mode_layout.addWidget(self.radio_incremental)
        mode_layout.addWidget(self.radio_full_scan)
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        btn_layout = QHBoxLayout()
        self.btn_update = QPushButton("开始更新地区")
        self.btn_update.clicked.connect(self.update_countries)
        btn_layout.addWidget(self.btn_update)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_background_task)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._register_task_buttons(self.btn_update)

        layout.addWidget(self._create_progress_group())
        layout.addWidget(self._create_log_group(), 1)

        self.logger = setup_qt_logger(
            'country_update',
            self.log_text,
            os.path.join(self.log_dir, 'country_update.log'),
        )
        self.load_config()
        self.edit_url.textChanged.connect(self.save_config)
        self.edit_api.textChanged.connect(self.save_config)
        self.edit_user.textChanged.connect(self.save_config)
        self.radio_emby.toggled.connect(self.save_config)
        self.radio_jellyfin.toggled.connect(self.save_config)
        self.radio_incremental.toggled.connect(self.save_config)
        self.radio_full_scan.toggled.connect(self.save_config)

    def load_config(self):
        config = self.config.get('country_update') or {}
        if not all(config.get(key) for key in ('server_url', 'api_key', 'username')):
            config = self.config.get('genre_update') or config

        self.edit_url.setText(config.get('server_url', ''))
        self.edit_api.setText(config.get('api_key', ''))
        self.edit_user.setText(config.get('username', ''))
        server_type = config.get('server_type', 'emby')
        self.radio_jellyfin.setChecked(server_type == 'jellyfin')
        self.radio_emby.setChecked(server_type != 'jellyfin')
        scan_mode = config.get('scan_mode', 'incremental')
        self.radio_full_scan.setChecked(scan_mode == 'full')
        self.radio_incremental.setChecked(scan_mode != 'full')

    def save_config(self):
        self.config.set('country_update', 'server_url', self.edit_url.text().strip())
        self.config.set('country_update', 'api_key', self.edit_api.text().strip())
        self.config.set('country_update', 'username', self.edit_user.text().strip())
        self.config.set('country_update', 'server_type', self.selected_server_type())
        self.config.set('country_update', 'scan_mode', 'full' if self.radio_full_scan.isChecked() else 'incremental')
        self.config.save()

    def save_sync_state(self, state):
        self.config.set('country_update', 'sync_state', state)
        self.config.save()

    def selected_server_type(self):
        return 'jellyfin' if self.radio_jellyfin.isChecked() else 'emby'

    def update_countries(self):
        return run_with_error_dialog(self, self.logger, "更新地区", self._update_countries)

    def _update_countries(self):
        server_url = self.edit_url.text().strip()
        api_key = self.edit_api.text().strip()
        username = self.edit_user.text().strip()
        server_type = self.selected_server_type()
        full_scan = self.radio_full_scan.isChecked()
        sync_state = self.config.get('country_update', 'sync_state', {})

        if not server_url or not api_key or not username:
            QMessageBox.warning(self, "警告", "请先填写服务器地址、API Key 和用户名")
            return

        def task():
            self.logger.info(f"开始更新地区，服务器类型: {server_type}")
            operator = self._track_worker(
                MediaServerClient(
                    server_url=server_url,
                    api_key=api_key,
                    username=username,
                    logger=self.logger,
                    server_type=server_type,
                )
            )
            worker_thread = operator.update_countries(
                lambda payload: self._task_signals.progress.emit(payload),
                full_scan=full_scan,
                sync_state=sync_state,
                state_callback=self.save_sync_state,
            )
            if worker_thread:
                worker_thread.join()

        return self._start_background_task("更新地区", task)
