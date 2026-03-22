"""GUI entry point for TikTokDer desktop application."""

import sys

from PySide6.QtWidgets import QApplication

from config import load_config, save_config


def main() -> None:
    """Launch TikTokDer desktop app."""
    app = QApplication(sys.argv)
    app.setApplicationName("TikTokDer")

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
