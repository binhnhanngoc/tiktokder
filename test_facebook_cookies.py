"""Tests for facebook_cookies: Netscape format parsing + FB-domain filter."""

from __future__ import annotations

from pathlib import Path

import pytest

from facebook_cookies import filter_facebook, load_netscape_cookies


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "cookies.txt"
    p.write_text(body, encoding="utf-8")
    return p


class TestLoadNetscapeCookies:
    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert load_netscape_cookies(tmp_path / "nope.txt") == []

    def test_basic_row(self, tmp_path: Path):
        f = _write(tmp_path, ".facebook.com\tTRUE\t/\tTRUE\t1900000000\tc_user\t12345")
        cookies = load_netscape_cookies(f)
        assert len(cookies) == 1
        c = cookies[0]
        assert c["name"] == "c_user"
        assert c["value"] == "12345"
        assert c["domain"] == ".facebook.com"
        assert c["path"] == "/"
        assert c["secure"] is True
        assert c["httpOnly"] is False
        assert c["expires"] == 1900000000

    def test_httponly_prefix_marks_flag(self, tmp_path: Path):
        f = _write(
            tmp_path,
            "#HttpOnly_.facebook.com\tTRUE\t/\tTRUE\t1900000000\txs\tabc",
        )
        cookies = load_netscape_cookies(f)
        assert cookies[0]["httpOnly"] is True
        assert cookies[0]["domain"] == ".facebook.com"

    def test_comments_and_blank_lines_skipped(self, tmp_path: Path):
        body = (
            "# Netscape HTTP Cookie File\n"
            "\n"
            ".facebook.com\tTRUE\t/\tTRUE\t1900000000\tc_user\t12345\n"
            "# trailing comment\n"
        )
        f = _write(tmp_path, body)
        cookies = load_netscape_cookies(f)
        assert len(cookies) == 1
        assert cookies[0]["name"] == "c_user"

    def test_malformed_line_skipped(self, tmp_path: Path):
        body = (
            "not\ta\tcookie\n"
            ".facebook.com\tTRUE\t/\tTRUE\t1900000000\tc_user\t12345\n"
        )
        f = _write(tmp_path, body)
        cookies = load_netscape_cookies(f)
        assert len(cookies) == 1

    def test_session_cookie_omits_expires(self, tmp_path: Path):
        f = _write(tmp_path, ".facebook.com\tTRUE\t/\tTRUE\t0\tsess\txyz")
        cookies = load_netscape_cookies(f)
        assert "expires" not in cookies[0]

    def test_unparseable_expires_treated_as_session(self, tmp_path: Path):
        f = _write(tmp_path, ".facebook.com\tTRUE\t/\tTRUE\tnotanumber\tsess\txyz")
        cookies = load_netscape_cookies(f)
        assert "expires" not in cookies[0]

    def test_path_default(self, tmp_path: Path):
        f = _write(tmp_path, ".facebook.com\tTRUE\t\tTRUE\t1900000000\tname\tval")
        cookies = load_netscape_cookies(f)
        assert cookies[0]["path"] == "/"


class TestFilterFacebook:
    def test_keeps_facebook_domains(self):
        cookies = [
            {"name": "a", "value": "1", "domain": ".facebook.com"},
            {"name": "b", "value": "2", "domain": "www.facebook.com"},
            {"name": "c", "value": "3", "domain": "m.facebook.com"},
        ]
        result = filter_facebook(cookies)
        assert {c["name"] for c in result} == {"a", "b", "c"}

    def test_drops_unrelated_domains(self):
        cookies = [
            {"name": "ok", "value": "1", "domain": ".facebook.com"},
            {"name": "bad", "value": "2", "domain": ".google.com"},
            {"name": "phish", "value": "3", "domain": ".notfacebook.com"},
        ]
        result = filter_facebook(cookies)
        assert {c["name"] for c in result} == {"ok"}

    def test_case_insensitive_domain(self):
        cookies = [{"name": "x", "value": "1", "domain": ".FaceBook.COM"}]
        assert len(filter_facebook(cookies)) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
