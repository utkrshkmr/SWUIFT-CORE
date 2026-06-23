import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

_imageio_ffmpeg_datas = collect_data_files("imageio_ffmpeg", includes=["*.exe", "ffmpeg*"])

ICON_MACOS = "SWUIFT.icns"
ICON_WIN = "SWUIFT.ico"
ICON = ICON_MACOS if sys.platform == "darwin" else ICON_WIN

a = Analysis(
    ["swuift_app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("SWUIFT.icns", "."),
        ("SWUIFT.ico", "."),
        ("swuift", "swuift"),
        ("gui", "gui"),
        ("../../packages/core/src/swuift_core", "swuift_core"),
        *_imageio_ffmpeg_datas,
    ],
    hiddenimports=[
        "numpy",
        "numpy.core._multiarray_umath",
        "numpy.core._methods",
        "scipy",
        "scipy.io",
        "scipy.io.matlab",
        "h5py",
        "h5py._hl",
        "h5py._hl.files",
        "matplotlib",
        "matplotlib.backends.backend_agg",
        "imageio",
        "imageio_ffmpeg",
        "tqdm",
        "tqdm.auto",
        "av",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PIL",
        "PIL.Image",
        "swuift_core",
        "swuift_core.kernels",
        "swuift_core.spread",
        "swuift_core.hardening",
        "swuift_core.config",
        "numba",
        "numba.core",
        "numba.np",
        "llvmlite",
        "llvmlite.binding",
    ],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SWUIFT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SWUIFT",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SWUIFT.app",
        icon=ICON_MACOS,
        bundle_identifier="com.swuift.app",
        info_plist={
            "CFBundleName": "SWUIFT",
            "CFBundleDisplayName": "SWUIFT",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "11.0",
        },
    )
