"""Tests for gui/about_panel.AboutPanel — pill state derivation + actions."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.about_panel import AboutPanel, _human_delta
from update_checker import ReleaseInfo
from version import __version__, __version_info__


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _stub_main_window(cached=None, last_check=0.0, enabled=True):
    """Lightweight MagicMock-shaped object with the attributes AboutPanel reads."""
    mw = MagicMock()
    mw._latest_release_cache = cached
    mw.config.last_update_check_at = last_check
    mw.config.update_check_enabled = enabled
    return mw


class TestPillState:
    def test_unknown_when_no_main_window(self, qapp):
        panel = AboutPanel(main_window=None)
        # Pill text reflects "never checked".
        assert "Never checked" in panel._pill.text() or "—" in panel._pill.text()

    def test_unknown_when_no_cache_and_no_check(self, qapp):
        mw = _stub_main_window(cached=None, last_check=0.0)
        panel = AboutPanel(main_window=mw)
        assert "Never checked" in panel._pill.text()

    def test_stale_when_no_cache_but_checked_before(self, qapp):
        mw = _stub_main_window(cached=None, last_check=time.time() - 3600)
        panel = AboutPanel(main_window=mw)
        assert "Last checked" in panel._pill.text()

    def test_up_to_date_when_cache_equals_current(self, qapp):
        mw = _stub_main_window(
            cached=ReleaseInfo(
                __version_info__, __version__, "https://x", "", False
            ),
            last_check=time.time(),
        )
        panel = AboutPanel(main_window=mw)
        assert "Up to date" in panel._pill.text()

    def test_available_when_cache_newer(self, qapp):
        bumped = (__version_info__[0] + 1, 0, 0)
        bumped_str = f"{bumped[0]}.0.0"
        mw = _stub_main_window(
            cached=ReleaseInfo(bumped, bumped_str, "https://x", "", False),
            last_check=time.time(),
        )
        panel = AboutPanel(main_window=mw)
        assert bumped_str in panel._pill.text()
        assert "available" in panel._pill.text()


class TestCheckNowButton:
    def test_clicks_call_main_window_manual(self, qapp):
        mw = _stub_main_window()
        panel = AboutPanel(main_window=mw)
        panel._check_now_btn.click()
        mw._on_check_updates_manual.assert_called_once()

    def test_no_main_window_no_crash(self, qapp):
        panel = AboutPanel(main_window=None)
        panel._check_now_btn.click()  # should not raise


class TestPillClick:
    def test_amber_pill_click_opens_dialog(self, qapp):
        bumped = (__version_info__[0] + 1, 0, 0)
        cached = ReleaseInfo(bumped, f"{bumped[0]}.0.0", "https://x", "", False)
        mw = _stub_main_window(cached=cached, last_check=time.time())
        panel = AboutPanel(main_window=mw)
        panel._on_pill_link_activated("open")
        mw._show_update_dialog.assert_called_once_with(cached)

    def test_pill_click_no_cache_does_nothing(self, qapp):
        mw = _stub_main_window(cached=None, last_check=time.time())
        panel = AboutPanel(main_window=mw)
        panel._on_pill_link_activated("open")
        mw._show_update_dialog.assert_not_called()


class TestRefreshSignal:
    def test_update_check_finished_triggers_refresh(self, qapp):
        from PySide6.QtCore import QObject, Signal

        class MWStub(QObject):
            update_check_finished = Signal()

            def __init__(self):
                super().__init__()
                self.config = MagicMock()
                self.config.last_update_check_at = 0.0
                self._latest_release_cache = None

        mw = MWStub()
        panel = AboutPanel(main_window=mw)
        # Toggle cache to "available" then emit — pill should redraw.
        bumped = (__version_info__[0] + 1, 0, 0)
        mw._latest_release_cache = ReleaseInfo(
            bumped, f"{bumped[0]}.0.0", "https://x", "", False
        )
        mw.update_check_finished.emit()
        assert "available" in panel._pill.text()


class TestHumanDelta:
    def test_zero_returns_em_dash(self):
        assert _human_delta(0.0) == "—"

    def test_just_now(self):
        assert _human_delta(time.time() - 5) == "just now"

    def test_minutes_plural(self):
        assert "minute" in _human_delta(time.time() - 300)

    def test_hours(self):
        assert "hour" in _human_delta(time.time() - 7200)

    def test_days(self):
        assert "day" in _human_delta(time.time() - 86400 * 3)
