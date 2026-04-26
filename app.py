"""GUI entry point for TikTokDer desktop application."""

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config import load_config, save_config


def _icon_path() -> str:
    """Return absolute path to the bundled app icon.

    PyInstaller onedir builds expose bundled assets under sys._MEIPASS,
    while a normal source run resolves relative to this file.
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return str(Path(base) / "assets" / "icon.ico")


def main() -> None:
    """Launch TikTokDer desktop app."""
    app = QApplication(sys.argv)
    app.setApplicationName("TikTokDer")

    icon_file = _icon_path()
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    config = load_config()

    # Import here to avoid circular imports during setup
    from gui.main_window import MainWindow

    window = MainWindow(config)
    window.show()

    exit_code = app.exec()

    # Save window geometry on exit
    geo = window.geometry()
    config.window_width = geo.width()
    config.window_height = geo.height()
    config.window_x = geo.x()
    config.window_y = geo.y()
    save_config(config)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
