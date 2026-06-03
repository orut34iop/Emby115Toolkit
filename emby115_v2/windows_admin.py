from __future__ import annotations

import ctypes
import os
import tempfile


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def can_create_symlink() -> bool:
    """Return whether the current process can create a file symlink."""
    try:
        with tempfile.TemporaryDirectory(prefix="emby115_symlink_check_") as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            target = root / "target.link"
            source.write_text("ok", encoding="utf-8")
            os.symlink(str(source), str(target))
            return target.is_symlink() and target.exists()
    except Exception:
        return False
