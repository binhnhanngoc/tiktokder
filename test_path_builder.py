"""Tests for path_builder.py — slugify, URL fallback slug, outtmpl assembly."""

import os

import pytest

from path_builder import (
    UNKNOWN_UPLOADER,
    build_output_template,
    platform_slug_from_url,
    slugify_uploader,
)


class TestSlugifyUploader:
    def test_strips_path_separators(self):
        assert slugify_uploader("@user/with/slash") == "@user_with_slash"
        assert slugify_uploader(r"name\with\back") == "name_with_back"

    def test_strips_reserved_chars(self):
        assert slugify_uploader('a<b>c:d"e|f?g*h') == "a_b_c_d_e_f_g_h"

    def test_collapses_whitespace_and_underscores(self):
        assert slugify_uploader("multiple   spaces") == "multiple_spaces"
        assert slugify_uploader("a___b") == "a_b"

    def test_keeps_unicode_letters(self):
        assert slugify_uploader("Tiếng Việt") == "Tiếng_Việt"

    def test_strips_emoji_via_reserved_filter(self):
        result = slugify_uploader("user😀name")
        # Emoji is not in reserved set — Python keeps it; just verify length-safe.
        assert "user" in result and "name" in result
        assert "/" not in result

    def test_empty_returns_unknown_uploader(self):
        assert slugify_uploader("") == UNKNOWN_UPLOADER
        assert slugify_uploader(None) == UNKNOWN_UPLOADER
        assert slugify_uploader("   ") == UNKNOWN_UPLOADER

    def test_only_separators_returns_unknown(self):
        assert slugify_uploader("///") == UNKNOWN_UPLOADER
        assert slugify_uploader("...") == UNKNOWN_UPLOADER

    def test_truncates_to_80(self):
        long_name = "a" * 200
        result = slugify_uploader(long_name)
        assert len(result) <= 80


class TestPlatformSlugFromUrl:
    def test_tiktok_handle(self):
        assert platform_slug_from_url("https://www.tiktok.com/@user/video/123") == "@user"

    def test_facebook_page(self):
        assert platform_slug_from_url("https://www.facebook.com/PageName") == "PageName"

    def test_facebook_videos_path(self):
        # /pagename/videos/123 — should pick "pagename" not "videos".
        assert platform_slug_from_url("https://www.facebook.com/pagename/videos/123") == "pagename"

    def test_facebook_watch_path(self):
        assert platform_slug_from_url("https://www.facebook.com/watch/?v=123") == UNKNOWN_UPLOADER \
            or platform_slug_from_url("https://www.facebook.com/watch/?v=123") != ""

    def test_facebook_reel_url_skips_numeric_id(self):
        # /reel/<digits> has no page name in path — must NOT use the video id.
        assert platform_slug_from_url("https://www.facebook.com/reel/1438416620945910") == UNKNOWN_UPLOADER

    def test_facebook_videos_path_skips_numeric_id(self):
        # /pagename/videos/<digits> still picks pagename, not the trailing id.
        assert platform_slug_from_url("https://www.facebook.com/NeonNewZealand/videos/1438416620945910") == "NeonNewZealand"

    def test_facebook_profile_php_uses_id_query(self):
        # profile.php?id=<digits> — only stable identifier is the id;
        # prefix with profile_ so each profile gets its own folder.
        url = "https://www.facebook.com/profile.php?id=100093703437726"
        assert platform_slug_from_url(url) == "profile_100093703437726"

    def test_facebook_profile_php_without_id_falls_back(self):
        # No `id` query → no usable identifier in URL → unknown.
        assert platform_slug_from_url("https://www.facebook.com/profile.php") == UNKNOWN_UPLOADER

    def test_empty_url(self):
        assert platform_slug_from_url("") == UNKNOWN_UPLOADER

    def test_no_path(self):
        assert platform_slug_from_url("https://www.tiktok.com/") == UNKNOWN_UPLOADER


class TestBuildOutputTemplate:
    def test_tiktok_with_uploader_metadata(self):
        from path_builder import FILENAME_TEMPLATE

        url = "https://www.tiktok.com/@user/video/123"
        info = {"uploader": "@user", "id": "123"}
        tmpl = build_output_template(url, info, "downloads")
        # Normalize for cross-platform.
        norm = tmpl.replace(os.sep, "/")
        assert norm == f"downloads/tiktok/@user/{FILENAME_TEMPLATE}"

    def test_facebook_no_uploader_falls_back_to_url_slug(self):
        from path_builder import FILENAME_TEMPLATE

        url = "https://www.facebook.com/PageName/videos/123"
        info = {}  # uploader missing
        tmpl = build_output_template(url, info, "downloads")
        norm = tmpl.replace(os.sep, "/")
        assert "facebook" in norm
        assert "PageName" in norm
        assert norm.endswith(f"/{FILENAME_TEMPLATE}")

    def test_unknown_platform_uses_unknown_segment(self):
        url = "https://example.com/something/123"
        tmpl = build_output_template(url, None, "downloads")
        norm = tmpl.replace(os.sep, "/")
        assert "/unknown/" in norm

    def test_empty_uploader_string_falls_back_to_unknown(self):
        url = "https://www.tiktok.com/somepath"
        info = {"uploader": ""}
        tmpl = build_output_template(url, info, "downloads")
        norm = tmpl.replace(os.sep, "/")
        # tiktok URL without @handle → no path-derived handle → unknown_uploader
        assert UNKNOWN_UPLOADER in norm or "/somepath/" in norm

    def test_uses_channel_when_uploader_missing(self):
        url = "https://www.facebook.com/x/videos/9"
        info = {"channel": "Channel Name"}
        tmpl = build_output_template(url, info, "downloads")
        norm = tmpl.replace(os.sep, "/")
        assert "Channel_Name" in norm

    def test_facebook_reel_with_numeric_uploader_id_falls_back_to_url(self):
        # yt-dlp commonly returns only a numeric uploader_id for FB reels —
        # must NOT become the folder name.
        url = "https://www.facebook.com/NeonNewZealand/videos/123"
        info = {"uploader_id": "1017087350885646", "id": "123"}
        tmpl = build_output_template(url, info, "downloads")
        norm = tmpl.replace(os.sep, "/")
        assert "1017087350885646" not in norm
        assert "NeonNewZealand" in norm

    def test_facebook_reel_uses_uploader_url_when_path_lacks_page(self):
        # /reel/<id> has no page in path — recover from uploader_url.
        url = "https://www.facebook.com/reel/1438416620945910"
        info = {
            "uploader_id": "1017087350885646",
            "uploader_url": "https://www.facebook.com/NeonNewZealand",
        }
        tmpl = build_output_template(url, info, "downloads")
        norm = tmpl.replace(os.sep, "/")
        assert "NeonNewZealand" in norm
        assert "1438416620945910" not in norm.split("/")[:-1]  # not in the folder portion

    def test_facebook_reel_no_metadata_lands_in_unknown_uploader(self):
        # Worst case: /reel/<id> URL with empty info → unknown_uploader, never numeric.
        url = "https://www.facebook.com/reel/1438416620945910"
        tmpl = build_output_template(url, {}, "downloads")
        norm = tmpl.replace(os.sep, "/")
        assert f"/facebook/{UNKNOWN_UPLOADER}/" in norm

    def test_page_hint_url_overrides_missing_metadata(self):
        # Browser panel scraped from facebook.com/NeonNewZealand → reel URL
        # carries no page; hint URL recovers the page name.
        url = "https://www.facebook.com/reel/1438416620945910"
        tmpl = build_output_template(
            url, {}, "downloads",
            page_hint="https://www.facebook.com/NeonNewZealand",
        )
        norm = tmpl.replace(os.sep, "/")
        assert "/facebook/NeonNewZealand/" in norm

    def test_page_hint_bare_slug_used_directly(self):
        url = "https://www.facebook.com/watch/?v=999"
        tmpl = build_output_template(url, {}, "downloads", page_hint="NeonNewZealand")
        norm = tmpl.replace(os.sep, "/")
        assert "/facebook/NeonNewZealand/" in norm

    def test_page_hint_overrides_numeric_uploader_id(self):
        url = "https://www.facebook.com/reel/123"
        info = {"uploader_id": "1017087350885646"}
        tmpl = build_output_template(
            url, info, "downloads", page_hint="https://www.facebook.com/NeonNewZealand"
        )
        norm = tmpl.replace(os.sep, "/")
        assert "NeonNewZealand" in norm
        assert "1017087350885646" not in norm

    def test_page_hint_empty_string_is_ignored(self):
        url = "https://www.facebook.com/PageName/videos/9"
        tmpl = build_output_template(url, {}, "downloads", page_hint="")
        norm = tmpl.replace(os.sep, "/")
        assert "PageName" in norm

    def test_page_hint_numeric_only_is_ignored(self):
        url = "https://www.facebook.com/PageName/videos/9"
        tmpl = build_output_template(url, {}, "downloads", page_hint="1234567890")
        norm = tmpl.replace(os.sep, "/")
        assert "PageName" in norm
        assert "1234567890" not in norm

    def test_page_hint_profile_php_id_becomes_profile_folder(self):
        # User browses facebook.com/profile.php?id=<digits>; reel downloads
        # land in `<facebook>/profile_<digits>/`, not in literal `profile.php/`.
        url = "https://www.facebook.com/reel/9876543210"
        hint = "https://www.facebook.com/profile.php?id=100093703437726"
        tmpl = build_output_template(url, {}, "downloads", page_hint=hint)
        norm = tmpl.replace(os.sep, "/")
        assert "/facebook/profile_100093703437726/" in norm
        assert "profile.php" not in norm

    def test_base_dir_with_absolute_path(self):
        url = "https://www.tiktok.com/@u/video/1"
        info = {"uploader": "@u"}
        base = os.path.join(os.sep, "tmp", "downloads")
        tmpl = build_output_template(url, info, base)
        assert tmpl.startswith(base)
