"""Shared remote-media workflow: snapshot a profile, run, persist state, then unlock."""

import os
import threading

from PyQt5.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from macos_gui.media_profiles import ProfilePicker
from macos_gui.qt_utils import setup_qt_logger
from macos_gui.task_helpers import BackgroundTaskMixin
from media_server.client import MediaServerClient
from utils.config import Config
from utils.media_profiles import connection, get_media_profiles


class MediaOperationTab(BackgroundTaskMixin, QWidget):
    section = ''
    operation = ''
    method = ''

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.profiles = get_media_profiles(self.config)
        self._profile_token = None
        self._cancel_event = None
        self._init_task_state()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self.profile_picker = ProfilePicker(self.profiles, self)
        layout.addWidget(self.profile_picker)
        if self.section != 'version_merge':
            mode_group = QGroupBox('扫描模式')
            modes = QHBoxLayout(mode_group)
            self.radio_incremental = QRadioButton('快速增量（推荐）')
            self.radio_full_scan = QRadioButton('完整扫描修复')
            self.scan_mode_group = QButtonGroup(self)
            for button in (self.radio_incremental, self.radio_full_scan):
                self.scan_mode_group.addButton(button)
                modes.addWidget(button)
                button.clicked.connect(self.save_config)
            modes.addStretch()
            layout.addWidget(mode_group)
        buttons = QHBoxLayout()
        start = QPushButton('开始' + self.operation)
        start.clicked.connect(self.start_operation)
        self.btn_merge = self.btn_update = start
        buttons.addWidget(start)
        self.btn_stop = QPushButton('停止')
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_background_task)
        buttons.addWidget(self.btn_stop)
        buttons.addStretch()
        layout.addLayout(buttons)
        self._register_task_buttons(start)
        layout.addWidget(self._create_progress_group())
        layout.addWidget(self._create_log_group(), 1)
        self.logger = setup_qt_logger(self.section, self.log_text, os.path.join(log_dir, self.section + '.log'))
        unsubscribe = self.profiles.subscribe(self.load_config)
        self.destroyed.connect(unsubscribe)
        self.load_config()

    def load_config(self):
        self.btn_merge.setEnabled(not self.profiles.busy and self.profiles.active is not None)
        if self.section != 'version_merge':
            full = self.profiles.settings(self.section).get('scan_mode') == 'full'
            self.radio_full_scan.setChecked(full)
            self.radio_incremental.setChecked(not full)
            for button in (self.radio_incremental, self.radio_full_scan):
                button.setEnabled(not self.profiles.busy and self.profiles.active is not None)

    def save_config(self):
        try:
            self.profiles.set_scan_mode(self.section, 'full' if self.radio_full_scan.isChecked() else 'incremental')
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, '保存失败', str(exc))
            self.load_config()

    def start_operation(self):
        if self._active_task is not None:
            return
        try:
            token, snapshot = self.profiles.begin_task(self.section)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, '无法开始', str(exc))
            return
        self._profile_token = token
        profile = snapshot['profile']
        settings = profile.get('settings', {}).get(self.section, {})
        self.logger.info(f"{self.operation} → {profile['name']} ({profile['server_type']}, {profile['server_url']})")

        cancel_event = self._cancel_event = threading.Event()

        def task():
            if cancel_event.is_set():
                return
            operator = self._track_worker(
                MediaServerClient(**connection(profile), logger=self.logger, cancel_event=cancel_event)
            )
            kwargs = {}
            if self.section != 'version_merge':
                kwargs = dict(
                    full_scan=settings.get('scan_mode') == 'full',
                    sync_state=settings.get('sync_state', {}),
                    state_callback=lambda state: self.profiles.save_task_state(token, state),
                )
            worker = getattr(operator, self.method)(self._task_signals.progress.emit, **kwargs)
            if worker:
                worker.join()

        try:
            return self._start_background_task(self.operation, task)
        except Exception:
            self._active_task = None
            self._set_task_running(False)
            self.profiles.end_task(token)
            self._profile_token = None
            self.logger.exception('无法启动媒体任务')
            return None

    def _on_background_task_finished(self, task_name):
        super()._on_background_task_finished(task_name)
        token, self._profile_token = self._profile_token, None
        if token:
            self.profiles.end_task(token)

    def stop_background_task(self):
        if self._cancel_event is not None:
            self._cancel_event.set()
        super().stop_background_task()
