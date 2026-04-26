"""Tests for download_engine.py - DownloadEngine queue and signal logic."""

from unittest.mock import patch, MagicMock

import pytest

from downloader import DownloadResult
from download_engine import DownloadEngine, DownloadWorker


class TestDownloadWorker:
    """Test DownloadWorker thread."""

    def test_worker_emits_finished(self):
        """Test worker emits finished signal with result."""
        fake_result = DownloadResult(url="http://x.com/1", success=True, video_id="1", title="Test")
        fake_info = {"id": "1", "title": "Test"}
        results = []

        worker = DownloadWorker("http://x.com/1", "./downloads")
        worker.finished_download.connect(lambda url, r: results.append((url, r)))

        # download_video now returns (result, info) when return_info=True.
        with patch("download_engine.download_video", return_value=(fake_result, fake_info)):
            worker.run()  # Run directly for testing

        assert len(results) == 1
        assert results[0][0] == "http://x.com/1"
        assert results[0][1].success is True

    def test_worker_cancel_flag(self):
        """Test that cancel sets internal flag."""
        worker = DownloadWorker("http://x.com/1", "./downloads")
        assert worker._cancelled is False
        worker.cancel()
        assert worker._cancelled is True


class TestDownloadEngine:
    """Test DownloadEngine queue management."""

    def test_add_urls_updates_queue(self):
        """Test adding URLs to queue."""
        engine = DownloadEngine(output_dir="./downloads", max_workers=3)
        queue_counts = []
        engine.queue_updated.connect(lambda c: queue_counts.append(c))

        # Patch _start_next to avoid actually spawning threads
        with patch.object(engine, "_start_next"):
            engine.add_urls(["http://a.com/1", "http://b.com/2"])

        assert engine._total_count == 2
        assert len(engine._queue) == 2

    def test_cancel_all_clears_queue(self):
        """Test cancel_all clears queue."""
        engine = DownloadEngine(output_dir="./downloads")

        with patch.object(engine, "_start_next"):
            engine.add_urls(["http://a.com/1", "http://b.com/2", "http://c.com/3"])

        engine.cancel_all()
        assert len(engine._queue) == 0

    def test_history_skip(self):
        """Test that URLs with video IDs in history are skipped."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = {"1234567890123456789"}

        skipped = []
        engine.download_finished.connect(lambda url, r: skipped.append((url, r)))

        with patch.object(engine, "_start_next"):
            engine.add_urls(["https://www.tiktok.com/@user/video/1234567890123456789"])

        assert len(skipped) == 1
        assert skipped[0][1].skipped is True
        # URL should NOT be in the queue (it was skipped)
        assert len(engine._queue) == 0

    def test_force_bypasses_history(self):
        """force=True must queue the URL even when its video ID is in history."""
        engine = DownloadEngine(output_dir="./downloads")
        url = "https://www.tiktok.com/@user/video/1234567890123456789"
        engine._history = {"1234567890123456789"}

        skipped = []
        engine.download_finished.connect(lambda u, r: skipped.append((u, r)))

        with patch.object(engine, "_start_next"):
            engine.add_urls([url], force=True)

        assert skipped == []  # not emitted as skipped
        assert engine._queue == [url]
        assert url in engine._forced_urls

    def test_retry_urls_force_propagates(self):
        """retry_urls(force=True) must mark URLs as forced even if in history."""
        engine = DownloadEngine(output_dir="./downloads")
        url = "https://www.tiktok.com/@user/video/9999999999999999999"
        engine._history = {"9999999999999999999"}
        engine._queued_urls = {url}  # simulate URL was previously skipped

        with patch.object(engine, "_start_next"):
            engine.retry_urls([url], force=True)

        assert engine._queue == [url]
        assert url in engine._forced_urls

    def test_non_history_url_added_to_queue(self):
        """Test that URLs not in history are queued normally."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        with patch.object(engine, "_start_next"):
            engine.add_urls(["https://www.tiktok.com/@user/video/9999999999999999999"])

        assert len(engine._queue) == 1

    def test_engine_properties(self):
        """Test active_count and queue_count properties."""
        engine = DownloadEngine(output_dir="./downloads")
        assert engine.active_count == 0
        assert engine.queue_count == 0

        with patch.object(engine, "_start_next"):
            engine.add_urls(["http://a.com/1"])

        assert engine.queue_count == 1

    def test_successful_download_saves_history(self):
        """Test that successful download adds video_id to history and persists a record."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        result = DownloadResult(url="http://x.com/1", success=True, video_id="12345")

        with patch("download_engine.add_history_record") as mock_add:
            engine._on_worker_finished("http://x.com/1", result)

        assert "12345" in engine._history
        mock_add.assert_called_once()

    def test_failed_download_does_not_save_history(self):
        """Test that failed download does not modify history."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        result = DownloadResult(url="http://x.com/1", success=False, error="fail")

        with patch("download_engine.add_history_record") as mock_add:
            engine._on_worker_finished("http://x.com/1", result)

        assert len(engine._history) == 0
        mock_add.assert_not_called()

    def test_history_changed_signal_fires_on_success(self):
        """Engine emits history_changed after persisting a record."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()
        emissions: list[bool] = []
        engine.history_changed.connect(lambda: emissions.append(True))

        result = DownloadResult(url="http://x.com/1", success=True, video_id="12345")
        with patch("download_engine.add_history_record"):
            engine._on_worker_finished("http://x.com/1", result)

        assert emissions == [True]

    def test_engine_uses_quality_from_init(self):
        """Engine forwards quality kwarg to spawned workers."""
        engine = DownloadEngine(output_dir="./downloads", quality="720p", write_subs=True)
        assert engine.quality == "720p"
        assert engine.write_subs is True
        assert engine.write_thumb is False

    def test_build_record_uses_info_metadata(self):
        """_build_record extracts platform/uploader/title from yt-dlp info."""
        engine = DownloadEngine(output_dir="./downloads", quality="best")
        result = DownloadResult(
            url="https://www.tiktok.com/@u/video/1",
            success=True,
            video_id="1",
            title="hello",
        )
        info = {
            "id": "1",
            "title": "hello",
            "uploader": "@u",
            "height": 720,
            "filesize_approx": 1024,
            "requested_downloads": [{"filepath": "/tmp/1.mp4", "height": 720}],
        }
        rec = engine._build_record("https://www.tiktok.com/@u/video/1", result, info)
        assert rec.video_id == "1"
        assert rec.platform == "tiktok"
        assert rec.uploader == "@u"
        assert rec.quality == "720p"
        assert rec.file_path == "/tmp/1.mp4"
        assert rec.downloaded_at is not None

    def test_add_urls_dedups_repeats(self):
        """Re-adding the same URL while it's tracked should not double-queue."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        with patch.object(engine, "_start_next"):
            engine.add_urls(["http://a.com/1"])
            engine.add_urls(["http://a.com/1"])

        assert len(engine._queue) == 1

    def test_retry_url_re_queues_after_failure(self):
        """retry_url must drop the dedup entry and re-queue the URL."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        with patch.object(engine, "_start_next"):
            engine.add_urls(["http://a.com/1"])
            # Simulate the engine finishing the URL (worker would have removed
            # itself from _active, but the URL stays in _queued_urls dedup set).
            engine._queue.clear()
            assert "http://a.com/1" in engine._queued_urls

            engine.retry_url("http://a.com/1")

        assert len(engine._queue) == 1
        assert engine._queue[0] == "http://a.com/1"

    def test_retry_urls_bulk(self):
        """retry_urls should re-queue every URL passed in."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        with patch.object(engine, "_start_next"):
            engine.add_urls(["http://a.com/1", "http://b.com/2"])
            engine._queue.clear()  # simulate both finished

            engine.retry_urls(["http://a.com/1", "http://b.com/2"])

        assert len(engine._queue) == 2

    def test_clear_dedup_specific_urls(self):
        """clear_dedup with explicit URLs should remove only those entries."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._queued_urls = {"http://a.com/1", "http://b.com/2"}

        engine.clear_dedup(["http://a.com/1"])

        assert engine._queued_urls == {"http://b.com/2"}

    def test_clear_dedup_all(self):
        """clear_dedup() with no args wipes the entire dedup set."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._queued_urls = {"http://a.com/1", "http://b.com/2"}

        engine.clear_dedup()

        assert engine._queued_urls == set()
