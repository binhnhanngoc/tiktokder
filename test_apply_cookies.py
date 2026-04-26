"""Tests for the apply_cookies() yt-dlp option helper."""

from __future__ import annotations

from pathlib import Path

from yt_dlp_helpers import apply_cookies


class TestApplyCookies:
    """Precedence: existing cookie *file* wins over *browser*; missing file
    falls through to browser; neither set → no mutation.
    """

    def test_both_none_no_mutation(self) -> None:
        opts: dict = {}
        apply_cookies(opts, None, None)
        assert opts == {}

    def test_browser_only_sets_cookiesfrombrowser(self) -> None:
        opts: dict = {}
        apply_cookies(opts, "chrome", None)
        assert opts == {"cookiesfrombrowser": ("chrome",)}

    def test_file_only_existing_sets_cookiefile(self, tmp_path: Path) -> None:
        f = tmp_path / "cookies.txt"
        f.write_text("# fake netscape", encoding="utf-8")
        opts: dict = {}
        apply_cookies(opts, None, str(f))
        assert opts == {"cookiefile": str(f)}

    def test_file_missing_silent_skip(self, tmp_path: Path) -> None:
        opts: dict = {}
        apply_cookies(opts, None, str(tmp_path / "nope.txt"))
        assert opts == {}

    def test_both_file_wins(self, tmp_path: Path) -> None:
        f = tmp_path / "cookies.txt"
        f.write_text("# fake", encoding="utf-8")
        opts: dict = {}
        apply_cookies(opts, "chrome", str(f))
        assert opts == {"cookiefile": str(f)}
        assert "cookiesfrombrowser" not in opts

    def test_both_file_missing_falls_through_to_browser(self, tmp_path: Path) -> None:
        opts: dict = {}
        apply_cookies(opts, "chrome", str(tmp_path / "missing.txt"))
        assert opts == {"cookiesfrombrowser": ("chrome",)}
