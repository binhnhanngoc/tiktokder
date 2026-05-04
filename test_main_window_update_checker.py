"""Tests for the update-checker wiring inside MainWindow.

Exercises the four result branches (None × manual, None × bg, newer × bg
with skip, manual up-to-date) without spawning real workers — we drive
``_on_update_check_done`` directly with synthetic ``ReleaseInfo`` payloads.
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from config import AppConfig
from update_checker import ReleaseInfo


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def main_window(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gui.main_window.SAVED_CHANNELS_PATH", tmp_path / "saved.json")
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr("config.CONFIG_DIR", tmp_path)

    from gui.main_window import MainWindow

    win = MainWindow(AppConfig())
    yield win
    win.close()


def _release(version=(99, 0, 0), version_str="99.0.0"):
    return ReleaseInfo(
        version=version,
        version_str=version_str,
        html_url=f"https://github.com/x/y/releases/tag/v{version_str}",
        body="# Notes",
        is_tag_fallback=False,
    )


class TestBackgroundGate:
    def test_skips_when_disabled(self, main_window, monkeypatch):
        spawned: list[bool] = []
        monkeypatch.setattr(
            main_window, "_spawn_update_worker", lambda is_manual: spawned.append(is_manual)
        )
        main_window.config.update_check_enabled = False
        main_window.config.last_update_check_at = 0.0  # would otherwise fire
        main_window._maybe_check_updates_background()
        assert spawned == []

    def test_skips_when_recently_checked(self, main_window, monkeypatch):
        spawned: list[bool] = []
        monkeypatch.setattr(
            main_window, "_spawn_update_worker", lambda is_manual: spawned.append(is_manual)
        )
        main_window.config.update_check_enabled = True
        main_window.config.last_update_check_at = time.time()
        main_window._maybe_check_updates_background()
        assert spawned == []

    def test_fires_when_enabled_and_stale(self, main_window, monkeypatch):
        spawned: list[bool] = []
        monkeypatch.setattr(
            main_window, "_spawn_update_worker", lambda is_manual: spawned.append(is_manual)
        )
        main_window.config.update_check_enabled = True
        main_window.config.last_update_check_at = 0.0
        main_window._maybe_check_updates_background()
        assert spawned == [False]


class TestResultHandlerNetFailure:
    def test_background_silent_on_none(self, main_window, monkeypatch):
        shown: list = []
        monkeypatch.setattr(
            "gui.main_window.QMessageBox.warning",
            lambda *a, **kw: shown.append(("warning", a, kw)),
        )
        monkeypatch.setattr(
            "gui.main_window.QMessageBox.information",
            lambda *a, **kw: shown.append(("info", a, kw)),
        )
        emitted: list[bool] = []
        main_window.update_check_finished.connect(lambda: emitted.append(True))

        main_window._on_update_check_done(None, is_manual=False)

        assert shown == []
        assert emitted == [True]
        # Cooldown timestamp written
        assert main_window.config.last_update_check_at > 0

    def test_manual_warns_on_none(self, main_window, monkeypatch):
        shown: list = []
        monkeypatch.setattr(
            "gui.main_window.QMessageBox.warning",
            lambda *a, **kw: shown.append(("warning", a, kw)),
        )
        main_window._on_update_check_done(None, is_manual=True)
        assert len(shown) == 1
        assert shown[0][0] == "warning"


class TestResultHandlerSkipVersion:
    def test_background_skips_skipped_version(self, main_window, monkeypatch):
        shown_dialog: list = []
        monkeypatch.setattr(
            main_window, "_show_update_dialog", lambda r: shown_dialog.append(r)
        )
        main_window.config.skipped_update_version = "99.0.0"

        main_window._on_update_check_done(_release(), is_manual=False)
        assert shown_dialog == []

    def test_manual_does_not_respect_skip(self, main_window, monkeypatch):
        shown_dialog: list = []
        monkeypatch.setattr(
            main_window, "_show_update_dialog", lambda r: shown_dialog.append(r)
        )
        main_window.config.skipped_update_version = "99.0.0"

        main_window._on_update_check_done(_release(), is_manual=True)
        assert len(shown_dialog) == 1


class TestResultHandlerUpToDate:
    def test_background_silent_when_equal(self, main_window, monkeypatch):
        shown: list = []
        monkeypatch.setattr(
            "gui.main_window.QMessageBox.information",
            lambda *a, **kw: shown.append(("info", a, kw)),
        )
        from version import __version__, __version_info__

        same = ReleaseInfo(
            version=__version_info__,
            version_str=__version__,
            html_url="https://x",
            body="",
            is_tag_fallback=False,
        )
        main_window._on_update_check_done(same, is_manual=False)
        assert shown == []

    def test_manual_shows_up_to_date_dialog(self, main_window, monkeypatch):
        shown: list = []
        monkeypatch.setattr(
            "gui.main_window.QMessageBox.information",
            lambda *a, **kw: shown.append(("info", a, kw)),
        )
        from version import __version__, __version_info__

        same = ReleaseInfo(
            version=__version_info__,
            version_str=__version__,
            html_url="https://x",
            body="",
            is_tag_fallback=False,
        )
        main_window._on_update_check_done(same, is_manual=True)
        assert len(shown) == 1


class TestSkipVersionPersists:
    def test_skip_writes_config(self, main_window):
        main_window._on_skip_version("1.10.1")
        assert main_window.config.skipped_update_version == "1.10.1"


class TestUpdateMenuAction:
    def test_menu_has_check_for_updates(self, main_window):
        help_menu = next(
            m
            for m in main_window.menuBar().findChildren(
                type(main_window.menuBar().addMenu("_t"))
            )
            if m.title() == "&Help"
        )
        labels = [a.text().replace("&", "") for a in help_menu.actions() if not a.isSeparator()]
        joined = " | ".join(labels)
        assert "Check for Updates" in joined
