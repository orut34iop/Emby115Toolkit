from __future__ import annotations

import ctypes
import os
import tempfile
from pathlib import Path


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


def symlink_failure_message() -> str:
    if is_windows():
        return "当前 Windows 用户无法创建符号链接。请到系统设置中打开开发者模式后重试。"
    return "当前用户无法创建符号链接。请检查当前用户对目标目录的写入权限。"
