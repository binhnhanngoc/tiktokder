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

    captured: list[list[str]] = []
    panel.download_requested.connect(captured.append)

    ch = store.find_by_url("tiktok", "https://www.tiktok.com/@a")
    panel._download_all_new(ch)

    assert captured == [["https://x/v/new1"]]
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
