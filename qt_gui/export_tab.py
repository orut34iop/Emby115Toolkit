"""
导出软链接标签页 - PyQt5 版本
支持原生 macOS 拖拽
"""

import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QSpinBox,
    QCheckBox, QGroupBox, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.config import Config
from autosync.SymlinkCreator import SymlinkCreator
from autosync.MetadataCopyer import MetadataCopyer


class DropLineEdit(QLineEdit):
    """支持拖拽的输入框"""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None, accept_files=True):
        super().__init__(parent)
        self.accept_files = accept_files
        self.setAcceptDrops(True)
        self.setPlaceholderText("拖拽文件夹到这里，或点击浏览按钮")

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e0f0ff; border: 2px dashed #0078d4;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """拖拽离开"""
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        """拖拽放下"""
        self.setStyleSheet("")
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.exists(path):
                files.append(path)

        if files:
            self.files_dropped.emit(files)
            # 设置第一个文件为文本
            self.setText(files[0])


class DropListWidget(QListWidget):
    """支持拖拽的列表框 - 支持多个文件夹拖拽"""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 启用拖拽接收
        self.setAcceptDrops(True)
        # 设置拖拽模式为只接收（不启用内部拖拽）
        self.setDragDropMode(QListWidget.DropOnly)
        # 设置选择模式为多选
        self.setSelectionMode(QListWidget.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入 - 接受 URL 拖拽"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e0f0ff; border: 2px dashed #0078d4;")
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """拖拽移动 - 必须接受才能放置"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """拖拽离开"""
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        """拖拽放下"""
        self.setStyleSheet("")
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                files.append(path)

        if files:
            self.files_dropped.emit(files)
            for f in files:
                item = QListWidgetItem(f)
                self.addItem(item)


class ExportTab(QWidget):
    """导出软链接标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self.init_ui()
        self.load_config()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # === 文件夹设置 ===
        folder_group = QGroupBox("文件夹设置")
        folder_layout = QVBoxLayout()

        # 链接文件夹
        link_label = QLabel("链接文件夹（拖拽或点击添加）：")
        folder_layout.addWidget(link_label)

        self.link_list = DropListWidget()
        self.link_list.setMaximumHeight(100)
        self.link_list.files_dropped.connect(self.on_link_folders_dropped)
        folder_layout.addWidget(self.link_list)

        link_btn_layout = QHBoxLayout()
        self.btn_add_link = QPushButton("添加文件夹")
        self.btn_add_link.clicked.connect(self.browse_link_folder)
        link_btn_layout.addWidget(self.btn_add_link)

        self.btn_clear_link = QPushButton("清空列表")
        self.btn_clear_link.clicked.connect(self.clear_link_folders)
        link_btn_layout.addWidget(self.btn_clear_link)
        link_btn_layout.addStretch()

        folder_layout.addLayout(link_btn_layout)

        # 目标文件夹
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标文件夹："))
        self.target_edit = DropLineEdit()
        self.target_edit.files_dropped.connect(self.on_target_dropped)
        target_layout.addWidget(self.target_edit)

        self.btn_browse_target = QPushButton("浏览")
        self.btn_browse_target.clicked.connect(self.browse_target_folder)
        target_layout.addWidget(self.btn_browse_target)

        folder_layout.addLayout(target_layout)
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)

        # === 路径替换设置 ===
        replace_group = QGroupBox("软链接文件路径替换设置")
        replace_layout = QVBoxLayout()

        self.chk_replace = QCheckBox("替换文件路径")
        self.chk_replace.stateChanged.connect(self.save_config)
        replace_layout.addWidget(self.chk_replace)

        original_layout = QHBoxLayout()
        original_layout.addWidget(QLabel("原路径："))
        self.original_edit = QLineEdit()
        self.original_edit.textChanged.connect(self.save_config)
        original_layout.addWidget(self.original_edit)
        replace_layout.addLayout(original_layout)

        replace_path_layout = QHBoxLayout()
        replace_path_layout.addWidget(QLabel("替换路径："))
        self.replace_edit = QLineEdit()
        self.replace_edit.textChanged.connect(self.save_config)
        replace_path_layout.addWidget(self.replace_edit)
        replace_layout.addLayout(replace_path_layout)

        replace_group.setLayout(replace_layout)
        layout.addWidget(replace_group)

        # === 115防封设置 ===
        protect_group = QGroupBox("115防封设置")
        protect_layout = QVBoxLayout()

        self.chk_protect = QCheckBox("开启115防封")
        self.chk_protect.stateChanged.connect(self.save_config)
        protect_layout.addWidget(self.chk_protect)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("文件操作时间间隔(秒)："))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(0, 60)
        self.spin_interval.setValue(4)
        self.spin_interval.valueChanged.connect(self.save_config)
        interval_layout.addWidget(self.spin_interval)
        interval_layout.addStretch()
        protect_layout.addLayout(interval_layout)

        protect_group.setLayout(protect_layout)
        layout.addWidget(protect_group)

        # === 同步设置 ===
        sync_group = QGroupBox("同步设置")
        sync_layout = QVBoxLayout()

        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel("同步线程数："))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 16)
        self.spin_threads.setValue(4)
        self.spin_threads.valueChanged.connect(self.save_config)
        thread_layout.addWidget(self.spin_threads)
        thread_layout.addStretch()
        sync_layout.addLayout(thread_layout)

        self.chk_tvshow = QCheckBox("只下载剧集tvshow.nfo")
        self.chk_tvshow.stateChanged.connect(self.save_config)
        sync_layout.addWidget(self.chk_tvshow)

        # 后缀设置
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("软链接后缀："))
        self.edit_link_suffix = QLineEdit(".mkv;.iso;.ts;.mp4;.avi;.rmvb;.wmv;.m2ts;.mpg;.flv;.rm;.m4v")
        self.edit_link_suffix.textChanged.connect(self.save_config)
        suffix_layout.addWidget(self.edit_link_suffix)
        sync_layout.addLayout(suffix_layout)

        meta_layout = QHBoxLayout()
        meta_layout.addWidget(QLabel("元数据后缀："))
        self.edit_meta_suffix = QLineEdit(".nfo;.jpg;.png;.ass;.srt")
        self.edit_meta_suffix.textChanged.connect(self.save_config)
        meta_layout.addWidget(self.edit_meta_suffix)
        sync_layout.addLayout(meta_layout)

        sync_group.setLayout(sync_layout)
        layout.addWidget(sync_group)

        # === 操作按钮 ===
        btn_layout = QHBoxLayout()

        self.btn_sync_all = QPushButton("一键全同步")
        self.btn_sync_all.clicked.connect(self.sync_all)
        btn_layout.addWidget(self.btn_sync_all)

        self.btn_create_link = QPushButton("创建软链接")
        self.btn_create_link.clicked.connect(self.create_symlink)
        btn_layout.addWidget(self.btn_create_link)

        self.btn_download_meta = QPushButton("下载元数据")
        self.btn_download_meta.clicked.connect(self.download_metadata)
        btn_layout.addWidget(self.btn_download_meta)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # === 日志区域 ===
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 创建日志处理器
        self.logger = self.create_logger()

    def create_logger(self):
        """创建日志处理器"""
        import logging
        from logging import Handler

        class QTextEditHandler(Handler):
            def __init__(self, widget):
                super().__init__()
                self.widget = widget

            def emit(self, record):
                msg = self.format(record)
                from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
                self.widget.append(msg)

        # 设置日志
        import logging
        logger = logging.getLogger('export_symlink')
        logger.setLevel(logging.INFO)

        handler = QTextEditHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                     datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def on_link_folders_dropped(self, files):
        """链接文件夹被拖拽"""
        self.logger.info(f"通过拖拽添加 {len(files)} 个文件夹")
        self.save_config()

    def on_target_dropped(self, files):
        """目标文件夹被拖拽"""
        if files:
            self.logger.info(f"设置目标文件夹: {files[0]}")
            self.save_config()

    def browse_link_folder(self):
        """浏览链接文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择链接文件夹")
        if folder:
            item = QListWidgetItem(folder)
            self.link_list.addItem(item)
            self.save_config()

    def browse_target_folder(self):
        """浏览目标文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择目标文件夹")
        if folder:
            self.target_edit.setText(folder)
            self.save_config()

    def clear_link_folders(self):
        """清空链接文件夹列表"""
        self.link_list.clear()
        self.save_config()

    def load_config(self):
        """从配置文件加载设置"""
        # 加载链接文件夹
        link_folders = self.config.get('export_symlink', 'link_folders', [])
        self.link_list.clear()
        for folder in link_folders:
            if folder:
                self.link_list.addItem(QListWidgetItem(folder))

        # 加载目标文件夹
        target = self.config.get('export_symlink', 'target_folder', '')
        self.target_edit.setText(target)

        # 加载其他设置
        self.spin_threads.setValue(self.config.get('export_symlink', 'thread_count', 4))
        self.spin_interval.setValue(self.config.get('export_symlink', 'op_interval_sec', 4))
        self.chk_protect.setChecked(self.config.get('export_symlink', 'enable_115_protect', False))
        self.chk_replace.setChecked(self.config.get('export_symlink', 'enable_replace_path', False))
        self.chk_tvshow.setChecked(self.config.get('export_symlink', 'only_tvshow_nfo', True))

        # 路径替换
        self.original_edit.setText(self.config.get('export_symlink', 'original_path', ''))
        self.replace_edit.setText(self.config.get('export_symlink', 'replace_path', ''))

        # 后缀
        link_suffixes = self.config.get('export_symlink', 'link_suffixes', [])
        if link_suffixes:
            self.edit_link_suffix.setText(';'.join(link_suffixes))

        meta_suffixes = self.config.get('export_symlink', 'meta_suffixes', [])
        if meta_suffixes:
            self.edit_meta_suffix.setText(';'.join(meta_suffixes))

        self.logger.info("配置加载完成")

    def save_config(self):
        """保存设置到配置文件"""
        # 获取链接文件夹列表
        link_folders = []
        for i in range(self.link_list.count()):
            item = self.link_list.item(i)
            if item:
                link_folders.append(item.text())

        self.config.set('export_symlink', 'link_folders', link_folders)
        self.config.set('export_symlink', 'target_folder', self.target_edit.text())
        self.config.set('export_symlink', 'thread_count', self.spin_threads.value())
        self.config.set('export_symlink', 'op_interval_sec', self.spin_interval.value())
        self.config.set('export_symlink', 'enable_115_protect', self.chk_protect.isChecked())
        self.config.set('export_symlink', 'enable_replace_path', self.chk_replace.isChecked())
        self.config.set('export_symlink', 'only_tvshow_nfo', self.chk_tvshow.isChecked())
        self.config.set('export_symlink', 'original_path', self.original_edit.text())
        self.config.set('export_symlink', 'replace_path', self.replace_edit.text())

        # 后缀
        link_suffixes = [s.strip() for s in self.edit_link_suffix.text().split(';') if s.strip()]
        self.config.set('export_symlink', 'link_suffixes', link_suffixes)

        meta_suffixes = [s.strip() for s in self.edit_meta_suffix.text().split(';') if s.strip()]
        self.config.set('export_symlink', 'meta_suffixes', meta_suffixes)

        self.config.save()

    def sync_all(self):
        """一键全同步"""
        self.logger.info("=== 开始全同步操作 ===")
        self.create_symlink()

    def create_symlink(self):
        """创建软链接"""
        # 获取配置
        source_folders = []
        for i in range(self.link_list.count()):
            item = self.link_list.item(i)
            if item:
                source_folders.append(item.text())

        target_folder = self.target_edit.text()

        if not source_folders:
            QMessageBox.warning(self, "警告", "请先添加源文件夹")
            return

        if not target_folder:
            QMessageBox.warning(self, "警告", "请先设置目标文件夹")
            return

        # 创建软链接
        soft_link_extensions = tuple(
            s.strip() for s in self.edit_link_suffix.text().split(';') if s.strip()
        )

        self.logger.info("开始创建软链接...")

        creator = SymlinkCreator(
            source_folders=source_folders,
            target_folder=target_folder,
            allowed_extensions=soft_link_extensions,
            num_threads=self.spin_threads.value(),
            enable_115_protect=self.chk_protect.isChecked(),
            op_interval_sec=self.spin_interval.value(),
            enable_replace_path=self.chk_replace.isChecked(),
            original_path=self.original_edit.text(),
            replace_path=self.replace_edit.text(),
            logger=self.logger
        )

        def on_complete(message):
            self.logger.info(message)

        creator.run(on_complete)

    def download_metadata(self):
        """下载元数据"""
        self.logger.info("开始下载元数据...")
        # 实现下载元数据逻辑
