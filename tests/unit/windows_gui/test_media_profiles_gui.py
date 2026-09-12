"""Native Windows UI verification; intentionally never run tkinter on macOS/Linux."""

import sys
import threading
import time

import pytest

if sys.platform != 'win32':
    pytest.skip('Windows tkinter frontend only', allow_module_level=True)

import tkinter as tk
from tkinter import messagebox

from tkinterdnd2 import TkinterDnD

from utils.config import Config
from windows_gui.media_profiles import ProfileManager
from windows_main import EmbyToolkit


@pytest.fixture
def app(tmp_path, monkeypatch):
    def initialize(self):
        self.config_dir = str(tmp_path)
        self.config_file = str(tmp_path / 'config.yaml')
        self._create_default_config()
        self._load_config()

    monkeypatch.setattr(Config, '_initialize', initialize)
    Config._instance = None
    root = TkinterDnD.Tk()
    root.geometry('1000x760')
    toolkit = EmbyToolkit(root)
    root.update()
    yield root, toolkit
    root.destroy()
    Config._instance = None


def pump(root, predicate, timeout=5):
    deadline = time.monotonic() + timeout

    def check():
        if predicate() or time.monotonic() >= deadline:
            root.quit()
        else:
            root.after(10, check)

    root.after(0, check)
    root.mainloop()
    assert predicate()


def add_profiles(store):
    first = store.save_profile(
        dict(
            name='主机 Jellyfin',
            group='主机',
            server_type='jellyfin',
            server_url='http://host:8096',
            api_key='first',
            username='admin',
        )
    )
    second = store.save_profile(
        dict(
            name='主机 Emby',
            group='主机',
            server_type='emby',
            server_url='http://host:8097',
            api_key='second',
            username='user',
        )
    )
    return first, second


def test_seven_tabs_share_manager_and_picker(app):
    root, toolkit = app
    first, second = add_profiles(toolkit.profiles)
    assert [toolkit.notebook.tab(t, 'text') for t in toolkit.notebook.tabs()] == [
        '导出软链接',
        '文件夹操作',
        '文件合并',
        '合并版本',
        '更新流派',
        '更新地区',
        '115目录树镜像',
    ]
    for index in range(7):
        toolkit.notebook.select(index)
        root.update()
        assert toolkit.profile_button.winfo_viewable()
        dialog = ProfileManager(root, toolkit.profiles, toolkit.notebook.tab(index, 'text'))
        root.update()
        dialog.load_profile(second)
        assert toolkit.profiles.active['id'] == first
        dialog.use_profile()
        root.update()
        assert toolkit.notebook.index(toolkit.notebook.select()) == index
        assert toolkit.profiles.active['id'] == second
        toolkit.profiles.select(first)
    assert not toolkit.profiles.busy


def test_dialog_unsaved_edit_and_persistence(app, monkeypatch):
    root, toolkit = app
    first, _ = add_profiles(toolkit.profiles)
    dialog = ProfileManager(root, toolkit.profiles, '文件合并')
    dialog.fields['name'].set('新名称')
    monkeypatch.setattr(messagebox, 'askyesno', lambda *a, **kw: False)
    dialog.close()
    assert dialog.winfo_exists()
    dialog.save_profile()
    assert not dialog.dirty
    assert toolkit.profiles.active['id'] == first
    assert toolkit.profiles.active['name'] == '新名称'
    toolkit.config._load_config()
    assert toolkit.profiles.active['name'] == '新名称'
    dialog.close()


def test_workers_lock_until_join_without_scan_state(app, monkeypatch, tmp_path):
    from media_server.client import MediaServerClient
    from windows_gui.country_update_tab import CountryUpdateTab
    from windows_gui.genre_update_tab import GenreUpdateTab

    root, toolkit = app
    add_profiles(toolkit.profiles)
    started = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    frames = [tk.Frame(root), tk.Frame(root)]
    genre = GenreUpdateTab(frames[0], str(tmp_path))
    country = CountryUpdateTab(frames[1], str(tmp_path))

    def fake(index):
        def method(self, callback):
            def work():
                started[index].set()
                callback({'percent': 100})
                release[index].wait(10)

            worker = threading.Thread(target=work, daemon=True)
            worker.start()
            return worker

        return method

    monkeypatch.setattr(MediaServerClient, 'update_genres', fake(0))
    monkeypatch.setattr(MediaServerClient, 'update_countries', fake(1))
    genre.update_genres()
    try:
        pump(root, started[0].is_set)
        assert str(country.start_button.cget('state')) == 'disabled'
        genre.stop_background_task()
        assert toolkit.profiles.busy
        assert str(toolkit.profile_button.cget('state')) == 'disabled'
        release[0].set()
        pump(root, lambda: genre._task_thread is None)
        assert not toolkit.profiles.busy
        country.update_countries()
        pump(root, started[1].is_set)
        assert toolkit.profiles.busy
        release[1].set()
        pump(root, lambda: country._task_thread is None)
        assert not toolkit.profiles.busy
        assert toolkit.profiles.settings('genre_update') == {}
        assert toolkit.profiles.settings('country_update') == {}
    finally:
        for event in release:
            event.set()
        pump(root, lambda: genre._task_thread is None and country._task_thread is None)
        for frame in frames:
            frame.destroy()
