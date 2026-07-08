"""
导出软链接标签页 - macOS PyQt5 版本
支持原生 macOS 拖拽
"""

import os
import sys
import threading

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from macos_gui.qt_utils import run_with_error_dialog, setup_qt_logger
from macos_gui.task_helpers import BackgroundTaskMixin
from services.metadata_copier import MetadataCopier
from services.symlink_creator import SymlinkCreator
from utils.config import Config


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
            # 设置第一个文件为文本
            self.setText(files[0])
            self.files_dropped.emit(files)


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
            for f in files:
                item = QListWidgetItem(f)
                self.addItem(item)
            self.files_dropped.emit(files)


class SymlinkExportTab(BackgroundTaskMixin, QWidget):
    """导出软链接标签页"""

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = log_dir
        self.config = Config()
        self._init_task_state()
        self._loading_config = False
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
        self.target_edit.textChanged.connect(self.save_config)
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

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_background_task)
        btn_layout.addWidget(self.btn_stop)

        btn_layout.addStretch()

        self.chk_overwrite_meta = QCheckBox("覆盖nfo和图片文件")
        self.chk_overwrite_meta.stateChanged.connect(self.save_config)
        btn_layout.addWidget(self.chk_overwrite_meta)

        layout.addLayout(btn_layout)
        self._register_task_buttons(
            self.btn_sync_all,
            self.btn_create_link,
            self.btn_download_meta,
            self.btn_add_link,
            self.btn_clear_link,
            self.btn_browse_target,
            self.chk_overwrite_meta,
        )

        # === 进度和日志区域 ===
        layout.addWidget(self._create_progress_group())
        layout.addWidget(self._create_log_group(), 1)

        # 创建日志处理器
        self.logger = self.create_logger()

    def create_logger(self):
        """创建日志处理器"""
        log_file = os.path.join(self.log_dir, 'symlink_export.log')
        return setup_qt_logger('symlink_export', self.log_text, log_file)

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
        self._loading_config = True
        try:
            # 加载链接文件夹
            link_folders = self.config.get('symlink_export', 'link_folders', [])
            self.link_list.clear()
            for folder in link_folders:
                if folder:
                    self.link_list.addItem(QListWidgetItem(folder))

            # 加载目标文件夹
            target = self.config.get('symlink_export', 'target_folder', '')
            self.target_edit.setText(target)

            # 加载其他设置
            self.spin_threads.setValue(self.config.get('symlink_export', 'thread_count', 4))
            self.chk_replace.setChecked(self.config.get('symlink_export', 'enable_replace_path', False))
            self.chk_tvshow.setChecked(self.config.get('symlink_export', 'only_tvshow_nfo', True))
            self.chk_overwrite_meta.setChecked(self.config.get('symlink_export', 'overwrite_metadata', False))

            # 路径替换
            self.original_edit.setText(self.config.get('symlink_export', 'original_path', ''))
            self.replace_edit.setText(self.config.get('symlink_export', 'replace_path', ''))

            # 后缀
            link_suffixes = self.config.get('symlink_export', 'link_suffixes', [])
            if link_suffixes:
                self.edit_link_suffix.setText(';'.join(link_suffixes))

            meta_suffixes = self.config.get('symlink_export', 'meta_suffixes', [])
            if meta_suffixes:
                self.edit_meta_suffix.setText(';'.join(meta_suffixes))
        finally:
            self._loading_config = False

        self.logger.info("配置加载完成")

    def save_config(self):
        """保存设置到配置文件"""
        if self._loading_config:
            return

        # 获取链接文件夹列表
        link_folders = []
        for i in range(self.link_list.count()):
            item = self.link_list.item(i)
            if item:
                link_folders.append(item.text())

        self.config.set('symlink_export', 'link_folders', link_folders)
        self.config.set('symlink_export', 'target_folder', self.target_edit.text())
        self.config.set('symlink_export', 'thread_count', self.spin_threads.value())
        self.config.set('symlink_export', 'enable_replace_path', self.chk_replace.isChecked())
        self.config.set('symlink_export', 'only_tvshow_nfo', self.chk_tvshow.isChecked())
        self.config.set('symlink_export', 'overwrite_metadata', self.chk_overwrite_meta.isChecked())
        self.config.set('symlink_export', 'original_path', self.original_edit.text())
        self.config.set('symlink_export', 'replace_path', self.replace_edit.text())

        # 后缀
        link_suffixes = [s.strip() for s in self.edit_link_suffix.text().split(';') if s.strip()]
        self.config.set('symlink_export', 'link_suffixes', link_suffixes)

        meta_suffixes = [s.strip() for s in self.edit_meta_suffix.text().split(';') if s.strip()]
        self.config.set('symlink_export', 'meta_suffixes', meta_suffixes)

        self.config.save()

    def sync_all(self):
        """一键全同步"""
        return run_with_error_dialog(self, self.logger, "全同步", self._sync_all)

    def _sync_all(self):
        """一键全同步"""
        config = self._collect_export_config("all")
        if not config:
            return

        def task():
            self.logger.info("=== 开始全同步操作 ===")
            errors = []

            def run_child(child_name, child_task):
                try:
                    self.logger.info(f"=== {child_name}任务启动 ===")
                    child_task(config)
                    self.logger.info(f"=== {child_name}任务完成 ===")
                except Exception as e:
                    errors.append((child_name, e))
                    self.logger.exception(f"{child_name}执行异常: {e}")

            child_threads = [
                threading.Thread(
                    target=run_child,
                    args=("创建软链接", self._run_symlink_create),
                    daemon=True,
                ),
                threading.Thread(
                    target=run_child,
                    args=("下载元数据", self._run_metadata_copy),
                    daemon=True,
                ),
            ]

            for child_thread in child_threads:
                child_thread.start()

            for child_thread in child_threads:
                child_thread.join()

            if errors:
                failed_tasks = "、".join(name for name, _ in errors)
                raise RuntimeError(f"全同步子任务失败: {failed_tasks}")

            self.logger.info("=== 全同步操作完成 ===")

        self._start_background_task("全同步", task)

    def _collect_export_config(self, mode):
        link_folders = []
        for i in range(self.link_list.count()):
            item = self.link_list.item(i)
            if item:
                link_folders.append(item.text())

        target_folder = self.target_edit.text()

        if not link_folders:
            QMessageBox.warning(self, "警告", "请先添加源文件夹")
            return None

        if not target_folder:
            QMessageBox.warning(self, "警告", "请先设置目标文件夹")
            return None

        link_extensions = tuple(s.strip() for s in self.edit_link_suffix.text().split(';') if s.strip())
        meta_extensions = tuple(s.strip() for s in self.edit_meta_suffix.text().split(';') if s.strip())

        if mode in ("link", "all") and not link_extensions:
            QMessageBox.warning(self, "警告", "请先设置软链接后缀")
            return None

        if mode in ("metadata", "all") and not meta_extensions:
            QMessageBox.warning(self, "警告", "请先设置元数据后缀")
            return None

        return {
            "link_folders": link_folders,
            "target_folder": target_folder,
            "link_extensions": link_extensions,
            "meta_extensions": meta_extensions,
            "thread_count": self.spin_threads.value(),
            "enable_replace_path": self.chk_replace.isChecked(),
            "original_path": self.original_edit.text(),
            "replace_path": self.replace_edit.text(),
            "only_tvshow_nfo": self.chk_tvshow.isChecked(),
            "overwrite_metadata": self.chk_overwrite_meta.isChecked(),
        }

    def _run_symlink_create(self, config):
        self.logger.info("开始创建软链接...")

        creator = self._track_worker(SymlinkCreator(
            link_folders=config["link_folders"],
            target_folder=config["target_folder"],
            allowed_extensions=config["link_extensions"],
            thread_count=config["thread_count"],
            enable_replace_path=config["enable_replace_path"],
            original_path=config["original_path"],
            replace_path=config["replace_path"],
            only_tvshow_nfo=config["only_tvshow_nfo"],
            logger=self.logger,
        ))
        creator.run(lambda payload: self._task_signals.progress.emit(payload))

    def _run_metadata_copy(self, config):
        self.logger.info("开始下载元数据...")
        copier = self._track_worker(MetadataCopier(
            source_folders=config["link_folders"],
            target_folder=config["target_folder"],
            allowed_extensions=config["meta_extensions"],
            thread_count=config["thread_count"],
            only_tvshow_nfo=config["only_tvshow_nfo"],
            overwrite_existing=config["overwrite_metadata"],
            logger=self.logger,
        ))
        thread = copier.run(lambda payload: self._task_signals.progress.emit(payload))
        if thread:
            thread.join()

    def create_symlink(self):
        """创建软链接"""
        return run_with_error_dialog(self, self.logger, "创建软链接", self._create_symlink)

    def _create_symlink(self):
        """创建软链接"""
        config = self._collect_export_config("link")
        if not config:
            return

        self._start_background_task("创建软链接", lambda: self._run_symlink_create(config))

    def download_metadata(self):
        """下载元数据"""
        return run_with_error_dialog(self, self.logger, "下载元数据", self._download_metadata)

    def _download_metadata(self):
        """下载元数据"""
        config = self._collect_export_config("metadata")
        if not config:
            return

        self._start_background_task("下载元数据", lambda: self._run_metadata_copy(config))
