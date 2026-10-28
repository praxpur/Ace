# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas = [('gui_dist', 'gui_dist'), ('resource', 'resource'), ('TREEHOUSE-LICENSE', '.')]
binaries = []
hiddenimports = ['chardet']
for package in ('webview', 'pythonnet', 'cv2', 'playwright'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
browser_root = Path(os.environ.get('PLAYWRIGHT_BROWSERS_PATH', ''))
browsers = sorted(browser_root.glob('chromium-*/chrome-win64/chrome.exe'))
if not browsers:
    raise RuntimeError('Set PLAYWRIGHT_BROWSERS_PATH to an installed Playwright Chromium cache')
browser = browsers[-1].parents[1]
datas.append((str(browser), f'browsers/{browser.name}'))

a = Analysis(
    ['gui_main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['scripts/windows_runtime_hook.py'],
    excludes=['unittest', 'pydoc', 'doctest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CourseHub',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None,
          icon=['packaging/assets/app.ico'])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               upx_exclude=[], name='CourseHub')
