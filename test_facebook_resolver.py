"""Tests for facebook_resolver: shortlink detection + mocked HTTP resolution."""

from unittest.mock import MagicMock, patch

import pytest

from facebook_resolver import is_fb_shortlink, resolve_fb_shortlink


class TestIsFbShortlink:
    def test_positive_basic(self):
        assert is_fb_shortlink("https://fb.watch/abc/") is True

    def test_positive_no_trailing_slash(self):
        assert is_fb_shortlink("https://fb.watch/abc123") is True

    def test_positive_uppercase(self):
        assert is_fb_shortlink("HTTPS://FB.WATCH/X") is True

    def test_negative_facebook_watch(self):
        assert is_fb_shortlink("https://www.facebook.com/watch?v=123") is False

    def test_negative_tiktok(self):
        assert is_fb_shortlink("https://www.tiktok.com/@u/video/1") is False

    def test_negative_empty(self):
        assert is_fb_shortlink("") is False


def _mock_session(response_mock):
    """Build a session-like mock whose Session(...) returns a context with .get()."""
    session_instance = MagicMock()
    session_instance.get.return_value = response_mock
    session_instance.close.return_value = None
    requests_module = MagicMock()
    requests_module.Session.return_value = session_instance
    return requests_module


def _patch_curl_cffi(monkeypatch, requests_module):
    """Inject a fake curl_cffi.requests into resolve_fb_shortlink's import path."""
    import sys

    fake_pkg = MagicMock()
    fake_pkg.requests = requests_module
    monkeypatch.setitem(sys.modules, "curl_cffi", fake_pkg)
    monkeypatch.setitem(sys.modules, "curl_cffi.requests", requests_module)


class TestResolveFbShortlink:
    def test_redirect_to_login_returns_login_required(self, monkeypatch):
        response = MagicMock()
        response.status_code = 302
        response.headers = {"Location": "https://www.facebook.com/login/?next=/x"}
        response.text = ""
        _patch_curl_cffi(monkeypatch, _mock_session(response))

        url = "https://fb.watch/abc/"
        canonical, status = resolve_fb_shortlink(url)
        assert status == "login_required"
        assert canonical == url

    def test_redirect_to_canonical_returns_ok(self, monkeypatch):
        response = MagicMock()
        response.status_code = 302
        response.headers = {"Location": "https://www.facebook.com/watch?v=123"}
        response.text = ""
        _patch_curl_cffi(monkeypatch, _mock_session(response))

        canonical, status = resolve_fb_shortlink("https://fb.watch/abc/")
        assert status == "ok"
        assert canonical == "https://www.facebook.com/watch?v=123"

    def test_200_with_login_marker_returns_login_required(self, monkeypatch):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.text = '<html><form id="login_form">login</form></html>'
        _patch_curl_cffi(monkeypatch, _mock_session(response))

        url = "https://fb.watch/abc/"
        canonical, status = resolve_fb_shortlink(url)
        assert status == "login_required"
        assert canonical == url

    def test_200_clean_returns_ok(self, monkeypatch):
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.text = "<html><body>real video page</body></html>"
        _patch_curl_cffi(monkeypatch, _mock_session(response))

        url = "https://fb.watch/abc/"
        canonical, status = resolve_fb_shortlink(url)
        assert status == "ok"
        assert canonical == url

    def test_network_error_returns_unknown_fail_open(self, monkeypatch):
        requests_module = MagicMock()
        session_instance = MagicMock()
        session_instance.get.side_effect = TimeoutError("network down")
        session_instance.close.return_value = None
        requests_module.Session.return_value = session_instance
        _patch_curl_cffi(monkeypatch, requests_module)

        url = "https://fb.watch/abc/"
        canonical, status = resolve_fb_shortlink(url, timeout=0.1)
        assert status == "unknown"
        assert canonical == url

    def test_unexpected_status_returns_unknown(self, monkeypatch):
        response = MagicMock()
        response.status_code = 418
        response.headers = {}
        response.text = ""
        _patch_curl_cffi(monkeypatch, _mock_session(response))

        url = "https://fb.watch/abc/"
        canonical, status = resolve_fb_shortlink(url)
        assert status == "unknown"
        assert canonical == url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
