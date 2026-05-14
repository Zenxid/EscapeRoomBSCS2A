# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('questhash.dll', '.')],
    datas=[('events.lua', '.'), ('game.ini', '.'), ('quests.json', '.'), ('arena.db', '.'), ('assets', 'assets')],
    hiddenimports=['db', 'game_engine', 'lua_bridge', 'game_data', 'main_menu', 'c_bridge', 'audio', 'icon_gen', 'questhash_bridge', 'updater'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VaultZero',
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
    icon=['assets\\icon.ico'],
)
