# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import site
from pathlib import Path

block_cipher = None

# 查找 tkdnd 库文件位置
def find_tkdnd():
    # 尝试从 site-packages 查找
    for site_pkg in site.getsitepackages():
        tkdnd_path = os.path.join(site_pkg, 'tkinterdnd2', 'tkdnd')
        if os.path.exists(tkdnd_path):
            return tkdnd_path
    # 尝试从当前 Python 环境查找
    base_path = os.path.dirname(sys.executable)
    tkdnd_path = os.path.join(base_path, 'Lib', 'site-packages', 'tkinterdnd2', 'tkdnd')
    if os.path.exists(tkdnd_path):
        return tkdnd_path
    return None

tkdnd_path = find_tkdnd()
if not tkdnd_path:
    raise FileNotFoundError("Could not find tkdnd directory!")

print(f"Found tkdnd at: {tkdnd_path}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (tkdnd_path, os.path.join('tkinterdnd2', 'tkdnd')),
    ],
    hiddenimports=[
        'tkinterdnd2',
        'ttkthemes',
        'pathlib',
        'watchdog',
        'tqdm'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Emby115Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, 
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 如果你有图标文件的话
)
