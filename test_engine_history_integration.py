"""Integration tests: DownloadEngine builds + persists HistoryRecord on success.

Stubs `download_video` so no network access happens; asserts that the engine
calls `add_history_record` with fields derived from the yt-dlp info dict, and
that `history_changed` fires.
"""

from unittest.mock import patch

import pytest

from downloader import DownloadResult
from download_engine import DownloadEngine, DownloadWorker


class TestEngineHistoryPersistence:
    def test_engine_persists_record_on_success(self):
        """Successful download triggers add_history_record with rich fields."""
        engine = DownloadEngine(output_dir="./downloads", quality="best")
        engine._history = set()

        url = "https://www.tiktok.com/@u/video/1234567890123456789"
        result = DownloadResult(
            url=url, success=True, video_id="1234567890123456789", title="hello"
        )

        # Simulate worker._info populated by run().
        class _FakeWorker:
            def __init__(self):
                self._info = {
                    "id": "1234567890123456789",
                    "title": "hello",
                    "uploader": "@u",
                    "height": 720,
                    "filesize_approx": 2048,
                    "requested_downloads": [
                        {"filepath": "/tmp/hello [123456].mp4", "height": 720}
                    ],
                }
            def wait(self):
                pass
            def deleteLater(self):
                pass

        engine._active[url] = _FakeWorker()
        with patch("download_engine.add_history_record") as mock_add:
            engine._on_worker_finished(url, result)

        assert mock_add.called
        rec = mock_add.call_args[0][0]
        assert rec.video_id == "1234567890123456789"
        assert rec.platform == "tiktok"
        assert rec.uploader == "@u"
        assert rec.title == "hello"
        assert rec.url == url
        assert rec.quality == "720p"
        assert rec.file_path == "/tmp/hello [123456].mp4"
        assert rec.size_bytes == 2048

    def test_engine_emits_history_changed_signal(self):
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = set()
        emitted = []
        engine.history_changed.connect(lambda: emitted.append(True))

        result = DownloadResult(url="http://x/1", success=True, video_id="1")

        with patch("download_engine.add_history_record"):
            engine._on_worker_finished("http://x/1", result)

        assert emitted == [True]

    def test_engine_dedup_skips_v2_recorded_id(self):
        """When video_id is in the in-memory dedup set, queued URL is skipped."""
        engine = DownloadEngine(output_dir="./downloads")
        engine._history = {"1234567890123456789"}

        skipped = []
        engine.download_finished.connect(lambda u, r: skipped.append((u, r)))

        with patch.object(engine, "_start_next"):
            engine.add_urls(["https://www.tiktok.com/@u/video/1234567890123456789"])

        assert len(skipped) == 1
        assert skipped[0][1].skipped is True


class TestWorkerForwardsQuality:
    def test_worker_passes_quality_to_download_video(self):
        """DownloadWorker.run forwards quality/subs/thumb kwargs to download_video."""
        fake_result = DownloadResult(url="http://x/1", success=True, video_id="1")

        worker = DownloadWorker(
            "http://x/1", "./downloads",
            quality="720p", write_subs=True, write_thumb=False,
        )
        with patch("download_engine.download_video", return_value=(fake_result, {})) as mock_dl:
            worker.run()

        kwargs = mock_dl.call_args.kwargs
        assert kwargs["quality"] == "720p"
        assert kwargs["write_subs"] is True
        assert kwargs["write_thumb"] is False
        assert kwargs["return_info"] is True
