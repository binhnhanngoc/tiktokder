"""Tests for LibraryPreviewPane in-app player.

Headless / mock-based — never opens a real video file. Real-media validation
is the manual smoke per phase-05-tests.md (cannot be exercised in CI).

We mock ``QMediaPlayer`` for the position-debounce, resume-bounds and
keyboard tests because Qt's media stack needs an OS event loop that won't
behave consistently across CI. Stack-flip and codec-error tests use a real
``LibraryPreviewPane`` constructed offscreen — the player is real but we
don't actually load media.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from history_store import HistoryRecord, save_history_records


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def placeholder():
    pix = QPixmap(360, 200)
    pix.fill(Qt.GlobalColor.darkGray)
    return pix


@pytest.fixture
def history_path(tmp_path, monkeypatch):
    """Redirect HISTORY_PATH to tmp dir for the player's persistence calls."""
    path = tmp_path / "history.json"
    monkeypatch.setattr("gui.library_preview_pane.HISTORY_PATH", path)
    return path


def _make_record(video_id: str = "vid1", file_path: str | None = None, **kwargs) -> HistoryRecord:
    return HistoryRecord(
        video_id=video_id,
        title="t",
        file_path=file_path,
        **kwargs,
    )


class TestStackFlip:
    """Phase 2 — thumbnail ↔ player page transitions."""

    def test_initial_state_shows_thumbnail(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        assert pane.stack.currentWidget() is pane._thumb_page

    def test_stop_returns_to_thumbnail(self, qapp, placeholder, history_path, tmp_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        # Force the stack to player page so we can verify stop_and_show_thumb
        # flips it back without needing a real media file.
        pane.stack.setCurrentWidget(pane._player_page)
        pane.stop_and_show_thumb()
        assert pane.stack.currentWidget() is pane._thumb_page

    def test_play_with_missing_file_does_not_flip(self, qapp, placeholder, history_path, tmp_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        rec = _make_record(file_path=str(tmp_path / "does_not_exist.mp4"))
        with patch("gui.library_preview_pane.open_path") as fake_open:
            pane.play(rec)
            fake_open.assert_called_once()
        # Player page should NOT be active for a missing file.
        assert pane.stack.currentWidget() is pane._thumb_page


class TestCodecFallback:
    """Phase 3 — errorOccurred → fallback panel."""

    def test_error_swaps_video_for_fallback_panel(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        # Pretend a record is playing — required for _open_externally to
        # know which file to delegate.
        pane._playing_record = _make_record(file_path="/tmp/x.mp4")
        pane._video_stack.setCurrentWidget(pane._video_widget)

        pane._on_error_occurred(QMediaPlayer.Error.ResourceError, "test")
        assert pane._video_stack.currentWidget() is pane._fallback_panel

    def test_fallback_button_calls_open_path(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        rec = _make_record(file_path="/tmp/x.mp4")
        pane._playing_record = rec
        with patch("gui.library_preview_pane.open_path") as fake_open:
            pane._fallback_btn.click()
            fake_open.assert_called_once_with("/tmp/x.mp4")


class TestResumeBounds:
    """Phase 3 — resume only inside (5s, duration-5s)."""

    @pytest.mark.parametrize(
        "saved_pos, duration_ms, should_seek",
        [
            (3.0, 60_000, False),    # below 5s guard
            (30.0, 60_000, True),    # mid range
            (58.0, 60_000, False),   # above duration-5
            (5.0, 60_000, False),    # boundary excluded
            (55.0, 60_000, False),   # boundary excluded
            (10.0, 8_000, False),    # duration too short
        ],
    )
    def test_resume_seek_only_inside_bounds(
        self, qapp, placeholder, history_path, saved_pos, duration_ms, should_seek,
    ):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._pending_resume_seconds = saved_pos
        # Stub the player's duration() and capture setPosition calls.
        pane.player.duration = MagicMock(return_value=duration_ms)
        pane.player.setPosition = MagicMock()

        pane._on_media_status_changed(QMediaPlayer.MediaStatus.LoadedMedia)

        if should_seek:
            pane.player.setPosition.assert_called_once_with(int(saved_pos * 1000))
        else:
            pane.player.setPosition.assert_not_called()
        # _pending_resume_seconds always cleared after LoadedMedia.
        assert pane._pending_resume_seconds is None


class TestPositionPersist:
    """Phase 3 — debounced disk writes for play_position_seconds."""

    def test_position_changes_restart_persist_timer(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = _make_record(file_path="/tmp/x.mp4")
        # Each tick should reset (i.e. start) the timer; we don't actually
        # need to wait 5s — just verify the timer is active after a tick.
        pane._on_position_changed(1000)
        assert pane._position_persist_timer.isActive()

    def test_persist_writes_to_history(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        # Seed a real history file so update_history_record_fields finds the row.
        save_history_records(history_path, [_make_record("v1", file_path="/tmp/v1.mp4")])

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = _make_record("v1", file_path="/tmp/v1.mp4")
        pane.player.position = MagicMock(return_value=12_500)  # 12.5 s

        pane._persist_position()

        data = json.loads(history_path.read_text(encoding="utf-8"))
        entry = data["entries"][0]
        assert entry["play_position_seconds"] == 12.5
        assert entry["last_played_at"] is not None

    def test_persist_no_op_when_nothing_playing(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = None
        # Should not raise even if HISTORY_PATH doesn't exist.
        pane._persist_position()
        assert not history_path.exists()

    def test_debounce_only_one_write_per_window(self, qapp, placeholder, history_path):
        """Real timer test: many positionChanged ticks → exactly 1 disk write within the debounce window."""
        from gui.library_preview_pane import LibraryPreviewPane

        save_history_records(history_path, [_make_record("v1", file_path="/tmp/v1.mp4")])

        pane = LibraryPreviewPane(placeholder)
        # Shrink debounce so the test runs in <1s rather than 5s.
        pane._position_persist_timer.setInterval(150)
        pane._playing_record = _make_record("v1", file_path="/tmp/v1.mp4")
        pane.player.position = MagicMock(return_value=1000)

        # 10 fast ticks within 250 ms — debounce should collapse to one fire.
        write_count = {"n": 0}
        original = pane._persist_position

        def counting_persist():
            write_count["n"] += 1
            original()

        pane._persist_position = counting_persist
        # Re-wire the timer to the new wrapper.
        pane._position_persist_timer.timeout.disconnect()
        pane._position_persist_timer.timeout.connect(counting_persist)

        for _ in range(10):
            pane._on_position_changed(1000)
            QTest.qWait(20)
        # Wait for debounce trailing edge.
        QTest.qWait(300)
        assert write_count["n"] == 1


class TestKeyboardSeek:
    """Phase 3 — J/K/L/space/arrows seek correctly."""

    def test_seek_relative_clamps_to_zero(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = _make_record(file_path="/tmp/x.mp4")
        pane.player.position = MagicMock(return_value=2000)
        pane.player.duration = MagicMock(return_value=60_000)
        pane.player.setPosition = MagicMock()

        pane._seek_relative(-10_000)
        pane.player.setPosition.assert_called_once_with(0)

    def test_seek_relative_clamps_to_duration(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = _make_record(file_path="/tmp/x.mp4")
        pane.player.position = MagicMock(return_value=58_000)
        pane.player.duration = MagicMock(return_value=60_000)
        pane.player.setPosition = MagicMock()

        pane._seek_relative(+10_000)
        pane.player.setPosition.assert_called_once_with(60_000)

    def test_seek_relative_no_op_when_nothing_playing(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = None
        pane.player.setPosition = MagicMock()
        pane._seek_relative(+5000)
        pane.player.setPosition.assert_not_called()

    def test_toggle_play_pauses_when_playing(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane.player.playbackState = MagicMock(
            return_value=QMediaPlayer.PlaybackState.PlayingState
        )
        pane.player.pause = MagicMock()
        pane.player.play = MagicMock()
        pane._toggle_play()
        pane.player.pause.assert_called_once()
        pane.player.play.assert_not_called()

    def test_toggle_play_plays_when_paused(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane.player.playbackState = MagicMock(
            return_value=QMediaPlayer.PlaybackState.PausedState
        )
        pane.player.pause = MagicMock()
        pane.player.play = MagicMock()
        pane._toggle_play()
        pane.player.play.assert_called_once()
        pane.player.pause.assert_not_called()


class TestSetRecord:
    """Phase 2 — record-switch behavior across single/double-click flows."""

    def test_set_record_to_different_record_stops_playback(
        self, qapp, placeholder, history_path,
    ):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = _make_record("v1", file_path="/tmp/v1.mp4")
        pane.player.stop = MagicMock()
        pane.player.setSource = MagicMock()

        pane.set_record(_make_record("v2", file_path="/tmp/v2.mp4"))

        pane.player.stop.assert_called()
        # After stop_and_show_thumb, _playing_record cleared.
        assert pane._playing_record is None
        assert pane.stack.currentWidget() is pane._thumb_page

    def test_set_record_same_video_does_not_stop(self, qapp, placeholder, history_path):
        from gui.library_preview_pane import LibraryPreviewPane

        pane = LibraryPreviewPane(placeholder)
        pane._playing_record = _make_record("v1", file_path="/tmp/v1.mp4")
        pane.player.stop = MagicMock()

        pane.set_record(_make_record("v1", file_path="/tmp/v1.mp4"))

        pane.player.stop.assert_not_called()
        assert pane._playing_record is not None
