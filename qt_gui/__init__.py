"""
PyQt5 GUI 模块
为 macOS 提供原生拖拽支持
"""

from .main_window import MainWindow
from .export_tab import ExportTab
from .folder_tab import FolderTab
from .duplicate_tab import DuplicateTab
from .merge_tab import MergeTab
from .version_tab import VersionTab
from .genres_tab import GenresTab
from .mirror_tab import MirrorTab

__all__ = [
    'MainWindow',
    'ExportTab',
    'FolderTab',
    'DuplicateTab',
    'MergeTab',
    'VersionTab',
    'GenresTab',
    'MirrorTab',
]
