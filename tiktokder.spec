# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for TikTokDer — onedir build with GUI + CLI executables."""

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# curl_cffi native libraries (TLS impersonation for yt-dlp)
curl_cffi_datas = collect_data_files('curl_cffi')
curl_cffi_bins = collect_dynamic_libs('curl_cffi')

# yt-dlp extractors are dynamically imported — must collect all submodules
yt_dlp_imports = collect_submodules('yt_dlp')

# certifi CA bundle for HTTPS verification
certifi_datas = collect_data_files('certifi')

# ---------------------------------------------------------------------------
# GUI entry point (app.py) — no console window
# ---------------------------------------------------------------------------
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=curl_cffi_bins,
    datas=curl_cffi_datas + certifi_datas,
    hiddenimports=[
        *yt_dlp_imports,
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'curl_cffi',
        'curl_cffi.requests',
    ],
    hookspath=[],
    excludes=[
        'playwright',  # too large (~200MB Chromium), optional feature
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
    upx=True,
    console=False,  # GUI — no terminal window
    # icon='assets/icon.ico',  # uncomment after creating icon (Phase 5)
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
    upx=True,
    console=True,  # CLI needs terminal output
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
    upx=True,
    name='TikTokDer',
)
