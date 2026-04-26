"""
Comprehensive tests for TikTok batch video downloader.

Tests cover:
- url_parser functions (URL validation, ID extraction, batch file reading, username validation)
- CLI argument parsing and validation
- Download batch processing logic (without actual network calls)
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from url_parser import (
    validate_tiktok_url,
    validate_facebook_url,
    validate_url,
    is_facebook_page_url,
    detect_platform,
    extract_video_id,
    read_batch_file,
    build_user_url,
    is_channel_url,
)
from downloader import (
    get_ydl_opts,
    get_downloaded_ids,
    DownloadResult,
    _classify_error,
    _jittered_sleep,
)
from main import parse_args


# =============================================================================
# URL PARSER TESTS
# =============================================================================


class TestValidateTikTokUrl:
    """Test TikTok URL validation."""

    def test_valid_video_url_standard(self):
        """Test standard TikTok video URL."""
        url = "https://www.tiktok.com/@username/video/1234567890123456789"
        assert validate_tiktok_url(url) is True

    def test_valid_video_url_short_vm(self):
        """Test short vm.tiktok.com URL."""
        url = "https://vm.tiktok.com/ZMRvEabc1/"
        assert validate_tiktok_url(url) is True

    def test_valid_video_url_short_vt(self):
        """Test short vt.tiktok.com URL."""
        url = "https://vt.tiktok.com/ZSRvEabc1/"
        assert validate_tiktok_url(url) is True

    def test_valid_short_code_url(self):
        """Test short TikTok code URL (alphanumeric only)."""
        # The regex accepts /username format for short codes like tiktok.com/abcdef
        url = "https://tiktok.com/ZMRvEabc1"
        assert validate_tiktok_url(url) is True

    def test_valid_url_with_trailing_slash(self):
        """Test URL with trailing slash."""
        url = "https://www.tiktok.com/@username/video/1234567890123456789/"
        assert validate_tiktok_url(url) is True

    def test_valid_url_without_www(self):
        """Test URL without www prefix."""
        url = "https://tiktok.com/@username/video/1234567890123456789"
        assert validate_tiktok_url(url) is True

    def test_valid_url_http_not_https(self):
        """Test HTTP (non-HTTPS) URL."""
        url = "http://www.tiktok.com/@username/video/1234567890123456789"
        assert validate_tiktok_url(url) is True

    def test_invalid_url_wrong_domain(self):
        """Test URL with wrong domain."""
        url = "https://www.youtube.com/@username/video/1234567890123456789"
        assert validate_tiktok_url(url) is False

    def test_invalid_url_no_protocol(self):
        """Test URL without protocol."""
        url = "www.tiktok.com/@username/video/1234567890123456789"
        assert validate_tiktok_url(url) is False

    def test_invalid_url_special_chars_in_code(self):
        """Test URL with special characters (not allowed)."""
        # Short codes can only be alphanumeric, no special chars like -
        url = "https://tiktok.com/invalid-code-with-dash"
        assert validate_tiktok_url(url) is False

    def test_invalid_url_empty_string(self):
        """Test empty string."""
        assert validate_tiktok_url("") is False

    def test_valid_url_with_whitespace(self):
        """Test URL with leading/trailing whitespace (should be stripped)."""
        url = "  https://www.tiktok.com/@username/video/1234567890123456789  "
        assert validate_tiktok_url(url) is True

    def test_invalid_username_with_special_chars(self):
        """Test URL with invalid username characters."""
        url = "https://www.tiktok.com/@user!name/video/1234567890123456789"
        assert validate_tiktok_url(url) is False


class TestIsChannelUrl:
    """Test channel/profile URL detection."""

    def test_channel_url_basic(self):
        assert is_channel_url("https://www.tiktok.com/@username") is True

    def test_channel_url_with_trailing_slash(self):
        assert is_channel_url("https://www.tiktok.com/@username/") is True

    def test_channel_url_without_www(self):
        assert is_channel_url("https://tiktok.com/@user.name") is True

    def test_channel_url_with_dots_underscores(self):
        assert is_channel_url("https://www.tiktok.com/@user.name_123") is True

    def test_video_url_is_not_channel(self):
        assert is_channel_url("https://www.tiktok.com/@user/video/123456789") is False

    def test_short_url_is_not_channel(self):
        assert is_channel_url("https://vm.tiktok.com/ZMRvEabc1/") is False

    def test_empty_string(self):
        assert is_channel_url("") is False

    def test_non_tiktok_url(self):
        assert is_channel_url("https://www.youtube.com/@user") is False


class TestValidateFacebookUrl:
    """Test Facebook URL validation."""

    def test_valid_facebook_video_url(self):
        url = "https://www.facebook.com/user/videos/1234567890"
        assert validate_facebook_url(url) is True

    def test_valid_facebook_watch_url(self):
        url = "https://www.facebook.com/watch/?v=1234567890"
        assert validate_facebook_url(url) is True

    def test_valid_facebook_reel_url(self):
        url = "https://www.facebook.com/reel/1234567890"
        assert validate_facebook_url(url) is True

    def test_valid_fb_watch_short_link(self):
        url = "https://fb.watch/abc123/"
        assert validate_facebook_url(url) is True

    def test_valid_mobile_facebook_url(self):
        url = "https://m.facebook.com/user/videos/1234567890"
        assert validate_facebook_url(url) is True

    def test_valid_fb_com_short_url(self):
        url = "https://fb.com/user/videos/123"
        assert validate_facebook_url(url) is True

    def test_invalid_youtube_url(self):
        url = "https://www.youtube.com/watch?v=abc"
        assert validate_facebook_url(url) is False

    def test_invalid_empty_string(self):
        assert validate_facebook_url("") is False

    def test_invalid_tiktok_url(self):
        url = "https://www.tiktok.com/@user/video/123"
        assert validate_facebook_url(url) is False


class TestIsFacebookPageUrl:
    """Test Facebook page URL detection."""

    def test_facebook_page_url(self):
        assert is_facebook_page_url("https://www.facebook.com/pagename") is True

    def test_facebook_page_url_trailing_slash(self):
        assert is_facebook_page_url("https://www.facebook.com/pagename/") is True

    def test_facebook_page_url_with_dots(self):
        assert is_facebook_page_url("https://www.facebook.com/page.name") is True

    def test_facebook_video_url_not_page(self):
        assert is_facebook_page_url("https://www.facebook.com/user/videos/123") is False

    def test_non_facebook_url(self):
        assert is_facebook_page_url("https://www.tiktok.com/@user") is False

    def test_empty_string(self):
        assert is_facebook_page_url("") is False


class TestDetectPlatform:
    """Test platform detection."""

    def test_detect_tiktok_video(self):
        url = "https://www.tiktok.com/@user/video/1234567890"
        assert detect_platform(url) == "tiktok"

    def test_detect_tiktok_channel(self):
        url = "https://www.tiktok.com/@username"
        assert detect_platform(url) == "tiktok"

    def test_detect_facebook_video(self):
        url = "https://www.facebook.com/user/videos/123"
        assert detect_platform(url) == "facebook"

    def test_detect_facebook_page(self):
        url = "https://www.facebook.com/pagename"
        assert detect_platform(url) == "facebook"

    def test_detect_fb_watch(self):
        url = "https://fb.watch/abc123/"
        assert detect_platform(url) == "facebook"

    def test_detect_unknown(self):
        url = "https://www.youtube.com/watch?v=abc"
        assert detect_platform(url) is None

    def test_detect_empty(self):
        assert detect_platform("") is None


class TestValidateUrl:
    """Test unified URL validation."""

    def test_tiktok_url_valid(self):
        assert validate_url("https://www.tiktok.com/@user/video/123456789") is True

    def test_facebook_url_valid(self):
        assert validate_url("https://www.facebook.com/user/videos/123") is True

    def test_youtube_url_invalid(self):
        assert validate_url("https://www.youtube.com/watch?v=abc") is False

    def test_empty_string(self):
        assert validate_url("") is False


class TestExtractVideoId:
    """Test video ID extraction."""

    def test_extract_id_from_standard_url(self):
        """Test extracting ID from standard URL."""
        url = "https://www.tiktok.com/@username/video/1234567890123456789"
        video_id = extract_video_id(url)
        assert video_id == "1234567890123456789"

    def test_extract_id_from_short_url(self):
        """Test extracting ID from short URL (no /video/ part)."""
        url = "https://vm.tiktok.com/ZMRvEabc1/"
        video_id = extract_video_id(url)
        assert video_id is None  # Short URLs don't contain /video/ pattern

    def test_extract_id_with_different_digit_length(self):
        """Test ID extraction with different digit lengths."""
        url = "https://www.tiktok.com/@user/video/999888777666555444"
        video_id = extract_video_id(url)
        assert video_id == "999888777666555444"

    def test_extract_id_returns_none_for_profile_url(self):
        """Test that profile URL returns None (no video ID)."""
        url = "https://www.tiktok.com/@username"
        video_id = extract_video_id(url)
        assert video_id is None

    def test_extract_id_returns_none_invalid_url(self):
        """Test that invalid URL returns None."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(url)
        assert video_id is None

    def test_extract_id_empty_string(self):
        """Test empty string returns None."""
        video_id = extract_video_id("")
        assert video_id is None


class TestReadBatchFile:
    """Test batch file reading."""

    def test_read_batch_file_single_url(self):
        """Test reading file with single URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("https://www.tiktok.com/@user/video/123456789\n")
            urls = read_batch_file(filepath)
            assert len(urls) == 1
            assert urls[0] == "https://www.tiktok.com/@user/video/123456789"

    def test_read_batch_file_multiple_urls(self):
        """Test reading file with multiple URLs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("https://www.tiktok.com/@user1/video/111\n")
                f.write("https://www.tiktok.com/@user2/video/222\n")
                f.write("https://www.tiktok.com/@user3/video/333\n")
            urls = read_batch_file(filepath)
            assert len(urls) == 3
            assert urls[0] == "https://www.tiktok.com/@user1/video/111"
            assert urls[2] == "https://www.tiktok.com/@user3/video/333"

    def test_read_batch_file_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("https://www.tiktok.com/@user1/video/111\n")
                f.write("\n")
                f.write("https://www.tiktok.com/@user2/video/222\n")
                f.write("\n\n")
                f.write("https://www.tiktok.com/@user3/video/333\n")
            urls = read_batch_file(filepath)
            assert len(urls) == 3

    def test_read_batch_file_skip_comments(self):
        """Test that comment lines are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("# This is a comment\n")
                f.write("https://www.tiktok.com/@user1/video/111\n")
                f.write("# Another comment\n")
                f.write("https://www.tiktok.com/@user2/video/222\n")
            urls = read_batch_file(filepath)
            assert len(urls) == 2
            assert "# This is a comment" not in urls

    def test_read_batch_file_remove_duplicates(self):
        """Test that duplicate URLs are removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("https://www.tiktok.com/@user1/video/111\n")
                f.write("https://www.tiktok.com/@user1/video/111\n")
                f.write("https://www.tiktok.com/@user2/video/222\n")
                f.write("https://www.tiktok.com/@user1/video/111\n")
            urls = read_batch_file(filepath)
            assert len(urls) == 2
            assert urls.count("https://www.tiktok.com/@user1/video/111") == 1

    def test_read_batch_file_strip_whitespace(self):
        """Test that whitespace is stripped from lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("  https://www.tiktok.com/@user1/video/111  \n")
                f.write("\thttps://www.tiktok.com/@user2/video/222\t\n")
            urls = read_batch_file(filepath)
            assert len(urls) == 2
            assert urls[0] == "https://www.tiktok.com/@user1/video/111"
            assert urls[1] == "https://www.tiktok.com/@user2/video/222"

    def test_read_batch_file_not_found(self):
        """Test that FileNotFoundError is raised for non-existent file."""
        with pytest.raises(FileNotFoundError):
            read_batch_file("/nonexistent/path/to/file.txt")

    def test_read_batch_file_empty_file(self):
        """Test reading empty file returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                pass  # Create empty file
            urls = read_batch_file(filepath)
            assert urls == []

    def test_read_batch_file_only_comments_and_empty_lines(self):
        """Test file with only comments and empty lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'urls.txt')
            with open(filepath, 'w') as f:
                f.write("# Comment 1\n")
                f.write("\n")
                f.write("# Comment 2\n")
                f.write("\n\n")
            urls = read_batch_file(filepath)
            assert urls == []


class TestBuildUserUrl:
    """Test username URL builder."""

    def test_build_url_with_at_symbol(self):
        """Test building URL with @ symbol in input."""
        url = build_user_url("@username")
        assert url == "https://www.tiktok.com/@username"

    def test_build_url_without_at_symbol(self):
        """Test building URL without @ symbol (should add it)."""
        url = build_user_url("username")
        assert url == "https://www.tiktok.com/@username"

    def test_build_url_with_underscores(self):
        """Test username with underscores."""
        url = build_user_url("user_name_123")
        assert url == "https://www.tiktok.com/@user_name_123"

    def test_build_url_with_dots(self):
        """Test username with dots."""
        url = build_user_url("user.name")
        assert url == "https://www.tiktok.com/@user.name"

    def test_build_url_mixed_characters(self):
        """Test username with mixed valid characters."""
        url = build_user_url("user.name_123")
        assert url == "https://www.tiktok.com/@user.name_123"

    def test_build_url_invalid_special_chars(self):
        """Test that invalid special characters raise ValueError."""
        with pytest.raises(ValueError):
            build_user_url("user-name")

    def test_build_url_invalid_space(self):
        """Test that spaces raise ValueError."""
        with pytest.raises(ValueError):
            build_user_url("user name")

    def test_build_url_invalid_email_format(self):
        """Test that email-like format raises ValueError."""
        with pytest.raises(ValueError):
            build_user_url("user@domain.com")

    def test_build_url_with_multiple_at_symbols(self):
        """Test multiple @ symbols - lstrip removes all leading @."""
        # lstrip('@') removes ALL leading '@' characters, so @@username -> username
        url = build_user_url("@@username")
        assert url == "https://www.tiktok.com/@username"

    def test_build_url_multiple_leading_at_symbols(self):
        """Test that lstrip behavior is correct for multiple @ symbols."""
        # Even with many @, lstrip removes them all and result is valid
        url = build_user_url("@@@@@username")
        assert url == "https://www.tiktok.com/@username"


# =============================================================================
# DOWNLOADER TESTS (without network)
# =============================================================================


class TestGetYdlOpts:
    """Test yt-dlp options generation."""

    def test_ydl_opts_contains_output_template(self):
        """Test that output template is set correctly."""
        opts = get_ydl_opts("/path/to/output")
        assert "outtmpl" in opts
        assert "/path/to/output" in opts["outtmpl"]

    def test_ydl_opts_format_single_stream(self):
        """Test that format is set to single best stream."""
        opts = get_ydl_opts("/path/to/output")
        assert opts["format"] == "b"

    def test_ydl_opts_quiet_mode(self):
        """Test that quiet mode is enabled."""
        opts = get_ydl_opts("/path/to/output")
        assert opts["quiet"] is True
        assert opts["no_warnings"] is True

    def test_ydl_opts_extract_flat(self):
        """Test that extract_flat is False."""
        opts = get_ydl_opts("/path/to/output")
        assert opts["extract_flat"] is False

    def test_ydl_opts_quality_best_default(self):
        """Default quality maps to single best stream."""
        opts = get_ydl_opts("/out")
        assert opts["format"] == "b"

    def test_ydl_opts_quality_720p_format(self):
        """720p quality emits height-capped format expression."""
        opts = get_ydl_opts("/out", quality="720p")
        assert opts["format"] == "bv*[height<=720]+ba/b[height<=720]"

    def test_ydl_opts_quality_1080p_format(self):
        opts = get_ydl_opts("/out", quality="1080p")
        assert opts["format"] == "bv*[height<=1080]+ba/b[height<=1080]"

    def test_ydl_opts_quality_480p_format(self):
        opts = get_ydl_opts("/out", quality="480p")
        assert opts["format"] == "bv*[height<=480]+ba/b[height<=480]"

    def test_ydl_opts_quality_audio_postprocessor(self):
        """Audio quality wires the FFmpegExtractAudio postprocessor."""
        opts = get_ydl_opts("/out", quality="audio")
        assert opts["format"] == "ba/b"
        post = opts.get("postprocessors") or []
        assert any(
            p.get("key") == "FFmpegExtractAudio" and p.get("preferredcodec") == "m4a"
            for p in post
        )

    def test_ydl_opts_quality_unknown_falls_back_to_best(self):
        """Unknown quality literal falls back to best (defensive default)."""
        opts = get_ydl_opts("/out", quality="garbage")
        assert opts["format"] == "b"

    def test_ydl_opts_subs_flags_set_when_enabled(self):
        opts = get_ydl_opts("/out", write_subs=True)
        assert opts["writesubtitles"] is True
        assert opts["writeautomaticsub"] is True
        assert opts["subtitleslangs"] == ["en"]
        assert opts["subtitlesformat"] == "srt/best"

    def test_ydl_opts_subs_default_off(self):
        opts = get_ydl_opts("/out")
        assert "writesubtitles" not in opts

    def test_ydl_opts_thumb_flag_set_when_enabled(self):
        opts = get_ydl_opts("/out", write_thumb=True)
        assert opts["writethumbnail"] is True

    def test_ydl_opts_thumb_default_off(self):
        opts = get_ydl_opts("/out")
        assert "writethumbnail" not in opts


class TestGetDownloadedIds:
    """Test scanning for already-downloaded video IDs."""

    def test_get_downloaded_ids_empty_dir(self):
        """Test with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ids = get_downloaded_ids(tmpdir)
            assert ids == set()

    def test_get_downloaded_ids_nonexistent_dir(self):
        """Test with non-existent directory returns empty set."""
        ids = get_downloaded_ids("/nonexistent/path/to/dir")
        assert ids == set()

    def test_get_downloaded_ids_valid_video_file(self):
        """Test extracting ID from valid video filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with valid video ID pattern
            Path(tmpdir, "1234567890123456789_video_title.mp4").touch()
            ids = get_downloaded_ids(tmpdir)
            assert "1234567890123456789" in ids

    def test_get_downloaded_ids_multiple_videos(self):
        """Test extracting IDs from multiple video files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "1234567890123456789_video1.mp4").touch()
            Path(tmpdir, "9876543210987654321_video2.mp4").touch()
            Path(tmpdir, "1111111111111111111_video3.mp4").touch()
            ids = get_downloaded_ids(tmpdir)
            assert len(ids) == 3
            assert "1234567890123456789" in ids
            assert "9876543210987654321" in ids
            assert "1111111111111111111" in ids

    def test_get_downloaded_ids_skip_non_matching_files(self):
        """Test that non-matching files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "1234567890123456789_video.mp4").touch()
            Path(tmpdir, "README.txt").touch()
            Path(tmpdir, "invalid_filename.mp4").touch()
            Path(tmpdir, "another_file.txt").touch()
            ids = get_downloaded_ids(tmpdir)
            assert len(ids) == 1
            assert "1234567890123456789" in ids

    def test_get_downloaded_ids_walks_recursively(self):
        """Recursive scan picks up IDs from both flat root and nested folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Flat-root legacy file.
            Path(tmpdir, "111111111111111_legacy.mp4").touch()
            # Nested platform/uploader layout.
            nested = Path(tmpdir, "tiktok", "@user")
            nested.mkdir(parents=True)
            (nested / "222222222222222_clip.mp4").touch()
            fb = Path(tmpdir, "facebook", "PageName")
            fb.mkdir(parents=True)
            (fb / "333333333333333_video.mp4").touch()

            ids = get_downloaded_ids(tmpdir)

            assert ids == {"111111111111111", "222222222222222", "333333333333333"}

    def test_get_downloaded_ids_id_boundary_15_digits(self):
        """Test with 15-digit ID (minimum)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "123456789012345_video.mp4").touch()
            ids = get_downloaded_ids(tmpdir)
            assert "123456789012345" in ids

    def test_get_downloaded_ids_id_boundary_25_digits(self):
        """Test with 25-digit ID (maximum)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "1234567890123456789012345_video.mp4").touch()
            ids = get_downloaded_ids(tmpdir)
            assert "1234567890123456789012345" in ids

    def test_get_downloaded_ids_id_boundary_14_digits(self):
        """Test with 14-digit ID (below minimum, should not match)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "12345678901234_video.mp4").touch()
            ids = get_downloaded_ids(tmpdir)
            assert len(ids) == 0

    def test_get_downloaded_ids_id_boundary_26_digits(self):
        """Test with 26-digit ID (above maximum, should not match)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "12345678901234567890123456_video.mp4").touch()
            ids = get_downloaded_ids(tmpdir)
            assert len(ids) == 0


class TestDownloadResult:
    """Test DownloadResult dataclass."""

    def test_download_result_success(self):
        """Test successful download result."""
        result = DownloadResult(
            url="https://www.tiktok.com/@user/video/123",
            success=True,
            video_id="123",
            title="Sample Video",
        )
        assert result.url == "https://www.tiktok.com/@user/video/123"
        assert result.success is True
        assert result.video_id == "123"
        assert result.title == "Sample Video"
        assert result.error is None
        assert result.skipped is False

    def test_download_result_failure(self):
        """Test failed download result."""
        result = DownloadResult(
            url="https://www.tiktok.com/@user/video/456",
            success=False,
            error="Network timeout",
        )
        assert result.url == "https://www.tiktok.com/@user/video/456"
        assert result.success is False
        assert result.error == "Network timeout"
        assert result.skipped is False

    def test_download_result_skipped(self):
        """Test skipped download result."""
        result = DownloadResult(
            url="https://www.tiktok.com/@user/video/789",
            success=True,
            video_id="789",
            skipped=True,
        )
        assert result.success is True
        assert result.skipped is True


# =============================================================================
# CLI ARGUMENT PARSING TESTS
# =============================================================================


class TestParseArgs:
    """Test CLI argument parsing."""

    def test_parse_args_no_arguments(self):
        """Test parsing with no arguments."""
        with patch('sys.argv', ['main.py']):
            args = parse_args()
            assert args.url is None
            assert args.batch is None
            assert args.user is None
            assert args.facebook_page is None
            assert args.output == "./downloads"
            # workers/delay default to None so main() can fall back to per-platform presets.
            assert args.workers is None
            assert args.delay is None

    def test_parse_args_single_url(self):
        """Test parsing single URL argument."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123']):
            args = parse_args()
            assert args.url == "https://www.tiktok.com/@user/video/123"
            assert args.batch is None
            assert args.user is None

    def test_parse_args_batch_file(self):
        """Test parsing batch file argument."""
        with patch('sys.argv', ['main.py', '--batch', 'urls.txt']):
            args = parse_args()
            assert args.url is None
            assert args.batch == "urls.txt"
            assert args.user is None

    def test_parse_args_user_username(self):
        """Test parsing user argument."""
        with patch('sys.argv', ['main.py', '--user', 'username']):
            args = parse_args()
            assert args.url is None
            assert args.batch is None
            assert args.user == "username"

    def test_parse_args_facebook_page(self):
        """Test parsing --facebook-page argument."""
        with patch('sys.argv', ['main.py', '--facebook-page', 'https://www.facebook.com/somepage']):
            args = parse_args()
            assert args.facebook_page == "https://www.facebook.com/somepage"
            assert args.url is None
            assert args.user is None

    def test_parse_args_custom_output(self):
        """Test parsing custom output directory."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--output', '/custom/path']):
            args = parse_args()
            assert args.output == "/custom/path"

    def test_parse_args_custom_workers(self):
        """Test parsing custom worker count."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--workers', '5']):
            args = parse_args()
            assert args.workers == 5

    def test_parse_args_custom_delay(self):
        """Test parsing custom delay."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--delay', '2.5']):
            args = parse_args()
            assert args.delay == 2.5

    def test_parse_args_all_options(self):
        """Test parsing all options together."""
        with patch('sys.argv', [
            'main.py',
            'https://www.tiktok.com/@user/video/123',
            '--output', '/tmp/downloads',
            '--workers', '8',
            '--delay', '0.5',
        ]):
            args = parse_args()
            assert args.url == "https://www.tiktok.com/@user/video/123"
            assert args.output == "/tmp/downloads"
            assert args.workers == 8
            assert args.delay == 0.5


# =============================================================================
# INTEGRATION-STYLE TESTS (CLI validation logic)
# =============================================================================


class TestMainValidation:
    """Test main() validation logic (without actual downloads)."""

    def test_main_no_input_modes(self):
        """Test that main exits with error when no input mode is provided."""
        with patch('sys.argv', ['main.py']):
            with patch('main.console.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    from main import main
                    main()
                assert exc_info.value.code == 1
                # Verify error message was printed
                calls = [str(call) for call in mock_print.call_args_list]
                assert any("Provide a URL, --batch FILE, --user USERNAME, or --facebook-page URL" in str(call) for call in calls)

    def test_main_multiple_input_modes(self):
        """Test that main exits with error when multiple input modes are provided."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--batch', 'urls.txt']):
            with patch('main.console.print'):
                with pytest.raises(SystemExit) as exc_info:
                    from main import main
                    main()
                assert exc_info.value.code == 1

    def test_main_invalid_workers_negative(self):
        """Test that negative workers value causes error."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--workers', '-1']):
            with patch('main.console.print'):
                with pytest.raises(SystemExit) as exc_info:
                    from main import main
                    main()
                assert exc_info.value.code == 1

    def test_main_invalid_workers_zero(self):
        """Test that zero workers value causes error."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--workers', '0']):
            with patch('main.console.print'):
                with pytest.raises(SystemExit) as exc_info:
                    from main import main
                    main()
                assert exc_info.value.code == 1

    def test_main_invalid_delay_negative(self):
        """Test that negative delay value causes error."""
        with patch('sys.argv', ['main.py', 'https://www.tiktok.com/@user/video/123', '--delay', '-1.0']):
            with patch('main.console.print'):
                with pytest.raises(SystemExit) as exc_info:
                    from main import main
                    main()
                assert exc_info.value.code == 1


class TestJitteredSleep:
    """Verify gaussian jitter helper respects floor and centers on mean."""

    def test_respects_floor_with_seeded_rng(self):
        import random

        rng = random.Random(42)
        # Pull a sample manually to confirm clamp wouldn't kick in for these params.
        for _ in range(50):
            with patch("downloader.time.sleep") as mock_sleep:
                _jittered_sleep(0.5, 0.1, 0.2, rng=rng)
                slept = mock_sleep.call_args[0][0]
                assert slept >= 0.2

    def test_clamp_when_gauss_negative(self):
        """Even if gauss produces a tiny/negative value, sleep gets the floor."""
        import random

        rng = random.Random(0)
        with patch("downloader.time.sleep") as mock_sleep:
            _jittered_sleep(mean=0.0, std=10.0, floor=0.5, rng=rng)
            slept = mock_sleep.call_args[0][0]
            assert slept >= 0.5

    def test_distribution_centered_on_mean(self):
        """Mean of 1000 samples should be within tolerance of mu (no floor clamp triggered)."""
        import random

        rng = random.Random(123)
        samples = []
        with patch("downloader.time.sleep") as mock_sleep:
            for _ in range(1000):
                _jittered_sleep(2.0, 0.3, 0.1, rng=rng)
                samples.append(mock_sleep.call_args[0][0])
        avg = sum(samples) / len(samples)
        # Loose tolerance — 1000 samples with sigma 0.3 → SE of mean ≈ 0.01
        assert abs(avg - 2.0) < 0.1


class TestClassifyError:
    """Map yt-dlp/HTTP error messages to ErrorKind strings."""

    def test_login_form_marker(self):
        assert _classify_error(Exception('id="login_form"')) == "login_required"

    def test_login_button_marker(self):
        assert _classify_error(Exception('id="loginbutton"')) == "login_required"

    def test_must_log_in_marker(self):
        assert _classify_error(Exception("You must log in to continue")) == "login_required"

    def test_login_required_phrase(self):
        assert _classify_error(Exception("Login required to view")) == "login_required"

    def test_private_message(self):
        assert _classify_error(Exception("This video is private")) == "private"

    def test_video_unavailable(self):
        assert _classify_error(Exception("Video unavailable")) == "not_found"

    def test_404_marker(self):
        assert _classify_error(Exception("Got HTTP 404")) == "not_found"

    def test_rate_limit_429(self):
        assert _classify_error(Exception("HTTP Error 429: Too Many Requests")) == "rate_limited"

    def test_rate_limit_phrase(self):
        assert _classify_error(Exception("rate limit exceeded")) == "rate_limited"

    def test_server_5xx(self):
        assert _classify_error(Exception("HTTP Error 503: Service Unavailable")) == "transient"

    def test_timeout(self):
        assert _classify_error(Exception("Read timeout occurred")) == "transient"

    def test_connection_reset(self):
        assert _classify_error(Exception("Connection reset by peer")) == "transient"

    def test_unknown_fallback(self):
        assert _classify_error(Exception("Some completely novel error")) == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
