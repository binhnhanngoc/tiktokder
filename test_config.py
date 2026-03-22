"""Tests for config.py - settings and history persistence."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from config import AppConfig, load_config, save_config, load_history, save_history


class TestAppConfig:
    """Test AppConfig dataclass defaults."""

    def test_default_values(self):
        c = AppConfig()
        assert c.output_dir == "./downloads"
        assert c.workers == 3
        assert c.delay == 0.5
        assert c.cookie_browser is None
        assert c.window_width == 900
        assert c.window_height == 600

    def test_custom_values(self):
        c = AppConfig(output_dir="/tmp", workers=5, delay=2.0, cookie_browser="chrome")
        assert c.output_dir == "/tmp"
        assert c.workers == 5
        assert c.cookie_browser == "chrome"


class TestLoadSaveConfig:
    """Test config file load/save roundtrip."""

    def test_save_and_load_roundtrip(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_dir = tmp_path
        original = AppConfig(output_dir="/custom", workers=7, delay=0.5)

        with patch("config.CONFIG_PATH", config_path), patch("config.CONFIG_DIR", config_dir):
            save_config(original)
            loaded = load_config()

        assert loaded.output_dir == "/custom"
        assert loaded.workers == 7
        assert loaded.delay == 0.5

    def test_load_missing_file_returns_defaults(self, tmp_path):
        config_path = tmp_path / "nonexistent.json"
        with patch("config.CONFIG_PATH", config_path):
            c = load_config()
        assert c.output_dir == "./downloads"
        assert c.workers == 3

    def test_load_invalid_json_returns_defaults(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json{{{", encoding="utf-8")
        with patch("config.CONFIG_PATH", config_path):
            c = load_config()
        assert c.workers == 3

    def test_load_ignores_unknown_keys(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"output_dir": "/x", "workers": 2, "unknown_key": "ignored"}),
            encoding="utf-8",
        )
        with patch("config.CONFIG_PATH", config_path):
            c = load_config()
        assert c.output_dir == "/x"
        assert c.workers == 2


class TestHistory:
    """Test download history persistence."""

    def test_save_and_load_history(self, tmp_path):
        history_path = tmp_path / "history.json"
        history_dir = tmp_path
        ids = {"123456789012345", "987654321098765"}

        with patch("config.HISTORY_PATH", history_path), patch("config.CONFIG_DIR", history_dir):
            save_history(ids)
            loaded = load_history()

        assert loaded == ids

    def test_load_missing_history_returns_empty(self, tmp_path):
        history_path = tmp_path / "nonexistent.json"
        with patch("config.HISTORY_PATH", history_path):
            h = load_history()
        assert h == set()

    def test_load_invalid_history_returns_empty(self, tmp_path):
        history_path = tmp_path / "history.json"
        history_path.write_text("invalid json", encoding="utf-8")
        with patch("config.HISTORY_PATH", history_path):
            h = load_history()
        assert h == set()

    def test_history_persists_sorted(self, tmp_path):
        history_path = tmp_path / "history.json"
        history_dir = tmp_path
        ids = {"c_id", "a_id", "b_id"}

        with patch("config.HISTORY_PATH", history_path), patch("config.CONFIG_DIR", history_dir):
            save_history(ids)

        data = json.loads(history_path.read_text(encoding="utf-8"))
        assert data == ["a_id", "b_id", "c_id"]

    def test_empty_history(self, tmp_path):
        history_path = tmp_path / "history.json"
        history_dir = tmp_path

        with patch("config.HISTORY_PATH", history_path), patch("config.CONFIG_DIR", history_dir):
            save_history(set())
            loaded = load_history()

        assert loaded == set()
