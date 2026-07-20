"""
macOS PyQt5 frontend smoke and workflow tests.
"""

import os
import threading
import time

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    from utils.config import Config

    def initialize(self):
        self.config_dir = str(tmp_path)
        self.config_file = str(tmp_path / "config.yaml")
        if not os.path.exists(self.config_file):
            self._create_default_config()
        self._load_config()

    Config._instance = None
    Config._config = None
    monkeypatch.setattr(Config, "_initialize", initialize)
    yield tmp_path
    Config._instance = None
    Config._config = None


def wait_until(qapp, predicate, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def wait_for_tab_idle(qapp, tab, timeout=3):
    return wait_until(qapp, lambda: not tab.is_task_running(), timeout=timeout)


def test_main_window_initializes_all_tabs(qapp, isolated_config):
    from macos_gui.main_window import MainWindow

    window = MainWindow()

    assert window.tabs.count() == 7
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        "导出软链接",
        "文件夹操作",
        "文件合并",
        "合并版本",
        "更新流派",
        "更新地区",
        "115目录树镜像",
    ]
    for tab in [
        window.symlink_export_tab,
        window.folder_tools_tab,
        window.file_merge_tab,
        window.version_merge_tab,
        window.genre_update_tab,
        window.country_update_tab,
        window.tree_mirror_tab,
    ]:
        assert tab.progress_bar is not None
        assert tab.btn_stop is not None
        assert tab.log_text is not None

    window.close()


def test_country_update_tab_uses_genre_server_settings_as_initial_default(qapp, isolated_config, tmp_path):
    from macos_gui.country_update_tab import CountryUpdateTab
    from utils.config import Config

    config = Config()
    config.set('genre_update', 'server_url', 'http://jellyfin.local')
    config.set('genre_update', 'api_key', 'genre-api')
    config.set('genre_update', 'username', 'wiz')
    config.set('genre_update', 'server_type', 'jellyfin')
    config.save()

    tab = CountryUpdateTab(str(tmp_path / "logs"))

    assert tab.edit_url.text() == 'http://jellyfin.local'
    assert tab.edit_api.text() == 'genre-api'
    assert tab.edit_user.text() == 'wiz'
    assert tab.radio_jellyfin.isChecked()


def test_symlink_export_tab_creates_symlink_and_copies_metadata(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "movie.mp4").write_text("video", encoding="utf-8")
    (source / "movie.nfo").write_text("<movie />", encoding="utf-8")

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.clear()
    tab.link_list.setPlainText(str(source))
    tab.target_edit.setText(str(target))
    tab.chk_tvshow.setChecked(False)
    tab.create_symlink()
    assert wait_until(qapp, lambda: os.path.islink(target / "movie.mp4"))
    assert wait_until(qapp, tab.btn_create_link.isEnabled)

    tab.download_metadata()
    copied_metadata = target / "movie.nfo"
    assert wait_until(qapp, copied_metadata.exists)


def test_symlink_export_tab_load_preserves_saved_config(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab
    from utils.config import Config

    saved_config = Config()
    saved_config.set('symlink_export', 'link_folders', ['/saved/source'])
    saved_config.set('symlink_export', 'target_folder', '/saved/target')
    saved_config.set('symlink_export', 'thread_count', 9)
    saved_config.set('symlink_export', 'enable_replace_path', True)
    saved_config.set('symlink_export', 'only_tvshow_nfo', False)
    saved_config.set('symlink_export', 'overwrite_metadata', True)
    saved_config.set('symlink_export', 'original_path', '/old/root')
    saved_config.set('symlink_export', 'replace_path', '/new/root')
    saved_config.set('symlink_export', 'link_suffixes', ['.mp4', '.mkv'])
    saved_config.set('symlink_export', 'meta_suffixes', ['.nfo', '.jpg'])
    saved_config.save()

    tab = SymlinkExportTab(str(tmp_path / "logs"))

    assert tab.link_list.toPlainText() == '/saved/source'
    assert tab.target_edit.text() == '/saved/target'
    assert tab.spin_threads.value() == 9
    assert tab.chk_replace.isChecked()
    assert not tab.chk_tvshow.isChecked()
    assert tab.chk_overwrite_meta.isChecked()
    assert tab.original_edit.text() == '/old/root'
    assert tab.replace_edit.text() == '/new/root'
    assert tab.edit_link_suffix.text() == '.mp4;.mkv'
    assert tab.edit_meta_suffix.text() == '.nfo;.jpg'

    with open(saved_config.config_file, 'r', encoding='utf-8') as f:
        reloaded = yaml.safe_load(f)
    assert reloaded['symlink_export']['target_folder'] == '/saved/target'
    assert reloaded['symlink_export']['enable_replace_path'] is True
    assert reloaded['symlink_export']['overwrite_metadata'] is True


def test_symlink_export_tab_path_edits_persist_to_config(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab
    from utils.config import Config

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.target_edit.setText('/manual/target')
    qapp.processEvents()

    saved_config = Config()
    with open(saved_config.config_file, 'r', encoding='utf-8') as f:
        reloaded = yaml.safe_load(f)
    assert reloaded['symlink_export']['target_folder'] == '/manual/target'


def test_symlink_export_tab_accepts_multiline_folder_paths(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab
    from utils.config import Config

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.setPlainText(
        "  /media/movies/谜印女子 (2026)  \n"
        "\n"
        "/media/movies/蕾切尔·尼克尔谋杀案 (2026)\n"
        "/media/movies/追杀51号 (2025)"
    )
    tab.target_edit.setText('/manual/target')
    qapp.processEvents()

    expected_folders = [
        '/media/movies/谜印女子 (2026)',
        '/media/movies/蕾切尔·尼克尔谋杀案 (2026)',
        '/media/movies/追杀51号 (2025)',
    ]
    assert tab.link_list.folders() == expected_folders
    assert tab._collect_export_config('link')['link_folders'] == expected_folders

    saved_config = Config()
    with open(saved_config.config_file, 'r', encoding='utf-8') as f:
        reloaded = yaml.safe_load(f)
    assert reloaded['symlink_export']['link_folders'] == expected_folders


def test_symlink_export_tab_rerun_loads_previous_runtime_config(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab
    from utils.config import Config

    first_tab = SymlinkExportTab(str(tmp_path / "logs"))
    first_tab.link_list.clear()
    first_tab.link_list.setPlainText('/runtime/source')
    first_tab.target_edit.setText('/runtime/target')
    first_tab.spin_threads.setValue(7)
    first_tab.chk_tvshow.setChecked(False)
    first_tab.edit_link_suffix.setText('.mp4;.mkv')
    first_tab.save_config()

    Config._instance = None
    Config._config = None

    second_tab = SymlinkExportTab(str(tmp_path / "logs"))

    assert second_tab.link_list.toPlainText() == '/runtime/source'
    assert second_tab.target_edit.text() == '/runtime/target'
    assert second_tab.spin_threads.value() == 7
    assert not second_tab.chk_tvshow.isChecked()
    assert second_tab.edit_link_suffix.text() == '.mp4;.mkv'


def test_export_create_symlink_shows_progress_logs(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "movie1.mp4").write_text("video1", encoding="utf-8")
    (source / "movie2.mp4").write_text("video2", encoding="utf-8")
    (source / "poster.jpg").write_text("image", encoding="utf-8")

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.clear()
    tab.link_list.setPlainText(str(source))
    tab.target_edit.setText(str(target))

    tab.create_symlink()

    assert wait_until(qapp, tab.btn_create_link.isEnabled)
    log_text = tab.log_text.toPlainText()
    assert "创建软链接已在后台启动" in log_text
    assert "准备创建软链接" in log_text
    assert "扫描源文件夹" in log_text
    assert "扫描 3 个文件，匹配 2 个软链接候选" in log_text
    assert "待创建软链接候选: 2 个" in log_text
    assert "创建进度: 2/2" in log_text


def test_export_sync_all_runs_in_background(qapp, isolated_config, tmp_path, monkeypatch):
    from macos_gui.symlink_export_tab import SymlinkExportTab

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "movie.mp4").write_text("video", encoding="utf-8")

    started = threading.Event()
    release = threading.Event()

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.clear()
    tab.link_list.setPlainText(str(source))
    tab.target_edit.setText(str(target))

    def slow_metadata(config):
        started.set()
        release.wait(timeout=2)

    monkeypatch.setattr(tab, "_run_metadata_copy", slow_metadata)

    start_time = time.time()
    tab.sync_all()

    assert time.time() - start_time < 0.2
    assert wait_until(qapp, started.is_set)
    assert wait_until(qapp, lambda: os.path.islink(target / "movie.mp4"))
    assert not tab.btn_sync_all.isEnabled()

    release.set()
    assert wait_until(qapp, tab.btn_sync_all.isEnabled)


def test_export_sync_all_creates_symlink_and_metadata(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab

    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "movie.mp4").write_text("video", encoding="utf-8")
    (source / "movie.nfo").write_text("<movie />", encoding="utf-8")

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.clear()
    tab.link_list.setPlainText(str(source))
    tab.target_edit.setText(str(target))
    tab.chk_tvshow.setChecked(False)

    tab.sync_all()

    assert wait_until(qapp, lambda: os.path.islink(target / "movie.mp4"))
    assert wait_until(qapp, lambda: (target / "movie.nfo").exists())
    assert wait_until(qapp, tab.btn_sync_all.isEnabled)


def test_export_sync_all_preserves_multiline_source_folder_names(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab

    movies = tmp_path / "movies"
    first_source = movies / "谜印女子 (2026)"
    second_source = movies / "蕾切尔·尼克尔谋杀案 (2026)"
    target = tmp_path / "target"
    first_source.mkdir(parents=True)
    second_source.mkdir(parents=True)
    target.mkdir()
    (first_source / "movie.mp4").write_text("video1", encoding="utf-8")
    (first_source / "movie.nfo").write_text("nfo1", encoding="utf-8")
    (second_source / "movie.mp4").write_text("video2", encoding="utf-8")
    (second_source / "movie.nfo").write_text("nfo2", encoding="utf-8")

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.setPlainText(f"{first_source}\n{second_source}")
    tab.target_edit.setText(str(target))
    tab.chk_tvshow.setChecked(False)

    tab.sync_all()

    for source in (first_source, second_source):
        output_folder = target / source.name
        assert wait_until(qapp, lambda path=output_folder / "movie.mp4": os.path.islink(path))
        assert wait_until(qapp, lambda path=output_folder / "movie.nfo": path.exists())
    assert not os.path.lexists(target / "movie.mp4")
    assert not (target / "movie.nfo").exists()
    assert wait_until(qapp, tab.btn_sync_all.isEnabled)


def test_export_metadata_overwrite_checkbox_controls_existing_files(qapp, isolated_config, tmp_path):
    from macos_gui.symlink_export_tab import SymlinkExportTab

    source = tmp_path / "source"
    target = tmp_path / "target"
    existing_target = target / "movie.nfo"
    source.mkdir()
    existing_target.parent.mkdir(parents=True)
    (source / "movie.nfo").write_text("new content", encoding="utf-8")
    existing_target.write_text("existing content", encoding="utf-8")

    tab = SymlinkExportTab(str(tmp_path / "logs"))
    tab.link_list.clear()
    tab.link_list.setPlainText(str(source))
    tab.target_edit.setText(str(target))
    tab.chk_tvshow.setChecked(False)

    assert not tab.chk_overwrite_meta.isChecked()

    tab.download_metadata()
    assert wait_until(qapp, tab.btn_download_meta.isEnabled)
    assert existing_target.read_text(encoding="utf-8") == "existing content"

    (source / "movie.nfo").write_text("overwritten content", encoding="utf-8")
    tab.chk_overwrite_meta.setChecked(True)
    tab.download_metadata()
    assert wait_until(qapp, tab.btn_download_meta.isEnabled)
    assert existing_target.read_text(encoding="utf-8") == "overwritten content"


def test_folder_tools_tab_operations_do_not_raise(qapp, isolated_config, tmp_path):
    from macos_gui.folder_tools_tab import FolderToolsTab

    folder = tmp_path / "folder"
    folder.mkdir()
    real_file = folder / "real.mp4"
    real_file.write_text("video", encoding="utf-8")
    link_file = folder / "linked.mp4"
    os.symlink(real_file, link_file)

    tab = FolderToolsTab(str(tmp_path / "logs"))
    tab.target_edit.setText(str(folder))

    tab.combo_op.setCurrentText("删除软链接")
    tab.execute()
    assert wait_for_tab_idle(qapp, tab)
    assert not os.path.lexists(link_file)

    tab.combo_op.setCurrentText("删除所有视频文件")
    tab.execute()
    assert wait_for_tab_idle(qapp, tab)
    assert wait_until(qapp, lambda: not real_file.exists())

    tab.combo_op.setCurrentText("检查刮削数据完整性")
    tab.execute()
    assert wait_for_tab_idle(qapp, tab)


def test_merge_and_tree_mirror_tabs_run_backends(qapp, isolated_config, tmp_path):
    from macos_gui.file_merge_tab import FileMergeTab
    from macos_gui.tree_mirror_tab import TreeMirrorTab

    metadata = tmp_path / "metadata"
    video = tmp_path / "video"
    metadata.mkdir()
    video.mkdir()
    (metadata / "movie.nfo").write_text("<movie />", encoding="utf-8")
    (video / "movie.mp4").write_text("video", encoding="utf-8")

    file_merge_tab = FileMergeTab(str(tmp_path / "logs"))
    file_merge_tab.metadata_edit.setText(str(metadata))
    file_merge_tab.video_edit.setText(str(video))
    file_merge_tab.merge_files()
    assert wait_for_tab_idle(qapp, file_merge_tab)
    assert (video / "movie.nfo").exists()

    tree_file = tmp_path / "tree.txt"
    export = tmp_path / "mirror"
    export.mkdir()
    tree_file.write_text("Root\n|——电影\n| |- Movie.2024.mp4\n", encoding="utf-8")

    tree_mirror_tab = TreeMirrorTab(str(tmp_path / "logs"))
    tree_mirror_tab.tree_edit.setText(str(tree_file))
    tree_mirror_tab.export_edit.setText(str(export))
    tree_mirror_tab.start_mirror()
    assert wait_for_tab_idle(qapp, tree_mirror_tab)
    assert (export / "电影" / "Movie.2024.mp4").exists()


def test_emby_tabs_call_operator_methods(qapp, isolated_config, tmp_path, monkeypatch):
    from macos_gui.country_update_tab import CountryUpdateTab
    from macos_gui.genre_update_tab import GenreUpdateTab
    from macos_gui.version_merge_tab import VersionMergeTab
    from media_server.client import MediaServerClient

    calls = []

    def fake_merge_versions(self, callback):
        calls.append(("merge_versions", self.server_url, self.api_key, self.username, self.server_type))
        callback("merge done")

    def fake_update_genres(self, callback=None, **_kwargs):
        calls.append(("update_genres", self.server_url, self.api_key, self.username, self.server_type))
        if callback:
            callback("genres done")

    def fake_update_countries(self, callback=None, **_kwargs):
        calls.append(("update_countries", self.server_url, self.api_key, self.username, self.server_type))
        if callback:
            callback("countries done")

    monkeypatch.setattr(MediaServerClient, "merge_versions", fake_merge_versions)
    monkeypatch.setattr(MediaServerClient, "update_genres", fake_update_genres)
    monkeypatch.setattr(MediaServerClient, "update_countries", fake_update_countries)

    version_merge_tab = VersionMergeTab(str(tmp_path / "logs"))
    version_merge_tab.edit_url.setText("http://jellyfin.local")
    version_merge_tab.edit_api.setText("api")
    version_merge_tab.edit_user.setText("wiz")
    version_merge_tab.radio_jellyfin.setChecked(True)
    version_merge_tab.merge_versions()
    assert wait_until(qapp, lambda: len(calls) >= 1)
    assert wait_for_tab_idle(qapp, version_merge_tab)

    genre_update_tab = GenreUpdateTab(str(tmp_path / "logs"))
    genre_update_tab.edit_url.setText("http://emby.local")
    genre_update_tab.edit_api.setText("api")
    genre_update_tab.edit_user.setText("user")
    genre_update_tab.radio_emby.setChecked(True)
    genre_update_tab.update_genres()
    assert wait_until(qapp, lambda: len(calls) >= 2)
    assert wait_for_tab_idle(qapp, genre_update_tab)

    country_update_tab = CountryUpdateTab(str(tmp_path / "logs"))
    country_update_tab.edit_url.setText("http://jellyfin.local")
    country_update_tab.edit_api.setText("country-api")
    country_update_tab.edit_user.setText("wiz")
    country_update_tab.radio_jellyfin.setChecked(True)
    country_update_tab.update_countries()
    assert wait_until(qapp, lambda: len(calls) >= 3)
    assert wait_for_tab_idle(qapp, country_update_tab)

    assert calls == [
        ("merge_versions", "http://jellyfin.local", "api", "wiz", "jellyfin"),
        ("update_genres", "http://emby.local", "api", "user", "emby"),
        ("update_countries", "http://jellyfin.local", "country-api", "wiz", "jellyfin"),
    ]


def test_qt_slot_exception_guard_logs_instead_of_raising(qapp, isolated_config, tmp_path, monkeypatch):
    import macos_gui.file_merge_tab as merge_module
    from macos_gui.file_merge_tab import FileMergeTab

    class FailingMerger:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    metadata = tmp_path / "metadata"
    video = tmp_path / "video"
    metadata.mkdir()
    video.mkdir()

    monkeypatch.setattr(merge_module, "FileMerger", FailingMerger)

    tab = FileMergeTab(str(tmp_path / "logs"))
    tab.metadata_edit.setText(str(metadata))
    tab.video_edit.setText(str(video))

    tab.merge_files()
    assert wait_until(qapp, lambda: "boom" in tab.log_text.toPlainText())
    assert "boom" in tab.log_text.toPlainText()


def test_qtextedit_log_handler_swallows_widget_slot_errors(qapp):
    from macos_gui.qt_utils import QTextEditLogHandler

    class FailingWidget:
        def append(self, message):
            raise KeyboardInterrupt()

    handler = QTextEditLogHandler(FailingWidget())

    handler._append_message("hello")


def test_main_window_confirms_close_while_export_task_running(qapp, isolated_config, monkeypatch):
    from macos_gui.main_window import MainWindow

    class FakeCloseEvent:
        def __init__(self):
            self.accepted = False
            self.ignored = False

        def accept(self):
            self.accepted = True

        def ignore(self):
            self.ignored = True

    window = MainWindow()
    monkeypatch.setattr(window.symlink_export_tab, "is_task_running", lambda: True)

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.No)
    cancel_event = FakeCloseEvent()
    window.closeEvent(cancel_event)
    assert cancel_event.ignored
    assert not cancel_event.accepted

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    accept_event = FakeCloseEvent()
    window.closeEvent(accept_event)
    assert accept_event.accepted
    assert not accept_event.ignored

    window.close()
