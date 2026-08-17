# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para JobHunter Desktop (onedir, sin consola).

Build: pyinstaller --noconfirm desktop/packaging/jobhunter.spec  (desde la raiz)
"""
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

datas = [
    (os.path.join(REPO, "desktop", "ui"), "ui"),
    (os.path.join(REPO, "jobhunter", "assets"), "jobhunter/assets"),
]
binaries = []
hiddenimports = collect_submodules("jobhunter") + collect_submodules("desktop")

for pkg in ("playwright", "webview", "clr_loader", "pythonnet"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(REPO, "desktop", "app.py")],
    pathex=[REPO],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JobHunter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(SPECPATH, "icon.ico"),
    version=os.path.join(SPECPATH, "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="JobHunter",
)
