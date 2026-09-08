"""更新地区标签页 - macOS PyQt5。"""

from macos_gui.media_operation_tab import MediaOperationTab


class CountryUpdateTab(MediaOperationTab):
    section = 'country_update'
    operation = '更新地区'
    method = 'update_countries'

    def update_countries(self):
        return self.start_operation()
