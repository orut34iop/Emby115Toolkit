"""
macOS PyQt5 GUI 模块。
为 macOS 提供原生拖拽支持。
"""

from .country_update_tab import CountryUpdateTab
from .file_merge_tab import FileMergeTab
from .folder_tools_tab import FolderToolsTab
from .genre_update_tab import GenreUpdateTab
from .main_window import MainWindow
from .symlink_export_tab import SymlinkExportTab
from .tree_mirror_tab import TreeMirrorTab
from .version_merge_tab import VersionMergeTab

__all__ = [
    'MainWindow',
    'SymlinkExportTab',
    'FolderToolsTab',
    'FileMergeTab',
    'VersionMergeTab',
    'GenreUpdateTab',
    'CountryUpdateTab',
    'TreeMirrorTab',
]
