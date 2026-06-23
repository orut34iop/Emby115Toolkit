"""
合并版本标签页 - PyQt5 版本
"""

import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QGroupBox, QMessageBox,
    QRadioButton, QButtonGroup
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from emby115_v1.utils.config import Config
from emby115_v1.emby.EmbyOperator import EmbyOperator
from emby115_v1.qt_gui.qt_utils import run_with_error_dialog, setup_qt_logger


class VersionTab(QWidget):
    """合并版本标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
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
            'merge_version',
            self.log_text,
            os.path.join(self.log_dir, 'merge_version.log')
        )
        self.load_config()
        self.edit_url.textChanged.connect(self.save_config)
        self.edit_api.textChanged.connect(self.save_config)
        self.radio_emby.toggled.connect(self.save_config)
        self.radio_jellyfin.toggled.connect(self.save_config)

    def load_config(self):
        self.edit_url.setText(self.config.get('merge_version', 'emby_url', ''))
        self.edit_api.setText(self.config.get('merge_version', 'emby_api', ''))
        server_type = self.config.get('merge_version', 'server_type', 'emby')
        self.radio_jellyfin.setChecked(server_type == 'jellyfin')
        self.radio_emby.setChecked(server_type != 'jellyfin')

    def save_config(self):
        self.config.set('merge_version', 'emby_url', self.edit_url.text().strip())
        self.config.set('merge_version', 'emby_api', self.edit_api.text().strip())
        self.config.set('merge_version', 'server_type', self.selected_server_type())
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

        self.logger.info(f"开始合并版本，服务器类型: {server_type}")
        operator = EmbyOperator(
            server_url=server_url,
            api_key=api_key,
            logger=self.logger,
            server_type=server_type
        )
        operator.merge_versions(lambda message: self.logger.info(message))
