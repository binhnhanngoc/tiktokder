"""Tests for channel_fetcher.py - VideoInfo dataclass and ChannelFetcher logic."""

from unittest.mock import patch, MagicMock

import pytest

from channel_fetcher import VideoInfo, ChannelFetcher


class TestVideoInfo:
    """Test VideoInfo dataclass."""

    def test_create_video_info(self):
        v = VideoInfo(
            url="https://www.tiktok.com/@user/video/123",
            title="Test Video",
            duration=30,
            view_count=1000,
            upload_date="20250301",
            video_id="123",
        )
        assert v.url == "https://www.tiktok.com/@user/video/123"
        assert v.title == "Test Video"
        assert v.duration == 30
        assert v.view_count == 1000
        assert v.upload_date == "20250301"
        assert v.video_id == "123"

    def test_video_info_nullable_fields(self):
        v = VideoInfo(
            url="https://example.com",
            title="No metadata",
            duration=None,
            view_count=None,
            upload_date=None,
            video_id="456",
        )
        assert v.duration is None
        assert v.view_count is None
        assert v.upload_date is None
        assert v.quality is None  # default

    def test_video_info_quality_field(self):
        v = VideoInfo(
            url="https://example.com",
            title="HD clip",
            duration=10,
            view_count=None,
            upload_date=None,
            video_id="789",
            quality="720p",
        )
        assert v.quality == "720p"


class TestQualityFromEntry:
    """quality_from_entry helper used by fetchers to populate VideoInfo.quality."""

    def test_height_int_returns_p_string(self):
        from channel_fetcher import quality_from_entry
        assert quality_from_entry({"height": 720}) == "720p"

    def test_format_string_height_token(self):
        from channel_fetcher import quality_from_entry
        assert quality_from_entry({"format": "mp4 1080p"}) == "1080p"

    def test_no_metadata_returns_none(self):
        from channel_fetcher import quality_from_entry
        assert quality_from_entry({}) is None

    def test_height_zero_falls_through(self):
        from channel_fetcher import quality_from_entry
        assert quality_from_entry({"height": 0}) is None


class TestChannelFetcher:
    """Test ChannelFetcher with mocked yt-dlp."""

    def test_fetcher_extracts_videos(self):
        """Test that fetcher parses yt-dlp flat playlist output."""
        fake_entries = [
            {
                "id": "111",
                "url": "https://www.tiktok.com/@user/video/111",
                "title": "Video One",
                "duration": 15,
                "view_count": 500,
                "upload_date": "20250101",
            },
            {
                "id": "222",
                "url": "https://www.tiktok.com/@user/video/222",
                "title": "Video Two",
                "duration": 30,
                "view_count": 1000,
                "upload_date": "20250201",
            },
        ]
        fake_info = {"entries": fake_entries}

        found_videos = []

        def capture_video(video):
            found_videos.append(video)

        fetcher = ChannelFetcher("https://www.tiktok.com/@testuser")

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = fake_info
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.video_found.connect(capture_video)
            fetcher.run()  # Run directly (not in thread) for testing

        assert len(found_videos) == 2
        assert found_videos[0].video_id == "111"
        assert found_videos[0].title == "Video One"
        assert found_videos[1].video_id == "222"

    def test_fetcher_handles_empty_entries(self):
        """Test fetcher with no videos."""
        fake_info = {"entries": []}

        fetcher = ChannelFetcher("https://www.tiktok.com/@emptyuser")
        results = []

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = fake_info
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.video_found.connect(lambda v: results.append(v))
            fetcher.run()

        assert len(results) == 0

    def test_fetcher_handles_error(self):
        """Test fetcher emits error signal on exception."""
        fetcher = ChannelFetcher("https://www.tiktok.com/@baduser")
        errors = []

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = Exception("Network error")
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.error.connect(lambda msg: errors.append(msg))
            fetcher.run()

        assert len(errors) == 1
        assert "Network error" in errors[0]

    def test_fetcher_builds_url_from_id(self):
        """Test that fetcher constructs URL when only ID is available."""
        fake_entries = [{"id": "999", "title": "ID Only"}]
        fake_info = {"entries": fake_entries}
        found = []

        fetcher = ChannelFetcher("https://www.tiktok.com/@user")

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = fake_info
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.video_found.connect(lambda v: found.append(v))
            fetcher.run()

        assert len(found) == 1
        assert "999" in found[0].url

    def test_fetcher_cancellation(self):
        """Test that cancellation stops processing."""
        fake_entries = [
            {"id": str(i), "url": f"https://example.com/{i}", "title": f"V{i}"}
            for i in range(10)
        ]
        fake_info = {"entries": fake_entries}
        found = []

        fetcher = ChannelFetcher("https://www.tiktok.com/@user")
        fetcher.cancel()  # Cancel before running

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = fake_info
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.video_found.connect(lambda v: found.append(v))
            fetcher.run()

        assert len(found) == 0

    def test_fetcher_cookie_browser_option(self):
        """Test that cookie browser option is passed to yt-dlp."""
        fetcher = ChannelFetcher("https://www.tiktok.com/@user", cookie_browser="chrome")
        fake_info = {"entries": []}

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = fake_info
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.run()

            call_opts = mock_ydl_cls.call_args[0][0]
            assert call_opts["cookiesfrombrowser"] == ("chrome",)

    def test_fetcher_no_data_returned(self):
        """Test fetcher handles None return from extract_info."""
        fetcher = ChannelFetcher("https://www.tiktok.com/@ghost")
        errors = []

        with patch("channel_fetcher.yt_dlp.YoutubeDL") as mock_ydl_cls:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = None
            mock_ydl.__enter__ = lambda self: mock_ydl
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl_cls.return_value = mock_ydl

            fetcher.error.connect(lambda msg: errors.append(msg))
            fetcher.run()

        assert len(errors) == 1
        assert "No data" in errors[0]
