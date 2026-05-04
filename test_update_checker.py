"""Tests for update_checker.py — pure-logic stdlib release-fetch module.

Mocks ``urllib.request.urlopen`` exclusively; never hits the network. Each
case maps to a branch documented in the phase-01 plan.
"""

from __future__ import annotations

import io
import json
import socket
import time
import urllib.error
from contextlib import contextmanager
from unittest.mock import patch

import pytest

import update_checker
from update_checker import (
    ReleaseInfo,
    is_newer,
    latest_release,
    should_check_now,
)


# ── helpers ──────────────────────────────────────────────────────────────


class _FakeResponse:
    """Minimal context-manager standin for urllib's HTTP response."""

    def __init__(self, payload: bytes) -> None:
        self._buf = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self) -> bytes:
        return self._buf.read()


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.test", code=code, msg="x", hdrs=None, fp=None  # type: ignore[arg-type]
    )


@contextmanager
def _patch_urlopen(side_effect):
    """Patch ``urllib.request.urlopen`` with a callable side effect."""
    with patch("update_checker.urllib.request.urlopen", side_effect=side_effect) as p:
        yield p


# ── ReleaseInfo dataclass ────────────────────────────────────────────────


class TestReleaseInfo:
    def test_frozen(self) -> None:
        r = ReleaseInfo((1, 0, 0), "1.0.0", "u", "b", False)
        with pytest.raises(Exception):
            r.version = (2, 0, 0)  # type: ignore[misc]

    def test_field_order(self) -> None:
        r = ReleaseInfo((1, 2, 3), "1.2.3", "https://x", "notes", False)
        assert r.version == (1, 2, 3)
        assert r.version_str == "1.2.3"
        assert r.html_url == "https://x"
        assert r.body == "notes"
        assert r.is_tag_fallback is False


# ── is_newer ─────────────────────────────────────────────────────────────


class TestIsNewer:
    @pytest.mark.parametrize(
        "latest,current,expected",
        [
            ((1, 10, 0), (1, 9, 0), True),
            ((2, 0, 0), (1, 999, 999), True),
            ((1, 9, 1), (1, 9, 0), True),
            ((1, 9, 0), (1, 9, 0), False),
            ((1, 8, 0), (1, 9, 0), False),
        ],
    )
    def test_strict_gt(self, latest, current, expected) -> None:
        assert is_newer(latest, current) is expected


# ── should_check_now ─────────────────────────────────────────────────────


class TestShouldCheckNow:
    def test_never_checked_returns_true(self) -> None:
        assert should_check_now(0.0) is True

    def test_just_checked_returns_false(self) -> None:
        assert should_check_now(time.time()) is False

    def test_25h_ago_returns_true(self) -> None:
        assert should_check_now(time.time() - 25 * 3600) is True

    def test_23h_ago_returns_false(self) -> None:
        assert should_check_now(time.time() - 23 * 3600) is False

    def test_custom_interval(self) -> None:
        assert should_check_now(time.time() - 7200, interval_h=1.0) is True


# ── latest_release: /releases/latest happy path ──────────────────────────


class TestLatestReleaseHappyPath:
    def test_releases_200(self) -> None:
        payload = json.dumps(
            {
                "tag_name": "v1.10.0",
                "html_url": "https://github.com/x/y/releases/tag/v1.10.0",
                "body": "## Notes\n- thing",
            }
        ).encode("utf-8")

        def side(*_a, **_kw):
            return _FakeResponse(payload)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is not None
        assert r.version == (1, 10, 0)
        assert r.version_str == "1.10.0"
        assert r.is_tag_fallback is False
        assert "1.10.0" in r.html_url
        assert "thing" in r.body

    def test_releases_200_rejects_non_semver_tag(self) -> None:
        payload = json.dumps({"tag_name": "release-2024-q1", "html_url": ""}).encode()

        def side(*_a, **_kw):
            return _FakeResponse(payload)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_releases_200_pre_release_tag_rejected(self) -> None:
        payload = json.dumps({"tag_name": "v1.10.0-rc1", "html_url": ""}).encode()

        def side(*_a, **_kw):
            return _FakeResponse(payload)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None


# ── /tags fallback (404 → /tags 200) ─────────────────────────────────────


class TestTagsFallback:
    def test_404_then_tags_200_picks_max(self) -> None:
        tags_payload = json.dumps(
            [
                {"name": "v1.9.0"},
                {"name": "v1.10.0"},
                {"name": "v1.10.0-beta"},  # excluded
                {"name": "untagged-something"},  # excluded
                {"name": "v1.9.5"},
            ]
        ).encode("utf-8")

        calls = {"n": 0}

        def side(req, *_a, **_kw):
            calls["n"] += 1
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/releases/latest" in url:
                raise _http_error(404)
            return _FakeResponse(tags_payload)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is not None
        assert r.version == (1, 10, 0)
        assert r.is_tag_fallback is True
        assert r.body == ""
        assert "v1.10.0" in r.html_url
        assert calls["n"] == 2

    def test_404_then_tags_404_returns_none(self) -> None:
        def side(*_a, **_kw):
            raise _http_error(404)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_404_then_tags_empty_list_returns_none(self) -> None:
        def side(req, *_a, **_kw):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/releases/latest" in url:
                raise _http_error(404)
            return _FakeResponse(b"[]")

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_404_then_tags_only_pre_release_returns_none(self) -> None:
        tags = json.dumps(
            [{"name": "v2.0.0-rc1"}, {"name": "v2.0.0-beta"}]
        ).encode("utf-8")

        def side(req, *_a, **_kw):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/releases/latest" in url:
                raise _http_error(404)
            return _FakeResponse(tags)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None


# ── failure modes ────────────────────────────────────────────────────────


class TestFailureModes:
    def test_timeout_returns_none(self) -> None:
        def side(*_a, **_kw):
            raise socket.timeout("timed out")

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_url_error_returns_none(self) -> None:
        def side(*_a, **_kw):
            raise urllib.error.URLError("dns")

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_http_500_returns_none(self) -> None:
        def side(*_a, **_kw):
            raise _http_error(500)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_garbage_json_returns_none(self) -> None:
        def side(*_a, **_kw):
            return _FakeResponse(b"<!DOCTYPE html><html>oops</html>")

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_releases_payload_missing_tag_name(self) -> None:
        def side(*_a, **_kw):
            return _FakeResponse(b'{"html_url": "https://x"}')

        with _patch_urlopen(side):
            r = latest_release()
        assert r is None

    def test_body_non_string_coerced_or_blank(self) -> None:
        # Defensive: a malformed body field should not crash parsing.
        payload = json.dumps(
            {"tag_name": "v1.10.0", "html_url": "https://x", "body": None}
        ).encode("utf-8")

        def side(*_a, **_kw):
            return _FakeResponse(payload)

        with _patch_urlopen(side):
            r = latest_release()
        assert r is not None
        assert isinstance(r.body, str)


# ── module-level smoke ───────────────────────────────────────────────────


def test_module_exports() -> None:
    for name in ("ReleaseInfo", "latest_release", "is_newer", "should_check_now"):
        assert name in update_checker.__all__
