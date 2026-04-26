"""Tests for SettingsPanel split + facebook_max_scrolls_default propagation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QGroupBox

from config import AppConfig


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_settings_panel_has_three_groupboxes(qapp, tmp_path, monkeypatch) -> None:
    """Layout should expose Global / TikTok / Facebook QGroupBoxes."""
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")

    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    titles = sorted(g.title() for g in panel.findChildren(QGroupBox))
    assert titles == ["Facebook", "Global", "TikTok"]


def test_settings_panel_save_emits_settings_changed(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")

    from gui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppConfig())
    captured: list[bool] = []
    panel.settings_changed.connect(lambda: captured.append(True))

    panel.cookies_file_input.setText("/path/to/cookies.txt")
    # textChanged is wired to _save → emits settings_changed.
    assert captured  # at least once


def test_settings_panel_persists_fb_scrolls_default(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")

    from gui.settings_panel import SettingsPanel

    config = AppConfig()
    panel = SettingsPanel(config)
    panel.fb_scrolls_default_spin.setValue(25)
    # _save runs on valueChanged.

    raw = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert raw["facebook_max_scrolls_default"] == 25


def test_app_config_fb_scrolls_default_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.CONFIG_PATH", tmp_path / "config.json")

    from config import load_config, save_config

    cfg = AppConfig(facebook_max_scrolls_default=30)
    save_config(cfg)
    loaded = load_config()
    assert loaded.facebook_max_scrolls_default == 30


def test_facebook_panel_uses_default_scrolls(qapp) -> None:
    """`FacebookBrowserPanel(default_scrolls=N)` sets the spin to N."""
    from gui.facebook_browser_panel import FacebookBrowserPanel

    panel = FacebookBrowserPanel(default_scrolls=15)
    assert panel.scrolls_spin.value() == 15


def test_main_window_propagates_fb_scrolls_from_config(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.main_window.SAVED_CHANNELS_PATH", tmp_path / "saved.json")

    from gui.main_window import MainWindow

    cfg = AppConfig(facebook_max_scrolls_default=22)
    win = MainWindow(cfg)
    assert win._facebook_browser.scrolls_spin.value() == 22
