"""Smoke tests for SavedChannelsPanel + PlatformTab — Qt-offscreen.

Spins up `QApplication` once with the offscreen platform plugin so widgets
construct without a display. Tests cover:
  * panel instantiates against a real platform browser
  * download_requested emits filtered URLs after select_new_videos
  * PlatformTab drag-drop only routes own-platform URLs
  * MainWindow routes engine signals to the right platform's queue
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

# Force Qt to a headless platform before importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from saved_channels_store import (
    SavedChannel,
    SavedChannelsStore,
    add_channel,
    save_saved_channels,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Panel smoke ───────────────────────────────────────────────────────────

def test_saved_channels_panel_constructs(qapp, tmp_path: Path) -> None:
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel

    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://www.tiktok.com/@a", nickname="A"))

    browser = TikTokBrowserPanel()
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )
    assert panel.table.rowCount() == 1


def test_download_all_new_emits_filtered_urls(qapp, tmp_path: Path) -> None:
    """`Download all new` → emit URLs that are not in history and post-cutoff."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel
    from channel_fetcher import VideoInfo

    store = SavedChannelsStore()
    add_channel(
        store,
        "tiktok",
        SavedChannel(
            url="https://www.tiktok.com/@a",
            last_fetched_at="2026-04-20T00:00:00+00:00",
        ),
    )

    browser = TikTokBrowserPanel()
    # Seed the browser cache directly (skip the actual yt-dlp fetch).
    browser._videos = [
        VideoInfo(url="https://x/v/old", title="o", duration=0, view_count=0,
                  upload_date="20260415", video_id="old"),
        VideoInfo(url="https://x/v/new1", title="n1", duration=0, view_count=0,
                  upload_date="20260425", video_id="new1"),
        VideoInfo(url="https://x/v/dup", title="d", duration=0, view_count=0,
                  upload_date="20260426", video_id="dup"),
    ]
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )
    panel.history_ids_resolver = lambda: {"dup"}

    captured: list[tuple[list[str], str]] = []
    panel.download_requested.connect(lambda urls, hint: captured.append((urls, hint)))

    ch = store.find_by_url("tiktok", "https://www.tiktok.com/@a")
    panel._download_all_new(ch)

    assert captured == [(["https://x/v/new1"], "https://www.tiktok.com/@a")]
    # mark_fetched should have updated channel state.
    refreshed = store.find_by_url("tiktok", "https://www.tiktok.com/@a")
    assert refreshed.last_fetched_at != "2026-04-20T00:00:00+00:00"
    assert sorted(refreshed.last_fetched_video_ids) == ["dup", "new1", "old"]


# ── PlatformTab drag-drop routing ─────────────────────────────────────────

def test_platform_tab_filters_drag_drop_to_own_platform(qapp, tmp_path: Path) -> None:
    """A facebook URL dropped on the TikTok tab is rejected."""
    from gui.platform_tab import PlatformTab
    from gui.tiktok_browser_panel import TikTokBrowserPanel

    store = SavedChannelsStore()
    browser = TikTokBrowserPanel()
    tab = PlatformTab(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )

    # Construct a synthetic mime drop with mixed URLs.
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import QDropEvent

    mime = QMimeData()
    mime.setText(
        "https://www.tiktok.com/@a/video/123\n"
        "https://www.facebook.com/somepage/videos/456"
    )
    event = QDropEvent(QPointF(0, 0), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    captured: list[list[str]] = []
    tab.urls_dropped.connect(captured.append)
    tab.dropEvent(event)

    # Only the TikTok URL emerges on the TikTok tab.
    assert captured == [["https://www.tiktok.com/@a/video/123"]]


# ── MainWindow signal routing ─────────────────────────────────────────────

def test_main_window_routes_signals_to_platform_queues(qapp, tmp_path, monkeypatch) -> None:
    """A TikTok download_started routes to TikTok queue only — FB stays empty."""
    from config import AppConfig

    # Redirect saved-channels path to tmp so the real file isn't touched.
    monkeypatch.setattr("gui.main_window.SAVED_CHANNELS_PATH", tmp_path / "saved.json")

    from gui.main_window import MainWindow

    config = AppConfig()
    win = MainWindow(config)
    tt_url = "https://www.tiktok.com/@a/video/1"
    fb_url = "https://www.facebook.com/page/videos/2"

    win.tiktok_tab.queue_panel.add_download(tt_url)
    win.facebook_tab.queue_panel.add_download(fb_url)

    # Fire the routing slot directly — equivalent to engine.download_started.
    win._route_started(tt_url)
    # TikTok queue row 0 status should now be "Downloading".
    assert win.tiktok_tab.queue_panel._row_data[0]["status"] == "Downloading"
    # Facebook row should still be Queued.
    assert win.facebook_tab.queue_panel._row_data[0]["status"] == "Queued"


# ── Per-channel browse cache ──────────────────────────────────────────────

def test_show_channel_with_cache_loads_without_fetch(qapp, tmp_path: Path) -> None:
    """Activating a saved row with cached videos populates the browser table
    instantly — no fetcher is created."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel
    from saved_channels_store import CachedVideo

    store = SavedChannelsStore()
    add_channel(
        store,
        "tiktok",
        SavedChannel(
            url="https://www.tiktok.com/@cached",
            cached_videos=[
                CachedVideo(url="https://x/v/1", title="one", video_id="v1"),
                CachedVideo(url="https://x/v/2", title="two", video_id="v2"),
            ],
        ),
    )

    browser = TikTokBrowserPanel()
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )

    ch = store.find_by_url("tiktok", "https://www.tiktok.com/@cached")
    panel._show_channel(ch)

    # Browser panel restored from cache — no fetcher created.
    assert browser._fetcher is None
    assert [v.video_id for v in browser._videos] == ["v1", "v2"]
    assert browser.url_input.text() == "https://www.tiktok.com/@cached"
    assert browser.table.rowCount() == 2


def test_fetch_completed_signal_persists_cache(qapp, tmp_path: Path) -> None:
    """After a fetch finishes, the saved channel's cache is updated and saved."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel
    from channel_fetcher import VideoInfo

    store_path = tmp_path / "saved.json"
    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://www.tiktok.com/@a"))

    browser = TikTokBrowserPanel()
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=store_path,
    )

    # Simulate a completed fetch: URL set, _videos populated, signal emits.
    browser.url_input.setText("https://www.tiktok.com/@a")
    browser._videos = [
        VideoInfo(url="https://x/v/1", title="t1", duration=10,
                  view_count=50, upload_date="20260427", video_id="v1", quality="720p"),
        VideoInfo(url="https://x/v/2", title="t2", duration=20,
                  view_count=99, upload_date="20260427", video_id="v2"),
    ]
    panel._on_browser_fetch_completed(2)

    ch = store.find_by_url("tiktok", "https://www.tiktok.com/@a")
    assert [v.video_id for v in ch.cached_videos] == ["v1", "v2"]
    # Persisted to disk.
    from saved_channels_store import load_saved_channels
    reloaded = load_saved_channels(store_path)
    assert [v.video_id for v in reloaded.tiktok[0].cached_videos] == ["v1", "v2"]


def test_fetch_completed_signal_ignores_unsaved_url(qapp, tmp_path: Path) -> None:
    """Ad-hoc Browse for a URL that isn't saved leaves the store untouched."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel
    from channel_fetcher import VideoInfo

    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://www.tiktok.com/@saved"))

    browser = TikTokBrowserPanel()
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )

    browser.url_input.setText("https://www.tiktok.com/@unsaved-random")
    browser._videos = [VideoInfo(url="https://x/v/1", title="t", duration=0,
                                  view_count=0, upload_date=None, video_id="v1")]
    panel._on_browser_fetch_completed(1)

    ch = store.find_by_url("tiktok", "https://www.tiktok.com/@saved")
    assert ch.cached_videos == []


# ── Fetch lifecycle (rapid-switch hang prevention) ────────────────────────

class _StubFetcher:
    """Bare-minimum stand-in for a QThread fetcher.

    BaseBrowserPanel only touches: ``video_found``, ``error``, ``finished_fetch``
    (signal-like), ``start()``, ``isRunning()``, ``cancel()``. We provide a
    callable-list shim instead of a real QThread so the test stays synchronous
    and free of Qt event-loop timing.
    """

    class _Sig:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot) -> None:
            self._slots.append(slot)

        def emit(self, *args) -> None:
            for slot in self._slots:
                slot(*args)

    def __init__(self) -> None:
        self.video_found = self._Sig()
        self.error = self._Sig()
        self.finished_fetch = self._Sig()
        self.started = False
        self.cancelled = False
        self._running = False

    def start(self) -> None:
        self.started = True
        self._running = True

    def isRunning(self) -> bool:
        return self._running

    def cancel(self) -> None:
        self.cancelled = True

    def simulate_finish(self, count: int = 0) -> None:
        self._running = False
        self.finished_fetch.emit(count)


def test_fetch_lifecycle_disables_saved_channels_controls(qapp, tmp_path: Path) -> None:
    """Saved-channels table + buttons disable while browser fetch runs, re-enable on finish."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel

    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://www.tiktok.com/@a"))

    browser = TikTokBrowserPanel()
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )

    # Idle: controls enabled.
    assert panel.table.isEnabled()
    assert panel.add_btn.isEnabled()
    assert panel.refresh_btn.isEnabled()

    # Drive a fetch via the stub.
    fetcher = _StubFetcher()
    browser._start_fetcher(fetcher)

    # Fetching: controls disabled, busy bar visible.
    # Use ``isHidden()`` (inverse of setVisible) — in offscreen mode parents
    # aren't shown, so ``isVisible()`` returns False even for setVisible(True).
    assert not panel.table.isEnabled()
    assert not panel.add_btn.isEnabled()
    assert not panel.refresh_btn.isEnabled()
    assert not browser.progress_bar.isHidden()
    assert not browser.cancel_btn.isHidden()
    assert not browser.url_input.isEnabled()
    assert not browser.browse_btn.isEnabled()

    # Finish: everything restored.
    fetcher.simulate_finish(0)
    assert panel.table.isEnabled()
    assert panel.add_btn.isEnabled()
    assert panel.refresh_btn.isEnabled()
    assert browser.progress_bar.isHidden()
    assert browser.cancel_btn.isHidden()
    assert browser.url_input.isEnabled()
    assert browser.browse_btn.isEnabled()


def test_browse_re_entry_during_fetch_is_ignored(qapp) -> None:
    """Programmatic _on_browse() while fetching must NOT spawn a second fetcher
    — that's the rapid-switch hang scenario."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel

    browser = TikTokBrowserPanel()
    fetcher = _StubFetcher()
    browser.url_input.setText("https://www.tiktok.com/@a")
    browser._start_fetcher(fetcher)
    first_fetcher = browser._fetcher

    # Simulate the rapid double-click path: SavedChannelsPanel._refresh_channel
    # would call browser._on_browse() directly. The re-entry guard must hold.
    browser._on_browse()
    assert browser._fetcher is first_fetcher
    assert fetcher.cancelled is False  # original fetch untouched

    fetcher.simulate_finish(0)
    assert browser._is_fetching is False


def test_cancel_does_not_block_main_thread(qapp) -> None:
    """Cancel sets the fetcher flag and updates UI immediately — no wait()."""
    from gui.tiktok_browser_panel import TikTokBrowserPanel

    browser = TikTokBrowserPanel()
    fetcher = _StubFetcher()
    browser.url_input.setText("https://www.tiktok.com/@a")
    browser._start_fetcher(fetcher)

    browser._on_cancel_clicked()

    assert fetcher.cancelled is True
    assert not browser.cancel_btn.isEnabled()
    assert browser.status_label.text() == "Cancelling…"
    # Old fetcher still "running" until the worker exits — but UI must not block.
    assert browser._is_fetching is True

    # Worker eventually drains and emits finished_fetch.
    fetcher.simulate_finish(0)
    assert browser._is_fetching is False
    assert browser.progress_bar.isHidden()


def test_context_menu_suppressed_during_fetch(qapp, tmp_path: Path) -> None:
    """Right-click on the saved-channels table is a no-op while fetching —
    prevents stacking a second QThread via Refresh / Download-all-new."""
    from PySide6.QtCore import QPoint
    from gui.tiktok_browser_panel import TikTokBrowserPanel
    from gui.saved_channels_panel import SavedChannelsPanel

    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://www.tiktok.com/@a"))
    browser = TikTokBrowserPanel()
    panel = SavedChannelsPanel(
        platform="tiktok",
        browser_panel=browser,
        store=store,
        store_path=tmp_path / "saved.json",
    )

    # Force fetching state.
    browser._is_fetching = True

    # _on_context_menu must early-return without raising — easiest way to
    # observe the no-op is that no QMenu.exec is invoked (the method returns
    # cleanly even with a row hit).
    panel._on_context_menu(QPoint(0, 0))  # no exception, no menu shown
