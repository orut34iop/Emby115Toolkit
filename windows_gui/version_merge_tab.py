"""合并版本标签页 - Windows tkinter。"""

from windows_gui.media_operation_tab import MediaOperationTab


class VersionMergeTab(MediaOperationTab):
    section = 'version_merge'
    operation = '合并版本'
    method = 'merge_versions'

    def merge_versions(self):
        return self.start_operation()
