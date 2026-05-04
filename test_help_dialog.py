"""Tests for HelpDialog and Help-menu wiring in MainWindow."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTextBrowser

from config import AppConfig
from gui.help_content import (
    TAB_ABOUT,
    TAB_COOKIES_CONFIGURE,
    TAB_COOKIES_EXPORT,
    TAB_GETTING_STARTED,
    TAB_SHORTCUTS,
    TAB_TROUBLESHOOTING,
    help_tabs,
)
from gui.help_dialog import HelpDialog


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_help_tabs_definitions_have_unique_ids_and_non_empty_html() -> None:
    """Every tab needs a stable id, a label, and renderable HTML body."""
    tabs = help_tabs()
    assert len(tabs) >= 5
    ids = [tab_id for tab_id, _label, _html in tabs]
    assert len(ids) == len(set(ids)), "tab ids must be unique"
    for tab_id, label, html in tabs:
        assert tab_id, "tab id must be non-empty"
        assert label, f"tab {tab_id!r} missing label"
        assert "<" in html and ">" in html, f"tab {tab_id!r} missing HTML markup"
        assert len(html.strip()) > 80, f"tab {tab_id!r} body suspiciously short"


def test_help_dialog_instantiates_with_all_tabs(qapp) -> None:
    dlg = HelpDialog()
    assert dlg.tabs.count() == len(help_tabs())
    # Each tab is a QTextBrowser (the dialog promises HTML rendering).
    for i in range(dlg.tabs.count()):
        assert isinstance(dlg.tabs.widget(i), QTextBrowser)


@pytest.mark.parametrize(
    "tab_id",
    [
        TAB_GETTING_STARTED,
        TAB_COOKIES_EXPORT,
        TAB_COOKIES_CONFIGURE,
        TAB_TROUBLESHOOTING,
        TAB_SHORTCUTS,
        TAB_ABOUT,
    ],
)
def test_open_at_tab_navigates_to_known_id(qapp, tab_id: str) -> None:
    dlg = HelpDialog()
    dlg.open_at_tab(tab_id)
    expected_idx = dlg._tab_index_by_id[tab_id]
    assert dlg.tabs.currentIndex() == expected_idx
    assert dlg.isVisible()


def test_open_at_tab_unknown_id_falls_back_to_first(qapp) -> None:
    dlg = HelpDialog()
    dlg.open_at_tab("does-not-exist")
    assert dlg.tabs.currentIndex() == 0


def test_help_dialog_is_non_modal(qapp) -> None:
    """Users must be able to interact with main window while help is open."""
    dlg = HelpDialog()
    assert dlg.isModal() is False


def test_main_window_help_menu_lists_expected_actions(qapp, tmp_path, monkeypatch) -> None:
    """Help menu must surface manual + cookie guides + shortcuts + about."""
    monkeypatch.setattr("gui.main_window.SAVED_CHANNELS_PATH", tmp_path / "saved.json")

    from gui.main_window import MainWindow

    win = MainWindow(AppConfig())
    help_menu = next(
        (m for m in win.menuBar().findChildren(type(win.menuBar().addMenu("_t"))) if m.title() == "&Help"),
        None,
    )
    assert help_menu is not None, "Help menu should exist"
    labels = [a.text() for a in help_menu.actions() if not a.isSeparator()]
    # Ampersand-stripped check — Qt keeps the & in text() but adjacent to mnemonic char.
    joined = " | ".join(labels).replace("&", "")
    for needle in (
        "User Manual",
        "Export Cookies",
        "Configure Cookies",
        "Troubleshooting",
        "Keyboard Shortcuts",
        "About",
    ):
        assert needle in joined, f"Help menu missing entry: {needle!r}"


def test_main_window_user_manual_has_f1_shortcut(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.main_window.SAVED_CHANNELS_PATH", tmp_path / "saved.json")

    from gui.main_window import MainWindow

    win = MainWindow(AppConfig())
    help_menu = next(m for m in win.menuBar().findChildren(type(win.menuBar().addMenu("_t"))) if m.title() == "&Help")
    manual = next(a for a in help_menu.actions() if "Manual" in a.text())
    assert manual.shortcut().toString() == "F1"
