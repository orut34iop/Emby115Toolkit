"""
更新流派标签页 - macOS PyQt5 版本
"""

import os
import sys
import threading

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macos_gui.qt_utils import run_with_error_dialog, setup_qt_logger
from media_server.client import MediaServerClient
from utils.config import Config


class GenreUpdateTab(QWidget):
    """更新流派标签页"""

    task_finished = pyqtSignal(str)

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self._active_operator = None
        self._active_task = None
        self.task_finished.connect(self._on_task_finished)
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

        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("用户名："))
        self.edit_user = QLineEdit()
        user_layout.addWidget(self.edit_user)
        server_layout.addLayout(user_layout)

        server_group.setLayout(server_layout)
        layout.addWidget(server_group)

        # 执行按钮
        btn_layout = QHBoxLayout()
        self.btn_update = QPushButton("开始更新流派")
        self.btn_update.clicked.connect(self.update_genres)
        btn_layout.addWidget(self.btn_update)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_update)
        btn_layout.addWidget(self.btn_stop)
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

        self.logger = setup_qt_logger('genre_update', self.log_text, os.path.join(self.log_dir, 'genre_update.log'))
        self.load_config()
        self.edit_url.textChanged.connect(self.save_config)
        self.edit_api.textChanged.connect(self.save_config)
        self.edit_user.textChanged.connect(self.save_config)
        self.radio_emby.toggled.connect(self.save_config)
        self.radio_jellyfin.toggled.connect(self.save_config)

    def load_config(self):
        self.edit_url.setText(self.config.get('genre_update', 'server_url', ''))
        self.edit_api.setText(self.config.get('genre_update', 'api_key', ''))
        self.edit_user.setText(self.config.get('genre_update', 'username', ''))
        server_type = self.config.get('genre_update', 'server_type', 'emby')
        self.radio_jellyfin.setChecked(server_type == 'jellyfin')
        self.radio_emby.setChecked(server_type != 'jellyfin')

    def save_config(self):
        self.config.set('genre_update', 'server_url', self.edit_url.text().strip())
        self.config.set('genre_update', 'api_key', self.edit_api.text().strip())
        self.config.set('genre_update', 'username', self.edit_user.text().strip())
        self.config.set('genre_update', 'server_type', self.selected_server_type())
        self.config.save()

    def selected_server_type(self):
        return 'jellyfin' if self.radio_jellyfin.isChecked() else 'emby'

    def update_genres(self):
        return run_with_error_dialog(self, self.logger, "更新流派", self._update_genres)

    def _update_genres(self):
        if self._active_task and self._active_task.is_alive():
            self.logger.warning("已有流派更新任务正在运行")
            return

        server_url = self.edit_url.text().strip()
        api_key = self.edit_api.text().strip()
        username = self.edit_user.text().strip()
        server_type = self.selected_server_type()

        if not server_url or not api_key or not username:
            QMessageBox.warning(self, "警告", "请先填写服务器地址、API Key 和用户名")
            return

        self.logger.info(f"开始更新流派，服务器类型: {server_type}")
        operator = MediaServerClient(
            server_url=server_url, api_key=api_key, username=username, logger=self.logger, server_type=server_type
        )
        task = operator.update_genres(lambda message: self.logger.info(message))
        if task and hasattr(task, "is_alive"):
            self._active_operator = operator
            self._active_task = task
            self._set_running(True)
            threading.Thread(target=self._wait_for_task, args=(task,), daemon=True).start()
        return task

    def stop_update(self):
        if self._active_operator and self._active_task and self._active_task.is_alive():
            self._active_operator.request_stop()
            self.btn_stop.setEnabled(False)
            self.logger.info("正在停止流派更新，请等待当前请求结束...")
        else:
            self.logger.warning("当前没有正在运行的流派更新任务")

    def _set_running(self, running):
        self.btn_update.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def _wait_for_task(self, task):
        task.join()
        self.task_finished.emit("更新流派")

    def _on_task_finished(self, task_name):
        self._active_task = None
        self._active_operator = None
        self._set_running(False)
        self.logger.info(f"{task_name}后台任务结束")
