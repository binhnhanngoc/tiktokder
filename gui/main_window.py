"""Main application window — platform-first 3-tab IA.

Layout: TikTok | Facebook | Settings, each platform tab a composite of
Channels / Queue / Library sub-tabs (see `gui/platform_tab.py`). Engine
signals route per-platform via `detect_platform(url)` so each tab's queue
table only shows its own downloads.
"""

import os
import sys
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app_state import AppState, clear_state_section
from config import (
    AppConfig,
    HistoryRecord,
    SAVED_CHANNELS_PATH,
    STATE_PATH,
    load_history_records,
    save_history_records,
)
from download_engine import DownloadEngine
from gui.facebook_browser_panel import FacebookBrowserPanel
from gui.global_url_bar import GlobalUrlBar
from gui.icons import icon
from gui.library_panel import LibraryPanel
from gui.platform_tab import PlatformTab
from gui.settings_panel import SettingsPanel
from gui.status_bar_widget import StatusBarWidget
from gui.tiktok_browser_panel import TikTokBrowserPanel
from saved_channels_store import load_saved_channels, resolve_page_hint
from url_parser import detect_platform


def _resolve_icon() -> QIcon:
    """Locate icon.ico in source tree or PyInstaller bundle; empty QIcon if missing."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    path = Path(base) / "assets" / "icon.ico"
    return QIcon(str(path)) if path.exists() else QIcon()


class MainWindow(QMainWindow):
    """TikTokDer main window — TikTok / Facebook / Settings tabs."""

    def __init__(
        self,
        config: AppConfig,
        state: AppState | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self._initial_state = state or AppState()

        self.setWindowTitle("TikTokDer")
        self.setWindowIcon(_resolve_icon())
        self._restore_geometry()
        self._setup_menu()

        # Download engine — shared across all platform tabs.
        self.engine = DownloadEngine(
            output_dir=config.output_dir,
            max_workers=config.workers,
            delay=config.delay,
            cookie_browser=config.cookie_browser,
            cookies_file=config.cookies_file,
            quality=config.quality_default,
            write_subs=config.write_subtitles,
            write_thumb=config.write_thumbnail,
            history_max_entries=config.history_max_entries,
            parent=self,
        )

        # Saved-channels store — loaded once, persisted by panels on mutation.
        self._saved_store = load_saved_channels(SAVED_CHANNELS_PATH)

        # Browser panels — created here so settings live-propagate cleanly.
        self._tiktok_browser = TikTokBrowserPanel(cookie_browser=config.cookie_browser)
        self._facebook_browser = FacebookBrowserPanel(
            cookies_file=config.cookies_file,
            default_scrolls=config.facebook_max_scrolls_default,
        )

        # Central widget — global URL bar + tab widget.
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.global_url_bar = GlobalUrlBar()
        central_layout.addWidget(self.global_url_bar)
        self.tabs = QTabWidget()
        central_layout.addWidget(self.tabs, stretch=1)
        self.setCentralWidget(central)

        self.tiktok_tab = PlatformTab(
            platform="tiktok",
            browser_panel=self._tiktok_browser,
            store=self._saved_store,
            store_path=SAVED_CHANNELS_PATH,
        )
        self.facebook_tab = PlatformTab(
            platform="facebook",
            browser_panel=self._facebook_browser,
            store=self._saved_store,
            store_path=SAVED_CHANNELS_PATH,
        )
        self.settings_panel = SettingsPanel(config)

        self.tabs.addTab(self.tiktok_tab, icon("mdi6.music-note"), "TikTok")
        self.tabs.addTab(self.facebook_tab, icon("mdi6.facebook"), "Facebook")
        self.tabs.addTab(self.settings_panel, icon("mdi6.cog"), "Settings")

        # Resolver lets saved-channels panel snapshot engine dedup IDs without
        # holding a hard ref (avoids a hard widget→engine coupling).
        self.tiktok_tab.channels_panel.history_ids_resolver = lambda: set(self.engine._history)
        self.facebook_tab.channels_panel.history_ids_resolver = lambda: set(self.engine._history)

        # Replace placeholder Library panels with the real two-pane widgets.
        self.tiktok_tab.replace_library_panel(
            LibraryPanel(platform="tiktok", saved_store=self._saved_store)
        )
        self.facebook_tab.replace_library_panel(
            LibraryPanel(platform="facebook", saved_store=self._saved_store)
        )

        # Status bar — per-platform badges + free-text.
        self.status_widget = StatusBarWidget()
        self.statusBar().addPermanentWidget(self.status_widget, stretch=1)

        self._connect_signals()
        self._restore_state(self._initial_state)

    # ── signal wiring ─────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Engine → per-platform queue tables.
        self.engine.download_started.connect(self._route_started)
        self.engine.download_progress.connect(self._route_progress)
        self.engine.download_finished.connect(self._route_finished)
        self.engine.all_finished.connect(self._on_all_finished)

        # Cancel/Retry/Clear from each queue table.
        for tab in (self.tiktok_tab, self.facebook_tab):
            tab.queue_panel.cancel_all_btn.clicked.connect(self.engine.cancel_all)
            tab.queue_panel.retry_requested.connect(self._on_retry_requested)
            tab.queue_panel.force_download_requested.connect(self._on_force_download_requested)
            tab.queue_panel.clear_all_requested.connect(self._on_clear_all_requested)

        # Saved-channels download-all-new.
        self.tiktok_tab.channels_panel.download_requested.connect(self._on_channel_download)
        self.facebook_tab.channels_panel.download_requested.connect(self._on_channel_download)

        # Global URL bar — splits per platform internally.
        self.global_url_bar.urls_submitted.connect(self._on_urls_submitted)

        # Drag-drop on each platform tab (filtered to that platform).
        self.tiktok_tab.urls_dropped.connect(self._on_urls_dropped)
        self.facebook_tab.urls_dropped.connect(self._on_urls_dropped)

        # Browser panels' "Download Selected" → queue.
        self._tiktok_browser.download_requested.connect(self._on_channel_download)
        self._facebook_browser.download_requested.connect(self._on_channel_download)

        # Library actions per-platform.
        for tab in (self.tiktok_tab, self.facebook_tab):
            lib = tab.library_panel
            lib.redownload_requested.connect(self._on_history_redownload)
            lib.remove_history_requested.connect(self._on_history_remove)

        # Engine history → both library panels refresh.
        self.engine.history_changed.connect(self.tiktok_tab.library_panel.refresh)
        self.engine.history_changed.connect(self.facebook_tab.library_panel.refresh)

        # Initial population.
        self.tiktok_tab.library_panel.refresh()
        self.facebook_tab.library_panel.refresh()

        # Settings → engine + panels (live propagation).
        self.settings_panel.settings_changed.connect(self._apply_settings)

    # ── per-platform routing ──────────────────────────────────────────────

    def _tab_for_url(self, url: str) -> PlatformTab:
        return self.facebook_tab if detect_platform(url) == "facebook" else self.tiktok_tab

    @Slot(str)
    def _route_started(self, url: str) -> None:
        self._tab_for_url(url).queue_panel.on_download_started(url)

    @Slot(str, float)
    def _route_progress(self, url: str, percent: float) -> None:
        self._tab_for_url(url).queue_panel.on_download_progress(url, percent)

    @Slot(str, object)
    def _route_finished(self, url: str, result) -> None:
        self._tab_for_url(url).queue_panel.on_download_finished(url, result)
        self._update_status_count()

    @Slot()
    def _on_all_finished(self) -> None:
        self.update_status("All downloads complete")

    # ── url submission helpers ────────────────────────────────────────────

    def _queue_url(self, url: str) -> None:
        self._tab_for_url(url).queue_panel.add_download(url)

    @Slot(list, str)
    def _on_channel_download(self, urls: list[str], page_hint: str = "") -> None:
        """Browser-panel or saved-channel `Download all new` → queue per platform.

        `page_hint` is the source page URL the user browsed; threaded into the
        engine so each video lands in `<platform>/<page>/` even when its own
        URL (e.g. ``/reel/<id>``) carries no page name. When the URL matches
        a saved channel with a nickname, the nickname wins so users can name
        ugly URLs (e.g. ``profile.php?id=...``) anything they like.
        """
        for url in urls:
            self._queue_url(url)
        platform = detect_platform(page_hint) if page_hint else None
        resolved = resolve_page_hint(self._saved_store, platform, page_hint) if page_hint else ""
        self.engine.add_urls(urls, page_hint=resolved or None)
        self._focus_first_platform(urls)
        self._update_status_count()

    @Slot(list)
    def _on_urls_dropped(self, urls: list[str]) -> None:
        for url in urls:
            self._queue_url(url)
        self.engine.add_urls(urls)
        self._focus_first_platform(urls)
        self._update_status_count()

    @Slot(list)
    def _on_urls_submitted(self, urls: list[str]) -> None:
        """Global URL bar entry — same path as drop, mixed-platform OK."""
        if not urls:
            return
        for url in urls:
            self._queue_url(url)
        self.engine.add_urls(urls)
        self._focus_first_platform(urls)
        self._update_status_count()

    def _focus_first_platform(self, urls: list[str]) -> None:
        """Switch active tab to the platform of the first URL in the batch."""
        if not urls:
            return
        target = self._tab_for_url(urls[0])
        target.set_active_sub_tab(1)  # show the Queue sub-tab
        self.tabs.setCurrentWidget(target)

    # ── retry / clear ─────────────────────────────────────────────────────

    @Slot(list)
    def _on_retry_requested(self, urls: list[str]) -> None:
        if urls:
            self.engine.retry_urls(urls)
            self._update_status_count()

    @Slot(list)
    def _on_force_download_requested(self, urls: list[str]) -> None:
        if urls:
            self.engine.retry_urls(urls, force=True)
            self._update_status_count()

    @Slot(str)
    def _on_history_redownload(self, url: str) -> None:
        """Library 'Re-download' → switch to platform queue + force re-queue."""
        target = self._tab_for_url(url)
        target.queue_panel.add_download(url)
        self.engine.retry_url(url, force=True)
        target.set_active_sub_tab(1)
        self.tabs.setCurrentWidget(target)
        self._update_status_count()

    @Slot(str)
    def _on_history_remove(self, video_id: str) -> None:
        """Library 'Remove from history' → drop record + refresh both libraries."""
        records = [r for r in load_history_records() if r.video_id != video_id]
        save_history_records(records)
        self.engine._history.discard(video_id)
        self.tiktok_tab.library_panel.refresh()
        self.facebook_tab.library_panel.refresh()

    @Slot(list)
    def _on_clear_all_requested(self, urls: list[str]) -> None:
        self.engine.cancel_all()
        self.engine.clear_dedup(urls)
        self._update_status_count()
        try:
            clear_state_section(STATE_PATH, clear_queue=True)
        except OSError:
            pass

    # ── status ────────────────────────────────────────────────────────────

    def _count_pending(self, tab: PlatformTab) -> int:
        """Rows in non-terminal states (Queued / Downloading) for one platform."""
        active_states = {"Queued", "Downloading"}
        return sum(
            1 for d in tab.queue_panel._row_data.values()
            if d.get("status") in active_states
        )

    def _update_status_count(self) -> None:
        tt_pending = self._count_pending(self.tiktok_tab)
        fb_pending = self._count_pending(self.facebook_tab)
        done = (
            self.tiktok_tab.queue_panel.get_completed_count()
            + self.facebook_tab.queue_panel.get_completed_count()
        )
        self.status_widget.set_counts(tt_pending, fb_pending, done)

    def update_status(self, text: str) -> None:
        self.status_widget.set_counts(
            self._count_pending(self.tiktok_tab),
            self._count_pending(self.facebook_tab),
            self.tiktok_tab.queue_panel.get_completed_count()
            + self.facebook_tab.queue_panel.get_completed_count(),
            text,
        )

    # ── settings propagation ──────────────────────────────────────────────

    @Slot()
    def _apply_settings(self) -> None:
        self.engine.output_dir = self.config.output_dir
        self.engine.max_workers = self.config.workers
        self.engine.delay = self.config.delay
        self.engine.cookie_browser = self.config.cookie_browser
        self.engine.cookies_file = self.config.cookies_file
        self.engine.quality = self.config.quality_default
        self.engine.write_subs = self.config.write_subtitles
        self.engine.write_thumb = self.config.write_thumbnail
        self.engine.history_max_entries = self.config.history_max_entries
        self._tiktok_browser.cookie_browser = self.config.cookie_browser
        self._facebook_browser.cookies_file = self.config.cookies_file

    # ── menu ──────────────────────────────────────────────────────────────

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(icon("mdi6.import"), "&Import URLs...", self._on_import_urls)
        file_menu.addAction(icon("mdi6.export"), "&Export URLs...", self._on_export_urls)
        file_menu.addSeparator()
        file_menu.addAction(icon("mdi6.exit-to-app"), "E&xit", self.close)
        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(icon("mdi6.information-outline"), "&About", self._show_about)

    @Slot()
    def _on_import_urls(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import URL list", "", "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        from url_parser import read_batch_file, validate_url

        try:
            urls = read_batch_file(path)
        except OSError:
            return
        valid = [u for u in urls if validate_url(u)]
        if valid:
            self._on_urls_dropped(valid)

    @Slot()
    def _on_export_urls(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export URL list", "urls.txt", "Text files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for tab_name, tab in (("TikTok", self.tiktok_tab), ("Facebook", self.facebook_tab)):
                    queue_urls = [
                        d.get("url") for d in tab.queue_panel._row_data.values() if d.get("url")
                    ]
                    if queue_urls:
                        f.write(f"# === {tab_name} Queue ===\n")
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

    @Slot()
    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About TikTokDer",
            "TikTokDer - Video Downloader\n\n"
            "Download TikTok and Facebook videos without watermarks.\n"
            "Powered by yt-dlp.",
        )

    # ── geometry / state ──────────────────────────────────────────────────

    def _restore_geometry(self) -> None:
        self.resize(self.config.window_width, self.config.window_height)
        if self.config.window_x is not None and self.config.window_y is not None:
            self.move(self.config.window_x, self.config.window_y)

    def _restore_state(self, state: AppState) -> None:
        # Restore queue rows: each row goes to its platform tab.
        if state.download_queue:
            tt_items = [q for q in state.download_queue if detect_platform(q.url) == "tiktok"]
            fb_items = [q for q in state.download_queue if detect_platform(q.url) == "facebook"]
            if tt_items:
                self.tiktok_tab.queue_panel.load_from_state(tt_items)
            if fb_items:
                self.facebook_tab.queue_panel.load_from_state(fb_items)
            self._update_status_count()

        # Restore browser panel state.
        self._tiktok_browser.load_from_state(state.tiktok_browser)
        self._facebook_browser.load_from_state(state.facebook_browser)

        # Restore library active uploader per platform.
        self.tiktok_tab.library_panel.set_active_uploader(state.library_active_uploader_tiktok)
        self.facebook_tab.library_panel.set_active_uploader(state.library_active_uploader_facebook)

        if 0 <= state.active_tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(state.active_tab_index)

    def snapshot_state(self) -> AppState:
        # Combine per-platform queues into one snapshot list.
        queue = (
            self.tiktok_tab.queue_panel.snapshot()
            + self.facebook_tab.queue_panel.snapshot()
        )
        return AppState(
            active_tab_index=self.tabs.currentIndex(),
            channel_active_sub_tab=self.tiktok_tab.current_sub_tab_index(),
            download_queue=queue,
            tiktok_browser=self._tiktok_browser.snapshot(),
            facebook_browser=self._facebook_browser.snapshot(),
            library_active_uploader_tiktok=self.tiktok_tab.library_panel.active_uploader(),
            library_active_uploader_facebook=self.facebook_tab.library_panel.active_uploader(),
        )
