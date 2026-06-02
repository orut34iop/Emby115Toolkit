from __future__ import annotations

import ctypes
import os
import subprocess
import sys
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


def requires_admin_for_symlink() -> bool:
    return is_windows()


def _powershell_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def restart_webui_as_admin(host: str, port: int, access_token: str = "", cwd: str | Path | None = None) -> None:
    if not is_windows():
        raise RuntimeError("当前平台不支持 Windows UAC 提权重启")
    if is_admin():
        return

    working_dir = Path(cwd or Path.cwd()).resolve()
    main_py = working_dir / "main.py"
    if not main_py.exists():
        raise RuntimeError(f"无法找到 WebUI 启动文件: {main_py}")

    args = [
        str(main_py),
        "--serve-web",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if access_token:
        args.extend(["--access-token", access_token])
    powershell_command = "Start-Sleep -Seconds 3; & " + " ".join(
        [_powershell_quote(sys.executable), *[_powershell_quote(arg) for arg in args]]
    )

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        "powershell.exe",
        subprocess.list2cmdline(["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", powershell_command]),
        str(working_dir),
        1,
    )
    if result <= 32:
        raise RuntimeError(f"用户取消或系统拒绝管理员提权，ShellExecuteW 返回值: {result}")
