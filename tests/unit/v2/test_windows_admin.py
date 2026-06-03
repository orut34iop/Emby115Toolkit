from pathlib import Path

from emby115_v2 import windows_admin


def test_can_create_symlink_uses_temp_path_and_symlink(tmp_path, monkeypatch):
    class FakeTemporaryDirectory:
        def __init__(self, prefix: str):
            self.prefix = prefix

        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_symlink(source: str, target: str):
        Path(target).write_text(Path(source).read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(windows_admin.tempfile, "TemporaryDirectory", FakeTemporaryDirectory)
    monkeypatch.setattr(windows_admin.os, "symlink", fake_symlink)
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "target.link")

    assert windows_admin.can_create_symlink() is True
