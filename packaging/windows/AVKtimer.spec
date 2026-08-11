# -*- mode: python ; coding: utf-8 -*-
# Build a Windows onefile executable.
# Invoke from the repository root: pyinstaller packaging/windows/AVKtimer.spec
# (dist/ and build/ land at the repo root, since those follow the invocation cwd).
# The Analysis() paths below are relative to THIS FILE's own folder instead
# (packaging/windows/), which is how PyInstaller resolves paths inside a .spec --
# not relative to the invocation cwd. Using bare 'avktimer.py' here (matching the
# comment above) is what broke the Windows CI build twice: PyInstaller looked for
# packaging/windows/avktimer.py, which doesn't exist [confirmed via the CI failure log].

a = Analysis(
    ['../../avktimer.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../../templates', 'templates'),
        ('../../static', 'static'),
        ('../../assets/app.ico', '.'),
        ('../../assets/alarme.mp3', '.'),
        ('../../assets/alarme1.mp3', '.'),
        ('../../assets/alarme2.mp3', '.'),
    ],
    hiddenimports=[],
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
    name='AVKtimer',
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
    icon=['../../assets/app.ico'],
)
