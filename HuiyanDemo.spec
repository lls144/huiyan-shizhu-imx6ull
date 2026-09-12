# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH)
DATA_FILES = [
    (str(ROOT / "pc/config/camera.json"), "pc/config"),
    (str(ROOT / "pc/config/controller_windows_ethernet.json"), "pc/config"),
    (str(ROOT / "pc/config/events.json"), "pc/config"),
    (str(ROOT / "pc/config/vision.json"), "pc/config"),
    (str(ROOT / "pc/gui/assets/huiyan_logo.svg"), "pc/gui/assets"),
    (str(ROOT / "pc/gui/assets/huiyan_logo.ico"), "pc/gui/assets"),
]

a = Analysis(
    [str(ROOT / "pc/gui/demo_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=["cv2_enumerate_cameras"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
# The host toolchain's Poppler ICU DLLs are discovered through PATH by the
# OpenCV hook.  They are unrelated to this demo and shadow Windows' system
# ICU at frozen runtime, preventing the matching PySide6 QtCore DLL from
# loading.  Do not ship those accidental host-toolchain binaries.
a.binaries = [
    entry
    for entry in a.binaries
    if entry[0].lower() not in {"icuuc.dll", "icudt78.dll"}
]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="HuiyanDemo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "pc/gui/assets/huiyan_logo.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HuiyanDemo",
)
