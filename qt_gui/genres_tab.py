"""
Emby更新流派标签页 - PyQt5 版本
"""

import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QGroupBox, QMessageBox
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from emby.EmbyOperator import EmbyOperator
from qt_gui.qt_utils import run_with_error_dialog, setup_qt_logger


class GenresTab(QWidget):
    """Emby更新流派标签页"""

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
            'update_genres',
            self.log_text,
            os.path.join(self.log_dir, 'update_genres.log')
        )
        self.load_config()
        self.edit_url.textChanged.connect(self.save_config)
        self.edit_api.textChanged.connect(self.save_config)
        self.edit_user.textChanged.connect(self.save_config)

    def load_config(self):
        self.edit_url.setText(self.config.get('update_genres', 'emby_url', ''))
        self.edit_api.setText(self.config.get('update_genres', 'emby_api', ''))
        self.edit_user.setText(self.config.get('update_genres', 'emby_username', ''))

    def save_config(self):
        self.config.set('update_genres', 'emby_url', self.edit_url.text().strip())
        self.config.set('update_genres', 'emby_api', self.edit_api.text().strip())
        self.config.set('update_genres', 'emby_username', self.edit_user.text().strip())
        self.config.save()

    def update_genres(self):
        return run_with_error_dialog(self, self.logger, "Emby更新流派", self._update_genres)

    def _update_genres(self):
        server_url = self.edit_url.text().strip()
        api_key = self.edit_api.text().strip()
        user_name = self.edit_user.text().strip()

        if not server_url or not api_key or not user_name:
            QMessageBox.warning(self, "警告", "请先填写 Emby 服务器地址、API Key 和用户名")
            return

        self.logger.info("开始更新流派...")
        operator = EmbyOperator(
            server_url=server_url,
            api_key=api_key,
            user_name=user_name,
            logger=self.logger
        )
        operator.update_genress(lambda message: self.logger.info(message))
