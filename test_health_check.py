"""Tests for health_check.py + health_signals.py — 6 signals + orchestrator."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from config import AppConfig
from health_check import (
    HealthReport,
    SEVERITY_RANK,
    compute_health,
    dismiss_issue,
    load_health_cache,
    record_fetch_outcome,
    save_health_cache,
)
from history_store import HistoryRecord
from saved_channels_store import SavedChannel, SavedChannelsStore


_FIXED_NOW = datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)


def _iso_days_ago(days: int) -> str:
    return (_FIXED_NOW - timedelta(days=days)).isoformat()


def _ch(url: str, **kwargs) -> SavedChannel:
    return SavedChannel(url=url, **kwargs)


def _store(tt: list[SavedChannel] | None = None, fb: list[SavedChannel] | None = None) -> SavedChannelsStore:
    return SavedChannelsStore(tiktok=list(tt or []), facebook=list(fb or []))


def _cache(tmp_path: Path) -> Path:
    return tmp_path / "health_cache.json"


def _no_yt_dlp(monkeypatch):
    """Stub the yt-dlp import to suppress the version-check signal in unrelated tests."""
    import health_signals

    def _no_op(*args, **kwargs):
        return []

    monkeypatch.setattr(health_signals, "_check_yt_dlp", _no_op)


# ── signal: stale_fetch ───────────────────────────────────────────────────


class TestStaleFetch:
    def test_info_at_14_days(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(20))
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        ids = [i.id for i in report.issues]
        sevs = {i.id: i.severity for i in report.issues}
        assert "stale_fetch:https://www.tiktok.com/@u1" in ids
        assert sevs["stale_fetch:https://www.tiktok.com/@u1"] == "info"

    def test_warn_at_31_days(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(31))
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        sevs = {i.id: i.severity for i in report.issues}
        assert sevs["stale_fetch:https://www.tiktok.com/@u1"] == "warn"

    def test_skip_under_14_days(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(5))
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        assert not any(i.id.startswith("stale_fetch:") for i in report.issues)


# ── signal: auth_wall_likely ──────────────────────────────────────────────


class TestAuthWall:
    def test_warn_when_empty_with_cookies(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch(
            "https://www.tiktok.com/@u1",
            last_fetched_at=_iso_days_ago(2),
            last_fetched_video_ids=[],
        )
        cfg = AppConfig(tiktok_cookies_file=str(tmp_path / "ck.txt"))
        report = compute_health(_store(tt=[ch]), [], cfg,
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        ids = [i.id for i in report.issues]
        assert "auth_wall:https://www.tiktok.com/@u1" in ids

    def test_no_signal_when_results_present(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch(
            "https://www.tiktok.com/@u1",
            last_fetched_at=_iso_days_ago(2),
            last_fetched_video_ids=["v1"],
        )
        cfg = AppConfig(tiktok_cookies_file=str(tmp_path / "ck.txt"))
        report = compute_health(_store(tt=[ch]), [], cfg,
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        assert not any(i.id.startswith("auth_wall:") for i in report.issues)


# ── signal: no_new_downloads ──────────────────────────────────────────────


class TestNoNewDownloads:
    def test_info_when_uploader_quiet_30d(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(2))
        records = [HistoryRecord(video_id="v1", uploader="@u1",
                                 downloaded_at=_iso_days_ago(45))]
        report = compute_health(_store(tt=[ch]), records, AppConfig(),
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        ids = [i.id for i in report.issues]
        assert "no_new_downloads:https://www.tiktok.com/@u1" in ids

    def test_no_signal_when_never_downloaded(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(2))
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        assert not any(i.id.startswith("no_new_downloads:") for i in report.issues)


# ── signal: login_required_marker ─────────────────────────────────────────


class TestLoginRequiredMarker:
    def test_error_when_marker_present(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        path = _cache(tmp_path)
        record_fetch_outcome(path, "https://www.tiktok.com/@u1", "LoginRequired")
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(1))
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=path, now=_FIXED_NOW)
        sevs = {i.id: i.severity for i in report.issues}
        assert sevs.get("login_required:https://www.tiktok.com/@u1") == "error"

    def test_marker_cleared_on_success(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        path = _cache(tmp_path)
        record_fetch_outcome(path, "https://www.tiktok.com/@u1", "LoginRequired")
        record_fetch_outcome(path, "https://www.tiktok.com/@u1", None)
        cache = load_health_cache(path)
        assert "https://www.tiktok.com/@u1" not in cache.get("fetch_outcomes", {})


# ── signal: cookies_old ───────────────────────────────────────────────────


class TestCookiesOld:
    def test_warn_at_60_days(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ck = tmp_path / "tt.txt"
        ck.write_text("netscape", encoding="utf-8")
        old = (_FIXED_NOW - timedelta(days=70)).timestamp()
        os.utime(ck, (old, old))
        cfg = AppConfig(tiktok_cookies_file=str(ck))
        report = compute_health(_store(), [], cfg,
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        ids = {i.id: i.severity for i in report.issues}
        assert ids.get("cookies_old:tiktok_cookies_file") == "warn"

    def test_error_at_121_days(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ck = tmp_path / "tt.txt"
        ck.write_text("netscape", encoding="utf-8")
        old = (_FIXED_NOW - timedelta(days=121)).timestamp()
        os.utime(ck, (old, old))
        cfg = AppConfig(tiktok_cookies_file=str(ck))
        report = compute_health(_store(), [], cfg,
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        ids = {i.id: i.severity for i in report.issues}
        assert ids.get("cookies_old:tiktok_cookies_file") == "error"


# ── signal: yt_dlp_outdated ───────────────────────────────────────────────


class TestYtDlpOutdated:
    def test_uses_cached_version_offline(self, tmp_path, monkeypatch):
        from health_signals import _check_yt_dlp

        # Pre-seed cache with a known-old PyPI version so the signal fires.
        cache = {
            "yt_dlp_pypi_version": "2099.12.31",
            "yt_dlp_checked_at": _FIXED_NOW.isoformat(),
        }
        # Force installed version old via monkeypatching yt_dlp.version.
        import yt_dlp.version
        monkeypatch.setattr(yt_dlp.version, "__version__", "2025.01.01")
        issues = _check_yt_dlp(cache, _FIXED_NOW, online=False, frozen=False)
        assert any(i.id == "yt_dlp_outdated" for i in issues)

    def test_skips_when_versions_match(self, tmp_path, monkeypatch):
        from health_signals import _check_yt_dlp

        import yt_dlp.version
        monkeypatch.setattr(yt_dlp.version, "__version__", "2025.10.21")
        cache = {
            "yt_dlp_pypi_version": "2025.10.21",
            "yt_dlp_checked_at": _FIXED_NOW.isoformat(),
        }
        issues = _check_yt_dlp(cache, _FIXED_NOW, online=False, frozen=False)
        assert not issues

    def test_frozen_branch_emits_releases_url(self, tmp_path, monkeypatch):
        from health_signals import _check_yt_dlp, RELEASES_URL

        import yt_dlp.version
        monkeypatch.setattr(yt_dlp.version, "__version__", "2025.01.01")
        cache = {
            "yt_dlp_pypi_version": "2025.06.15",
            "yt_dlp_checked_at": _FIXED_NOW.isoformat(),
        }
        issues = _check_yt_dlp(cache, _FIXED_NOW, online=False, frozen=True)
        assert issues
        assert issues[0].fix_action_kind == "open_url"
        assert issues[0].fix_action_arg == RELEASES_URL


class TestFacebookChannelDispatch:
    def test_facebook_channel_uses_facebook_cookies(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        ck = tmp_path / "fb.txt"
        ck.write_text("netscape", encoding="utf-8")
        cfg = AppConfig(facebook_cookies_file=str(ck))
        ch = _ch(
            "https://www.facebook.com/somepage",
            last_fetched_at=_iso_days_ago(2),
            last_fetched_video_ids=[],
        )
        report = compute_health(_store(fb=[ch]), [], cfg,
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        # Auth-wall signal should fire; fix arg points at the FB cookies file.
        auth = [i for i in report.issues if i.id.startswith("auth_wall:")]
        assert auth and auth[0].fix_action_arg == str(ck)


# ── orchestrator + cache ──────────────────────────────────────────────────


class TestOrchestrator:
    def test_empty_inputs_returns_empty_report(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        report = compute_health(_store(), [], AppConfig(),
                                cache_path=_cache(tmp_path), now=_FIXED_NOW)
        assert isinstance(report, HealthReport)
        assert report.issues == []
        assert report.computed_at  # iso string

    def test_max_severity_picks_highest(self):
        from health_check import HealthIssue

        report = HealthReport(issues=[
            HealthIssue(id="a", severity="info", title="x"),
            HealthIssue(id="b", severity="error", title="x"),
            HealthIssue(id="c", severity="warn", title="x"),
        ])
        assert report.max_severity() == "error"

    def test_pypi_fetch_caches_24h(self, tmp_path, monkeypatch):
        # Simulate a successful fetch then assert second call is a no-op.
        from health_signals import _check_yt_dlp
        import health_signals
        import yt_dlp.version

        monkeypatch.setattr(yt_dlp.version, "__version__", "2025.01.01")
        calls = {"n": 0}

        def fake_fetch():
            calls["n"] += 1
            return "2099.12.31"

        monkeypatch.setattr(health_signals, "_fetch_pypi_version", fake_fetch)

        cache: dict = {}
        _check_yt_dlp(cache, _FIXED_NOW, online=True, frozen=False)
        assert calls["n"] == 1
        assert cache["yt_dlp_pypi_version"] == "2099.12.31"

        # Within 24h window — no second network call.
        soon = _FIXED_NOW + timedelta(hours=2)
        _check_yt_dlp(cache, soon, online=True, frozen=False)
        assert calls["n"] == 1

        # Past 24h window — fetch again.
        later = _FIXED_NOW + timedelta(hours=25)
        _check_yt_dlp(cache, later, online=True, frozen=False)
        assert calls["n"] == 2


# ── dismissals ────────────────────────────────────────────────────────────


class TestDismissals:
    def test_dismiss_persists_across_loads(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        path = _cache(tmp_path)
        dismiss_issue(path, "stale_fetch:https://www.tiktok.com/@u1")
        cache = load_health_cache(path)
        assert "stale_fetch:https://www.tiktok.com/@u1" in cache.get("dismissed", [])

    def test_dismissed_info_drops_from_report(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        path = _cache(tmp_path)
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(20))
        # Pre-dismiss the issue ID.
        dismiss_issue(path, "stale_fetch:https://www.tiktok.com/@u1")
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=path, now=_FIXED_NOW)
        ids = [i.id for i in report.issues]
        assert "stale_fetch:https://www.tiktok.com/@u1" not in ids

    def test_dismissed_error_still_shows(self, tmp_path, monkeypatch):
        _no_yt_dlp(monkeypatch)
        path = _cache(tmp_path)
        record_fetch_outcome(path, "https://www.tiktok.com/@u1", "LoginRequired")
        dismiss_issue(path, "login_required:https://www.tiktok.com/@u1")
        ch = _ch("https://www.tiktok.com/@u1", last_fetched_at=_iso_days_ago(1))
        report = compute_health(_store(tt=[ch]), [], AppConfig(),
                                cache_path=path, now=_FIXED_NOW)
        ids = [i.id for i in report.issues]
        assert "login_required:https://www.tiktok.com/@u1" in ids


# ── record_fetch_outcome ──────────────────────────────────────────────────


class TestRecordFetchOutcome:
    def test_writes_marker_to_cache(self, tmp_path):
        path = _cache(tmp_path)
        record_fetch_outcome(path, "https://x", "LoginRequired")
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["fetch_outcomes"]["https://x"] == "LoginRequired"

    def test_save_load_roundtrip(self, tmp_path):
        path = _cache(tmp_path)
        save_health_cache(path, {"foo": "bar"})
        cache = load_health_cache(path)
        assert cache["foo"] == "bar"
        assert cache["schema"] == 1


# ── tolerant cache + CLI ──────────────────────────────────────────────────


class TestCacheTolerance:
    def test_malformed_json_returns_empty(self, tmp_path):
        path = _cache(tmp_path)
        path.write_text("{not json", encoding="utf-8")
        assert load_health_cache(path) == {}

    def test_non_dict_returns_empty(self, tmp_path):
        path = _cache(tmp_path)
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert load_health_cache(path) == {}


class TestCli:
    def test_cli_runs_clean_with_empty_state(self, tmp_path, monkeypatch, capsys):
        # Point config + saved-channels at empty tmp paths.
        import config as cfg_mod
        monkeypatch.setattr(cfg_mod, "CONFIG_PATH", tmp_path / "config.json")
        monkeypatch.setattr(cfg_mod, "SAVED_CHANNELS_PATH", tmp_path / "saved.json")
        monkeypatch.setattr(cfg_mod, "HISTORY_PATH", tmp_path / "history.json")

        # Stub yt-dlp + PyPI so CLI doesn't reach the network.
        import health_signals
        monkeypatch.setattr(health_signals, "_check_yt_dlp", lambda *a, **kw: [])

        from health_check import _cli, _default_cache_path

        # Override the lazy default cache path to land in tmp_path.
        monkeypatch.setattr("health_check._default_cache_path",
                            lambda: tmp_path / "health_cache.json")

        rc = _cli()
        assert rc == 0
        captured = capsys.readouterr()
        assert "All good" in captured.out
