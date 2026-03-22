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
        results = []

        worker = DownloadWorker("http://x.com/1", "./downloads")
        worker.finished_download.connect(lambda url, r: results.append((url, r)))

        with patch("download_engine.download_video", return_value=fake_result):
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
        """Test that successful download adds video_id to history."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        result = DownloadResult(url="http://x.com/1", success=True, video_id="12345")

        with patch("download_engine.save_history") as mock_save:
            engine._on_worker_finished("http://x.com/1", result)

        assert "12345" in engine._history
        mock_save.assert_called_once()

    def test_failed_download_does_not_save_history(self):
        """Test that failed download does not modify history."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()

        result = DownloadResult(url="http://x.com/1", success=False, error="fail")

        with patch("download_engine.save_history") as mock_save:
            engine._on_worker_finished("http://x.com/1", result)

        assert len(engine._history) == 0
        mock_save.assert_not_called()
