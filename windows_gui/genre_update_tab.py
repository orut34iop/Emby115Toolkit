"""更新流派标签页 - Windows tkinter。"""

from windows_gui.media_operation_tab import MediaOperationTab


class GenreUpdateTab(MediaOperationTab):
    section = 'genre_update'
    operation = '更新流派'
    method = 'update_genres'

    def update_genres(self):
        return self.start_operation()
