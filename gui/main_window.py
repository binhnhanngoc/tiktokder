"""Main application window with tab layout, wiring all components together."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from config import (
    AppConfig,
    HistoryRecord,
    load_history_records,
    save_history_records,
)
from download_engine import DownloadEngine
from gui.channel_browser import ChannelBrowser
from gui.download_tab import DownloadTab
from gui.history_tab import HistoryTab
from gui.icons import icon
from gui.settings_panel import SettingsPanel


def _resolve_icon() -> QIcon:
    """Locate icon.ico in source tree or PyInstaller bundle; empty QIcon if missing."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    path = Path(base) / "assets" / "icon.ico"
    return QIcon(str(path)) if path.exists() else QIcon()


class MainWindow(QMainWindow):
    """TikTokDer main window with Download, Channel, History, and Settings tabs."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("TikTokDer")
        self.setWindowIcon(_resolve_icon())
        self._restore_geometry()
        self._setup_menu()

        # Download engine (shared between tabs)
        self.engine = DownloadEngine(
            output_dir=config.output_dir,
            max_workers=config.workers,
            delay=config.delay,
            cookie_browser=config.cookie_browser,
            quality=config.quality_default,
            write_subs=config.write_subtitles,
            write_thumb=config.write_thumbnail,
            history_max_entries=config.history_max_entries,
            parent=self,
        )

        # Tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Download tab ---
        self.download_tab = DownloadTab()
        # Back-compat handles for legacy code paths and tests.
        self.url_input = self.download_tab.url_input
        self.download_table = self.download_tab.download_table
        self.tabs.addTab(self.download_tab, "Download")

        # --- Channel tab ---
        self.channel_browser = ChannelBrowser(cookie_browser=config.cookie_browser)
        self.tabs.addTab(self.channel_browser, "Channel / Page")

        # --- History tab ---
        self.history_tab = HistoryTab()
        self.tabs.addTab(self.history_tab, "History")

        # --- Settings tab ---
        self.settings_panel = SettingsPanel(config)
        self.tabs.addTab(self.settings_panel, "Settings")

        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

        # Wire signals
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect all component signals to slots."""
        # URL input -> engine
        self.url_input.video_url_submitted.connect(self._on_video_url)
        self.url_input.channel_url_submitted.connect(self._on_channel_url)

        # Drag-drop + import/export
        self.download_tab.urls_dropped.connect(self._on_urls_dropped)
        self.download_tab.import_requested.connect(self._on_urls_dropped)
        self.download_tab.export_requested.connect(self._on_export_requested)

        # Channel browser -> engine
        self.channel_browser.download_requested.connect(self._on_channel_download)

        # Engine -> download table
        self.engine.download_started.connect(self.download_table.on_download_started)
        self.engine.download_progress.connect(self.download_table.on_download_progress)
        self.engine.download_finished.connect(self._on_download_finished)
        self.engine.all_finished.connect(self._on_all_finished)
        self.engine.history_changed.connect(self.history_tab.refresh)

        # Cancel all button
        self.download_table.cancel_all_btn.clicked.connect(self.engine.cancel_all)

        # Retry & Clear All wiring
        self.download_table.retry_requested.connect(self._on_retry_requested)
        self.download_table.force_download_requested.connect(self._on_force_download_requested)
        self.download_table.clear_all_requested.connect(self._on_clear_all_requested)

        # History tab actions
        self.history_tab.redownload_requested.connect(self._on_history_redownload)
        self.history_tab.remove_history_requested.connect(self._on_history_remove)

        # Settings -> engine (live propagation)
        self.settings_panel.settings_changed.connect(self._apply_settings)

    @Slot(str)
    def _on_video_url(self, url: str) -> None:
        """Handle single video URL submission."""
        self.download_table.add_download(url)
        self.engine.add_urls([url])
        self._update_status_count()

    @Slot(str)
    def _on_channel_url(self, url: str) -> None:
        """Switch to Channel tab and start browsing."""
        # Set on whichever sub-panel matches the URL platform; channel_browser
        # detects platform and switches sub-tabs.
        self.channel_browser.url_input.setText(url)
        self.tabs.setCurrentWidget(self.channel_browser)
        self.channel_browser._on_browse()

    @Slot(list)
    def _on_channel_download(self, urls: list[str]) -> None:
        """Add channel-selected videos to download queue."""
        for url in urls:
            self.download_table.add_download(url)
        self.engine.add_urls(urls)
        self.tabs.setCurrentWidget(self.download_tab)
        self._update_status_count()

    @Slot(list)
    def _on_urls_dropped(self, urls: list[str]) -> None:
        """Drag-dropped or imported URLs — queue them."""
        for url in urls:
            self.download_table.add_download(url)
        self.engine.add_urls(urls)
        self.tabs.setCurrentWidget(self.download_tab)
        self._update_status_count()

    @Slot(str)
    def _on_export_requested(self, path: str) -> None:
        """Write current queue + history URLs to ``path`` (.txt)."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                queue_urls = [
                    d.get("url") for d in self.download_table._row_data.values() if d.get("url")
                ]
                if queue_urls:
                    f.write("# === Queue ===\n")
                    for u in queue_urls:
                        f.write(f"{u}\n")
                records = load_history_records()
                if records:
                    f.write("\n# === History ===\n")
                    for r in records:
                        if r.url:
                            f.write(f"# platform: {r.platform or '-'} uploader: {r.uploader or '-'}\n")
                            f.write(f"{r.url}\n")
            self.update_status(f"Exported to {path}")
        except OSError as exc:
            self.update_status(f"Export failed: {exc}")

    @Slot(str, object)
    def _on_download_finished(self, url: str, result) -> None:
        """Forward to table and update status."""
        self.download_table.on_download_finished(url, result)
        self._update_status_count()

    @Slot()
    def _on_all_finished(self) -> None:
        self.update_status("All downloads complete")

    @Slot(list)
    def _on_retry_requested(self, urls: list[str]) -> None:
        """Re-queue URLs whose previous attempt failed/cancelled."""
        if urls:
            self.engine.retry_urls(urls)
            self._update_status_count()

    @Slot(list)
    def _on_force_download_requested(self, urls: list[str]) -> None:
        """Re-queue URLs with force=True: bypass history, overwrite files."""
        if urls:
            self.engine.retry_urls(urls, force=True)
            self._update_status_count()

    @Slot(list)
    def _on_clear_all_requested(self, urls: list[str]) -> None:
        """User cleared the table — cancel active workers and reset dedup."""
        self.engine.cancel_all()
        self.engine.clear_dedup(urls)
        self._update_status_count()

    @Slot(str)
    def _on_history_redownload(self, url: str) -> None:
        """Re-download a history row: switch to Download tab and force re-queue."""
        self.download_table.add_download(url)
        self.engine.retry_url(url, force=True)
        self.tabs.setCurrentWidget(self.download_tab)
        self._update_status_count()

    @Slot(str)
    def _on_history_remove(self, video_id: str) -> None:
        """Drop a record from history persistently and refresh the tab."""
        records = [r for r in load_history_records() if r.video_id != video_id]
        save_history_records(records)
        # Also drop from in-memory dedup so the engine re-allows re-queue without force.
        self.engine._history.discard(video_id)
        self.history_tab.refresh()

    def _update_status_count(self) -> None:
        done = self.download_table.get_completed_count()
        total = self.download_table.get_total_count()
        self.update_status(f"Downloaded {done}/{total}")

    @Slot()
    def _apply_settings(self) -> None:
        """Propagate settings changes to engine and channel browser."""
        self.engine.output_dir = self.config.output_dir
        self.engine.max_workers = self.config.workers
        self.engine.delay = self.config.delay
        self.engine.cookie_browser = self.config.cookie_browser
        self.engine.quality = self.config.quality_default
        self.engine.write_subs = self.config.write_subtitles
        self.engine.write_thumb = self.config.write_thumbnail
        self.engine.history_max_entries = self.config.history_max_entries
        self.channel_browser.set_cookie_browser(self.config.cookie_browser)

    def _setup_menu(self) -> None:
        """Create menu bar with File and Help menus."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(icon("mdi6.exit-to-app"), "E&xit", self.close)
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(icon("mdi6.information-outline"), "&About", self._show_about)

    @Slot()
    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About TikTokDer",
            "TikTokDer - Video Downloader\n\n"
            "Download TikTok and Facebook videos without watermarks.\n"
            "Powered by yt-dlp.",
        )

    def update_status(self, text: str) -> None:
        """Update status bar message."""
        self.status_label.setText(text)

    def _restore_geometry(self) -> None:
        """Restore window size and position from config."""
        self.resize(self.config.window_width, self.config.window_height)
        if self.config.window_x is not None and self.config.window_y is not None:
            self.move(self.config.window_x, self.config.window_y)
