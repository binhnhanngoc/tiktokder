"""Main application window — platform-first 3-tab IA.

Layout: TikTok | Facebook | Settings, each platform tab a composite of
Channels / Queue / Library sub-tabs (see `gui/platform_tab.py`). Engine
signals route per-platform via `detect_platform(url)` so each tab's queue
table only shows its own downloads.
"""

import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence
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
    save_config,
    save_history_records,
)
from download_engine import DownloadEngine
from gui.facebook_browser_panel import FacebookBrowserPanel
from gui.global_url_bar import GlobalUrlBar
from gui.help_content import (
    TAB_ABOUT,
    TAB_CHANNELS_LIBRARY,
    TAB_COOKIES_CONFIGURE,
    TAB_COOKIES_EXPORT,
    TAB_GETTING_STARTED,
    TAB_SHORTCUTS,
    TAB_TROUBLESHOOTING,
)
from gui.help_dialog import HelpDialog
from gui.icons import icon
from gui.library_panel import LibraryPanel
from gui.platform_tab import PlatformTab
from gui.settings_panel import SettingsPanel
from gui.status_bar_widget import StatusBarWidget
from gui.tiktok_browser_panel import TikTokBrowserPanel
from gui.update_dialog import UpdateAvailableDialog
from health_check import (
    HealthIssue,
    HealthReport,
    compute_health,
    default_cache_path,
    dismiss_issue,
)
from saved_channels_store import load_saved_channels, resolve_page_hint
from update_checker import (
    ReleaseInfo,
    is_newer,
    latest_release,
    should_check_now,
)
from url_parser import detect_platform
from version import __version__, __version_info__

_HEALTH_TIMER_MS = 30 * 60 * 1000  # 30-minute periodic recompute


class _HealthWorkerSignals(QObject):
    """Cross-thread bridge for the health-compute worker."""

    done = Signal(object)  # HealthReport


class _HealthWorker(QRunnable):
    """One-shot QRunnable wrapping ``compute_health`` for the global thread pool."""

    def __init__(self, callable_) -> None:
        super().__init__()
        self._callable = callable_
        self.signals = _HealthWorkerSignals()

    def run(self) -> None:  # type: ignore[override]
        try:
            report = self._callable()
        except Exception:
            # Never crash the worker — UI thread continues with last known state.
            return
        self.signals.done.emit(report)


class _UpdateWorkerSignals(QObject):
    """Cross-thread bridge for the update-check worker.

    ``done`` carries ``(ReleaseInfo | None, is_manual: bool)`` so the
    receiving slot can pick the right surface (silent vs QMessageBox).
    """

    done = Signal(object, bool)


class _UpdateWorker(QRunnable):
    """One-shot QRunnable wrapping ``update_checker.latest_release``.

    Mirrors ``_HealthWorker``: caught-everything defensive ``run`` so a
    crashed worker never tears down the global thread pool.
    """

    def __init__(self, is_manual: bool) -> None:
        super().__init__()
        self._is_manual = is_manual
        self.signals = _UpdateWorkerSignals()

    def run(self) -> None:  # type: ignore[override]
        try:
            result = latest_release()
        except Exception:
            result = None
        self.signals.done.emit(result, self._is_manual)


def _resolve_icon() -> QIcon:
    """Locate icon.ico in source tree or PyInstaller bundle; empty QIcon if missing."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    path = Path(base) / "assets" / "icon.ico"
    return QIcon(str(path)) if path.exists() else QIcon()


class MainWindow(QMainWindow):
    """TikTokDer main window — TikTok / Facebook / Settings tabs."""

    # Emitted after every update-check completion (success / fail / no-op),
    # so the About-tab pill can re-render without polling.
    update_check_finished = Signal()

    def __init__(
        self,
        config: AppConfig,
        state: AppState | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self._initial_state = state or AppState()

        self.setWindowTitle(f"TikTokDer v{__version__}")
        self.setWindowIcon(_resolve_icon())
        self._restore_geometry()
        # Help dialog is created lazily on first open so app launch stays cheap.
        self._help_dialog: HelpDialog | None = None
        # Cached last successful update-check payload (None when never checked
        # or last check failed). Read by the About-tab pill (phase-05).
        self._latest_release_cache: ReleaseInfo | None = None
        self._setup_menu()

        # Download engine — shared across all platform tabs.
        self.engine = DownloadEngine(
            output_dir=config.output_dir,
            max_workers=config.workers,
            delay=config.delay,
            cookie_browser=config.cookie_browser,
            cookies_file=config.facebook_cookies_file,
            tiktok_cookies_file=config.tiktok_cookies_file,
            quality=config.quality_default,
            write_subs=config.write_subtitles,
            write_thumb=config.write_thumbnail,
            history_max_entries=config.history_max_entries,
            parent=self,
        )

        # Saved-channels store — loaded once, persisted by panels on mutation.
        self._saved_store = load_saved_channels(SAVED_CHANNELS_PATH)

        # Browser panels — created here so settings live-propagate cleanly.
        self._tiktok_browser = TikTokBrowserPanel(
            cookie_browser=config.cookie_browser,
            cookies_file=config.tiktok_cookies_file,
        )
        self._facebook_browser = FacebookBrowserPanel(
            cookies_file=config.facebook_cookies_file,
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

        # Browser panels: same id resolver for the ✓ column / Downloaded
        # filter, plus a record resolver for the timestamp tooltip. Records
        # are loaded from disk lazily and invalidated on history_changed.
        self._history_records_cache: dict[str, HistoryRecord] | None = None
        for browser in (self._tiktok_browser, self._facebook_browser):
            browser.history_ids_resolver = lambda: set(self.engine._history)
            browser.history_record_resolver = self._lookup_history_record

        # Restore + persist + live-refresh the per-platform Downloaded combo.
        for browser, field_name in (
            (self._tiktok_browser, "tiktok_browse_downloaded_filter"),
            (self._facebook_browser, "facebook_browse_downloaded_filter"),
        ):
            browser.set_downloaded_filter(getattr(self.config, field_name))
            browser.downloaded_combo.currentIndexChanged.connect(
                lambda _i, b=browser, f=field_name: self._save_browse_filter(b, f)
            )
            self.engine.history_changed.connect(browser.on_history_changed)

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

        # Health refresh: 30-min QTimer + post-fetch trigger. Compute runs in
        # the global QThreadPool so the network branch (yt-dlp PyPI) never
        # blocks the UI thread.
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(_HEALTH_TIMER_MS)
        self._health_timer.timeout.connect(self._refresh_health)

        self._connect_signals()
        self._restore_state(self._initial_state)

        self._health_timer.start()
        # Kick off the first compute — non-network, fast — right after init.
        QTimer.singleShot(0, self._refresh_health)
        # Update probe — delayed 2000ms so the first paint isn't blocked by
        # a thread-pool spin-up. Honours opt-out and 24h cache gates.
        QTimer.singleShot(2000, self._maybe_check_updates_background)

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

        # Engine history → both library panels refresh + health recompute.
        self.engine.history_changed.connect(self.tiktok_tab.library_panel.refresh)
        self.engine.history_changed.connect(self.facebook_tab.library_panel.refresh)
        self.engine.history_changed.connect(self._refresh_health)
        # Drop the by-id record cache so the browser ✓ tooltip picks up new
        # downloads immediately (Phase 03 wires the live cell refresh).
        self.engine.history_changed.connect(self._invalidate_history_records_cache)

        # Initial population.
        self.tiktok_tab.library_panel.refresh()
        self.facebook_tab.library_panel.refresh()

        # Settings → engine + panels (live propagation).
        self.settings_panel.settings_changed.connect(self._apply_settings)

        # Health pill click → action dispatcher.
        self.status_widget.health_action_requested.connect(self._handle_health_action)
        # Settings Health rows: fix/dismiss/manual-refresh.
        self.settings_panel.fix_action_requested.connect(self._handle_health_action)
        self.settings_panel.dismiss_action_requested.connect(self._on_dismiss_health_issue)
        self.settings_panel.manual_refresh_requested.connect(
            lambda: self._refresh_health(check_yt_dlp=True)
        )

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

    # ── health ────────────────────────────────────────────────────────────

    @Slot()
    def _refresh_health(self, *, check_yt_dlp: bool = False) -> None:
        """Spawn a worker that runs ``compute_health`` off the UI thread."""
        config = self.config
        store = self._saved_store
        # Snapshot history off the UI thread inside the worker (cheap I/O,
        # but keeps the closure self-contained).
        def work() -> HealthReport:
            records = load_history_records()
            return compute_health(store, records, config, check_yt_dlp=check_yt_dlp)

        worker = _HealthWorker(work)
        worker.signals.done.connect(self._on_health_ready)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _on_health_ready(self, report: HealthReport) -> None:
        """Route a fresh HealthReport into the pill + Settings section."""
        self.status_widget.set_health_report(report)
        if hasattr(self.settings_panel, "set_health_report"):
            self.settings_panel.set_health_report(report)

    @Slot(object)
    def _handle_health_action(self, issue: HealthIssue) -> None:
        """Dispatch a fix-action requested from the pill popover or Settings row."""
        kind = issue.fix_action_kind
        arg = issue.fix_action_arg or ""
        if kind == "open_path" and arg:
            QDesktopServices.openUrl(QUrl.fromLocalFile(arg))
        elif kind == "open_url" and arg.startswith("https://"):
            QDesktopServices.openUrl(QUrl(arg))
        elif kind == "refresh_channel" and arg:
            self._refresh_saved_channel(arg)
        # "none" / unknown → no-op

    def _save_browse_filter(self, panel, field_name: str) -> None:
        """Persist combo selection to AppConfig on every change."""
        setattr(self.config, field_name, panel.downloaded_combo.currentData())
        try:
            save_config(self.config)
        except OSError:
            # Persistence is best-effort — the combo state lives in-memory
            # for the rest of the session even if the disk write failed.
            pass

    def _lookup_history_record(self, video_id: str) -> HistoryRecord | None:
        """Lazy by-id lookup over history records; cache invalidated on history_changed."""
        if not video_id:
            return None
        if self._history_records_cache is None:
            self._history_records_cache = {
                r.video_id: r for r in load_history_records() if r.video_id
            }
        return self._history_records_cache.get(video_id)

    def _invalidate_history_records_cache(self) -> None:
        self._history_records_cache = None

    def _refresh_saved_channel(self, channel_url: str) -> None:
        """Find the saved channel in either platform tab and trigger its refresh."""
        for tab in (self.tiktok_tab, self.facebook_tab):
            panel = tab.channels_panel
            channel = panel.store.find_by_url(panel.platform, channel_url)
            if channel is not None:
                tab.set_active_sub_tab(0)  # Channels sub-tab
                self.tabs.setCurrentWidget(tab)
                panel._refresh_channel(channel)
                return

    @Slot(str)
    def _on_dismiss_health_issue(self, issue_id: str) -> None:
        """Persist a dismissal then re-render so the row disappears immediately."""
        dismiss_issue(default_cache_path(), issue_id)
        self._refresh_health()

    # ── settings propagation ──────────────────────────────────────────────

    @Slot()
    def _apply_settings(self) -> None:
        self.engine.output_dir = self.config.output_dir
        self.engine.max_workers = self.config.workers
        self.engine.delay = self.config.delay
        self.engine.cookie_browser = self.config.cookie_browser
        self.engine.cookies_file = self.config.facebook_cookies_file
        self.engine.tiktok_cookies_file = self.config.tiktok_cookies_file
        self.engine.quality = self.config.quality_default
        self.engine.write_subs = self.config.write_subtitles
        self.engine.write_thumb = self.config.write_thumbnail
        self.engine.history_max_entries = self.config.history_max_entries
        self._tiktok_browser.cookie_browser = self.config.cookie_browser
        self._tiktok_browser.cookies_file = self.config.tiktok_cookies_file
        self._facebook_browser.cookies_file = self.config.facebook_cookies_file

    # ── menu ──────────────────────────────────────────────────────────────

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(icon("mdi6.import"), "&Import URLs...", self._on_import_urls)
        file_menu.addAction(icon("mdi6.export"), "&Export URLs...", self._on_export_urls)
        file_menu.addSeparator()
        file_menu.addAction(icon("mdi6.exit-to-app"), "E&xit", self.close)

        help_menu = menu_bar.addMenu("&Help")
        manual_action = help_menu.addAction(
            icon("mdi6.book-open-variant"),
            "User &Manual",
            lambda: self._open_help(TAB_GETTING_STARTED),
        )
        manual_action.setShortcut(QKeySequence("F1"))
        help_menu.addAction(
            icon("mdi6.cookie-outline"),
            "How to &Export Cookies",
            lambda: self._open_help(TAB_COOKIES_EXPORT),
        )
        help_menu.addAction(
            icon("mdi6.cookie-cog-outline"),
            "How to &Configure Cookies",
            lambda: self._open_help(TAB_COOKIES_CONFIGURE),
        )
        help_menu.addAction(
            icon("mdi6.bookmark-multiple-outline"),
            "&Channels && Library",
            lambda: self._open_help(TAB_CHANNELS_LIBRARY),
        )
        help_menu.addAction(
            icon("mdi6.lifebuoy"),
            "&Troubleshooting",
            lambda: self._open_help(TAB_TROUBLESHOOTING),
        )
        help_menu.addAction(
            icon("mdi6.keyboard-outline"),
            "&Keyboard Shortcuts",
            lambda: self._open_help(TAB_SHORTCUTS),
        )
        help_menu.addAction(
            icon("mdi6.update"),
            "Check for &Updates…",
            self._on_check_updates_manual,
        )
        help_menu.addSeparator()
        help_menu.addAction(
            icon("mdi6.information-outline"),
            "&About",
            lambda: self._open_help(TAB_ABOUT),
        )

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

    def _open_help(self, tab_id: str) -> None:
        """Lazily instantiate HelpDialog and jump to the requested tab."""
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self, main_window=self)
        self._help_dialog.open_at_tab(tab_id)

    # ── update checker ────────────────────────────────────────────────────

    def _maybe_check_updates_background(self) -> None:
        """Startup probe gated by opt-out and 24h cache. Silent on every failure."""
        if not self.config.update_check_enabled:
            return
        if not should_check_now(self.config.last_update_check_at):
            return
        self._spawn_update_worker(is_manual=False)

    @Slot()
    def _on_check_updates_manual(self) -> None:
        """Help → Check for Updates…  Bypasses every gate; user asked explicitly."""
        self.update_status("Checking for updates…")
        self._spawn_update_worker(is_manual=True)

    def _spawn_update_worker(self, is_manual: bool) -> None:
        worker = _UpdateWorker(is_manual)
        worker.signals.done.connect(self._on_update_check_done)
        QThreadPool.globalInstance().start(worker)

    @Slot(object, bool)
    def _on_update_check_done(self, result: ReleaseInfo | None, is_manual: bool) -> None:
        """Apply a worker's outcome: cache, persist timestamp, surface or stay silent.

        Background path is silent on every miss / failure. Manual path always
        shows an outcome — newer / up-to-date / failed.
        """
        # Always write the timestamp; one failure = 24h cooldown for background.
        self.config.last_update_check_at = time.time()
        self._latest_release_cache = result
        try:
            save_config(self.config)
        except OSError:
            pass

        if result is None:
            if is_manual:
                QMessageBox.warning(
                    self,
                    "Update Check Failed",
                    "Could not reach GitHub. Check your internet connection "
                    "and try again.",
                )
            self.update_check_finished.emit()
            return

        if is_newer(result.version, __version_info__):
            # Background path: respect Skip-this-version.
            if not is_manual and result.version_str == self.config.skipped_update_version:
                self.update_check_finished.emit()
                return
            self._show_update_dialog(result)
        else:
            if is_manual:
                QMessageBox.information(
                    self,
                    "Up to Date",
                    f"You're running the latest version (v{__version__}).",
                )

        self.update_check_finished.emit()

    def _show_update_dialog(self, release: ReleaseInfo) -> None:
        """Construct + exec UpdateAvailableDialog; persist user choices."""
        dialog = UpdateAvailableDialog(
            release=release,
            current_version_str=__version__,
            opt_out_currently=not self.config.update_check_enabled,
            parent=self,
        )
        dialog.skip_requested.connect(self._on_skip_version)
        dialog.exec()
        # Read final checkbox state and flip config if it changed.
        new_opt_out = dialog.opt_out_chosen()
        new_enabled = not new_opt_out
        if new_enabled != self.config.update_check_enabled:
            self.config.update_check_enabled = new_enabled
            try:
                save_config(self.config)
            except OSError:
                pass

    @Slot(str)
    def _on_skip_version(self, version_str: str) -> None:
        """Persist the version the user chose to skip."""
        self.config.skipped_update_version = version_str
        try:
            save_config(self.config)
        except OSError:
            pass

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

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Stop the health timer and drain in-flight workers before teardown.

        Also flushes the in-app player's position so resume-on-next-launch
        doesn't drift by up to one debounce window when the user closes
        the app mid-playback.

        Without this, a worker emitting ``done`` after Qt has begun deleting
        child widgets can land on a dangling slot and crash on Windows.
        """
        try:
            self._health_timer.stop()
        except Exception:
            pass
        # Flush both library players' positions before teardown.
        for tab in (self.tiktok_tab, self.facebook_tab):
            panel = getattr(tab, "library_panel", None)
            preview = getattr(panel, "preview_pane", None)
            if preview is not None and hasattr(preview, "stop_and_show_thumb"):
                try:
                    preview.stop_and_show_thumb()
                except Exception:
                    pass
        try:
            QThreadPool.globalInstance().waitForDone(2000)
        except Exception:
            pass
        super().closeEvent(event)

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
