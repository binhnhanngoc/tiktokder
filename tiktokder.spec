# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for TikTokDer — onedir build with GUI + CLI executables."""

import os
import sys
from pathlib import Path

# Ensure `from version import ...` resolves regardless of PyInstaller's invocation CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(SPEC)))  # noqa: F821 (SPEC injected by PyInstaller)

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

from version import __version_info__


def _build_version_info() -> VSVersionInfo:
    """Windows VERSIONINFO resource — same metadata for GUI + CLI EXE (DRY)."""
    major, minor, patch = __version_info__
    filevers = (major, minor, patch, 0)
    ver_str = f"{major}.{minor}.{patch}"
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=filevers,
            prodvers=filevers,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "TikTokDer"),
                StringStruct("FileDescription", "TikTok & Facebook Batch Video Downloader"),
                StringStruct("FileVersion", ver_str),
                StringStruct("ProductName", "TikTokDer"),
                StringStruct("ProductVersion", ver_str),
                StringStruct("OriginalFilename", "TikTokDer.exe"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 0x04B0])]),
        ],
    )

# curl_cffi native libraries (TLS impersonation for yt-dlp)
curl_cffi_datas = collect_data_files('curl_cffi')
curl_cffi_bins = collect_dynamic_libs('curl_cffi')

# yt-dlp extractors are dynamically imported — must collect all submodules
yt_dlp_imports = collect_submodules('yt_dlp')

# certifi CA bundle for HTTPS verification
certifi_datas = collect_data_files('certifi')

# qtawesome ships icon fonts (TTFs) + JSON charmaps as package data
qtawesome_datas = collect_data_files('qtawesome')
qtawesome_imports = collect_submodules('qtawesome')

# qdarktheme ships SVG resources + stylesheet templates as package data
qdarktheme_datas = collect_data_files('qdarktheme')
qdarktheme_imports = collect_submodules('qdarktheme')

# darkdetect picks platform backend dynamically
darkdetect_imports = collect_submodules('darkdetect')

# Playwright (GUI-only) — Python wrapper + driver/ Node runtime + Chromium browsers.
# The browser binaries live OUTSIDE site-packages in %LOCALAPPDATA%/ms-playwright/,
# so we explicitly mirror that cache into the bundle and point a runtime hook at it.
playwright_datas = collect_data_files('playwright')
playwright_bins = collect_dynamic_libs('playwright')
playwright_imports = collect_submodules('playwright')

_browsers_root = Path(os.environ.get('LOCALAPPDATA', '')) / 'ms-playwright'
playwright_browser_datas = []
if _browsers_root.is_dir():
    for src in _browsers_root.rglob('*'):
        if src.is_file():
            rel_dir = src.parent.relative_to(_browsers_root)
            playwright_browser_datas.append(
                (str(src), str(Path('ms-playwright') / rel_dir))
            )

# PySide6 multimedia — QMediaPlayer / QVideoWidget / QAudioOutput.
# Plugin DLLs (windowsmediaplugin / ffmpegmediaplugin) are discovered by
# Qt at runtime — must be explicitly collected for frozen builds, otherwise
# Library playback works in dev but silently fails in the shipped exe.
# PySide6 wheel layout differs across versions: newer wheels put plugins
# under ``PySide6/plugins/`` (no Qt/ prefix), older ones use
# ``PySide6/Qt/plugins/``. Try both; whichever returns files wins.
pyside6_multimedia_plugins = (
    collect_data_files('PySide6', subdir=os.path.join('plugins', 'multimedia'))
    or collect_data_files('PySide6', subdir=os.path.join('Qt', 'plugins', 'multimedia'))
)

# ---------------------------------------------------------------------------
# GUI entry point (app.py) — no console window
# ---------------------------------------------------------------------------
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=curl_cffi_bins + playwright_bins,
    datas=(
        curl_cffi_datas
        + certifi_datas
        + qtawesome_datas
        + qdarktheme_datas
        + playwright_datas
        + playwright_browser_datas
        + pyside6_multimedia_plugins
        + [('assets/icon.ico', 'assets'), ('assets/icon.png', 'assets')]
    ),
    hiddenimports=[
        *yt_dlp_imports,
        *qtawesome_imports,
        *qdarktheme_imports,
        *darkdetect_imports,
        *playwright_imports,
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'curl_cffi',
        'curl_cffi.requests',
    ],
    hookspath=[],
    runtime_hooks=['runtime_hooks/playwright_browsers.py'],
    excludes=[
        'pytest',
        'tkinter',
        'unittest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir mode
    name='TikTokDer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI — no terminal window
    icon='assets/icon.ico',
    version=_build_version_info(),
)

# ---------------------------------------------------------------------------
# CLI entry point (main.py) — console enabled
# ---------------------------------------------------------------------------
cli_a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=curl_cffi_bins,
    datas=curl_cffi_datas + certifi_datas,
    hiddenimports=[
        *yt_dlp_imports,
        'curl_cffi',
        'curl_cffi.requests',
        'rich',
        'rich.console',
        'rich.progress',
    ],
    excludes=[
        'playwright',
        'pytest',
        'PySide6',
        'tkinter',
        'unittest',
    ],
    noarchive=False,
)

cli_pyz = PYZ(cli_a.pure)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name='TikTokDer-CLI',
    debug=False,
    strip=False,
    upx=False,
    console=True,  # CLI needs terminal output
    version=_build_version_info(),
)

# ---------------------------------------------------------------------------
# Single folder bundles both executables + all dependencies
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    cli_exe,
    cli_a.binaries,
    cli_a.datas,
    strip=False,
    upx=False,
    name='TikTokDer',
)
