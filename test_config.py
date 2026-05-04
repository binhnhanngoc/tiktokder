"""Tests for config.py - settings and history persistence."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from config import (
    AppConfig,
    FB_LOGIN_WALL_MARKERS,
    FACEBOOK_DEFAULTS,
    MAX_RETRY_ATTEMPTS_FACEBOOK,
    MAX_RETRY_ATTEMPTS_TIKTOK,
    PlatformDefaults,
    TIKTOK_DEFAULTS,
    get_max_retry_attempts,
    get_platform_defaults,
    load_config,
    save_config,
    load_history,
    save_history,
)


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


class TestCookiesFileMigration:
    """Legacy `cookies_file` key migrates to `facebook_cookies_file` on load,
    and only the new keys are emitted on save.
    """

    def test_legacy_key_migrates_to_facebook_cookies_file(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"cookies_file": "/path/a.txt"}),
            encoding="utf-8",
        )
        with patch("config.CONFIG_PATH", config_path):
            c = load_config()
        assert c.facebook_cookies_file == "/path/a.txt"
        assert c.tiktok_cookies_file is None

    def test_new_key_wins_when_both_present(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {"cookies_file": "/old.txt", "facebook_cookies_file": "/new.txt"}
            ),
            encoding="utf-8",
        )
        with patch("config.CONFIG_PATH", config_path):
            c = load_config()
        assert c.facebook_cookies_file == "/new.txt"

    def test_save_emits_only_new_keys(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = AppConfig(
            facebook_cookies_file="/fb.txt",
            tiktok_cookies_file="/tt.txt",
        )
        with patch("config.CONFIG_PATH", config_path), patch("config.CONFIG_DIR", tmp_path):
            save_config(cfg)
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        assert "cookies_file" not in raw
        assert raw["facebook_cookies_file"] == "/fb.txt"
        assert raw["tiktok_cookies_file"] == "/tt.txt"


class TestBrowseDownloadedFilter:
    """AppConfig persists per-platform Downloaded combo state across launches."""

    def test_default_is_all_for_both_platforms(self):
        c = AppConfig()
        assert c.tiktok_browse_downloaded_filter == "all"
        assert c.facebook_browse_downloaded_filter == "all"

    def test_save_and_load_roundtrip(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = AppConfig(
            tiktok_browse_downloaded_filter="new",
            facebook_browse_downloaded_filter="downloaded",
        )
        with patch("config.CONFIG_PATH", config_path), patch("config.CONFIG_DIR", tmp_path):
            save_config(cfg)
            loaded = load_config()
        assert loaded.tiktok_browse_downloaded_filter == "new"
        assert loaded.facebook_browse_downloaded_filter == "downloaded"


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
        """save_history writes the latest schema with bare records, ordered by id."""
        from history_store import SCHEMA_VERSION

        history_path = tmp_path / "history.json"
        history_dir = tmp_path
        ids = {"c_id", "a_id", "b_id"}

        with patch("config.HISTORY_PATH", history_path), patch("config.CONFIG_DIR", history_dir):
            save_history(ids)

        data = json.loads(history_path.read_text(encoding="utf-8"))
        assert data["schema"] == SCHEMA_VERSION
        ordered = [entry["video_id"] for entry in data["entries"]]
        assert ordered == ["a_id", "b_id", "c_id"]

    def test_empty_history(self, tmp_path):
        history_path = tmp_path / "history.json"
        history_dir = tmp_path

        with patch("config.HISTORY_PATH", history_path), patch("config.CONFIG_DIR", history_dir):
            save_history(set())
            loaded = load_history()

        assert loaded == set()


class TestPlatformDefaults:
    """Per-platform pacing/retry presets."""

    def test_tiktok_default_values(self):
        assert TIKTOK_DEFAULTS.delay_mean == 1.5
        assert TIKTOK_DEFAULTS.delay_std == 0.5
        assert TIKTOK_DEFAULTS.delay_floor == 0.2
        assert TIKTOK_DEFAULTS.workers == 3
        assert TIKTOK_DEFAULTS.retries == 10

    def test_facebook_default_values(self):
        assert FACEBOOK_DEFAULTS.delay_mean == 3.0
        assert FACEBOOK_DEFAULTS.delay_std == 1.5
        assert FACEBOOK_DEFAULTS.delay_floor == 0.5
        assert FACEBOOK_DEFAULTS.workers == 1
        assert FACEBOOK_DEFAULTS.retries == 2

    def test_platform_defaults_is_dataclass(self):
        # Must support equality and immutability.
        a = PlatformDefaults(1.0, 0.1, 0.05, 2, 5)
        b = PlatformDefaults(1.0, 0.1, 0.05, 2, 5)
        assert a == b


class TestGetPlatformDefaults:
    def test_tiktok_url(self):
        d = get_platform_defaults("https://www.tiktok.com/@u/video/123")
        assert d == TIKTOK_DEFAULTS

    def test_facebook_url(self):
        d = get_platform_defaults("https://www.facebook.com/x/videos/1")
        assert d == FACEBOOK_DEFAULTS

    def test_fb_watch_shortlink(self):
        d = get_platform_defaults("https://fb.watch/abc/")
        assert d == FACEBOOK_DEFAULTS

    def test_unknown_url_falls_back_to_tiktok(self):
        d = get_platform_defaults("https://example.com/whatever")
        assert d == TIKTOK_DEFAULTS


class TestMaxRetryAttempts:
    def test_facebook_url(self):
        assert get_max_retry_attempts("https://www.facebook.com/x/videos/1") == MAX_RETRY_ATTEMPTS_FACEBOOK

    def test_tiktok_url(self):
        assert get_max_retry_attempts("https://www.tiktok.com/@u/video/1") == MAX_RETRY_ATTEMPTS_TIKTOK

    def test_unknown_url_uses_tiktok_budget(self):
        assert get_max_retry_attempts("https://example.com") == MAX_RETRY_ATTEMPTS_TIKTOK


class TestFbLoginWallMarkers:
    def test_markers_are_a_tuple(self):
        assert isinstance(FB_LOGIN_WALL_MARKERS, tuple)

    def test_markers_not_empty(self):
        assert len(FB_LOGIN_WALL_MARKERS) > 0

    def test_markers_no_false_positive_on_benign_html(self):
        benign = "<html><body><h1>My homepage</h1><p>Hello world</p></body></html>"
        assert not any(m in benign for m in FB_LOGIN_WALL_MARKERS)

    def test_markers_match_login_form(self):
        login_html = '<html><form id="login_form">…</form></html>'
        assert any(m in login_html for m in FB_LOGIN_WALL_MARKERS)
