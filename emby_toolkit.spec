# filepath: /C:/Users/wiz/Desktop/dev/Emby115Toolkit/emby_toolkit.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['C:/Users/wiz/Desktop/dev/Emby115Toolkit'],
    binaries=[],
    datas=[('C:/Users/wiz/AppData/Local/Programs/Python/Python311/Lib/site-packages/tkinterdnd2/tkdnd', 'tkinterdnd2/tkdnd')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='emby_toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='emby_toolkit',
)