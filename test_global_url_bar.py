"""Tests for GlobalUrlBar + StatusBarWidget."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── GlobalUrlBar ──────────────────────────────────────────────────────────

def test_global_url_bar_emits_on_enter(qapp) -> None:
    from gui.global_url_bar import GlobalUrlBar

    bar = GlobalUrlBar()
    captured: list[list[str]] = []
    bar.urls_submitted.connect(captured.append)

    bar.url_input.setText("https://www.tiktok.com/@a/video/123")
    bar._on_submit()

    assert captured == [["https://www.tiktok.com/@a/video/123"]]
    # Input cleared after successful submit.
    assert bar.url_input.text() == ""


def test_global_url_bar_drops_invalid_lines(qapp) -> None:
    from gui.global_url_bar import GlobalUrlBar

    bar = GlobalUrlBar()
    captured: list[list[str]] = []
    bar.urls_submitted.connect(captured.append)

    # Mixed valid + garbage; only the valid TT URL survives.
    bar.url_input.setText(
        "https://www.tiktok.com/@a/video/1 not-a-url https://www.facebook.com/page/videos/2"
    )
    bar._on_submit()

    assert len(captured) == 1
    assert captured[0] == [
        "https://www.tiktok.com/@a/video/1",
        "https://www.facebook.com/page/videos/2",
    ]


def test_global_url_bar_drop_text_mixed_platforms(qapp) -> None:
    from gui.global_url_bar import GlobalUrlBar

    bar = GlobalUrlBar()
    captured: list[list[str]] = []
    bar.urls_submitted.connect(captured.append)

    mime = QMimeData()
    mime.setText(
        "https://www.tiktok.com/@x/video/1\n"
        "https://www.tiktok.com/@y/video/2\n"
        "https://www.facebook.com/p/videos/3\n"
        "https://www.facebook.com/q/videos/4\n"
        "https://www.facebook.com/r/videos/5\n"
    )
    event = QDropEvent(QPointF(0, 0), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    bar.dropEvent(event)

    assert captured == [[
        "https://www.tiktok.com/@x/video/1",
        "https://www.tiktok.com/@y/video/2",
        "https://www.facebook.com/p/videos/3",
        "https://www.facebook.com/q/videos/4",
        "https://www.facebook.com/r/videos/5",
    ]]


def test_global_url_bar_drop_txt_file(qapp, tmp_path: Path) -> None:
    from gui.global_url_bar import GlobalUrlBar

    txt = tmp_path / "batch.txt"
    txt.write_text(
        "https://www.tiktok.com/@a/video/1\n"
        "# comment line\n"
        "https://www.facebook.com/x/videos/2\n",
        encoding="utf-8",
    )

    bar = GlobalUrlBar()
    captured: list[list[str]] = []
    bar.urls_submitted.connect(captured.append)

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(txt))])
    event = QDropEvent(QPointF(0, 0), Qt.DropAction.CopyAction, mime,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    bar.dropEvent(event)

    assert captured == [[
        "https://www.tiktok.com/@a/video/1",
        "https://www.facebook.com/x/videos/2",
    ]]


# ── StatusBarWidget ──────────────────────────────────────────────────────

def test_status_bar_widget_set_counts(qapp) -> None:
    from gui.status_bar_widget import StatusBarWidget

    sw = StatusBarWidget()
    sw.set_counts(2, 3, 7, "Ready")

    assert sw.tiktok_label.text() == "TT: 2"
    assert sw.facebook_label.text() == "FB: 3"
    assert sw.done_label.text() == "Done: 7"
    assert sw.status_label.text() == "Ready"


def test_status_bar_widget_status_text_optional(qapp) -> None:
    from gui.status_bar_widget import StatusBarWidget

    sw = StatusBarWidget()
    sw.set_counts(0, 0, 0, "Old text")
    sw.set_counts(1, 1, 1)  # no status_text override

    # Status text preserved across set_counts when not provided.
    assert sw.status_label.text() == "Old text"


# ── MainWindow integration ────────────────────────────────────────────────

def test_main_window_routes_mixed_submission(qapp, tmp_path, monkeypatch) -> None:
    """Mixed batch from URL bar splits into both platform queues."""
    from config import AppConfig

    monkeypatch.setattr("gui.main_window.SAVED_CHANNELS_PATH", tmp_path / "saved.json")

    from gui.main_window import MainWindow

    win = MainWindow(AppConfig())
    # Replace engine.add_urls with a no-op — we only want to verify table+status math.
    win.engine.add_urls = lambda urls, force=False: None

    win._on_urls_submitted([
        "https://www.tiktok.com/@x/video/1",
        "https://www.tiktok.com/@y/video/2",
        "https://www.facebook.com/p/videos/3",
    ])

    # Two TikTok rows + one Facebook row.
    assert win.tiktok_tab.queue_panel.get_total_count() == 2
    assert win.facebook_tab.queue_panel.get_total_count() == 1
    # Status bar reflects per-platform pending.
    assert win.status_widget.tiktok_label.text() == "TT: 2"
    assert win.status_widget.facebook_label.text() == "FB: 1"
