"""QThread-based download engine with Qt signals for GUI progress updates."""

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from config import load_history, save_history
from downloader import download_video, DownloadResult
from url_parser import extract_video_id, detect_platform


class DownloadWorker(QThread):
    """Worker thread that downloads a single video and emits progress signals."""

    progress = Signal(str, float)       # (url, percent 0-100)
    finished_download = Signal(str, object)  # (url, DownloadResult)

    def __init__(
        self, url: str, output_dir: str, cookie_browser: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.cookie_browser = cookie_browser
        self._cancelled = False

    def run(self) -> None:
        """Execute download in background thread."""
        def _progress_hook(d: dict) -> None:
            if self._cancelled:
                raise Exception("Download cancelled")
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    pct = (downloaded / total) * 100
                    self.progress.emit(self.url, pct)

        try:
            # Skip cookies for Facebook — public reels don't need them,
            # and yt-dlp can't copy Chrome/Edge cookie DB while browser is running
            cookies = self.cookie_browser if detect_platform(self.url) != "facebook" else None
            result = download_video(
                self.url, self.output_dir,
                progress_hook=_progress_hook,
                cookie_browser=cookies,
            )
        except Exception as e:
            result = DownloadResult(url=self.url, success=False, error=str(e))
        self.finished_download.emit(self.url, result)

    def cancel(self) -> None:
        """Request cancellation (checked in progress hook)."""
        self._cancelled = True


class DownloadEngine(QObject):
    """Manages a queue of downloads with configurable concurrency."""

    download_started = Signal(str)          # url
    download_progress = Signal(str, float)  # url, percent
    download_finished = Signal(str, object) # url, DownloadResult
    all_finished = Signal()
    queue_updated = Signal(int)             # remaining count

    def __init__(
        self,
        output_dir: str = "./downloads",
        max_workers: int = 3,
        delay: float = 1.0,
        cookie_browser: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.delay = delay
        self.cookie_browser = cookie_browser
        self._queue: list[str] = []
        self._active: dict[str, DownloadWorker] = {}
        self._queued_urls: set[str] = set()  # Dedup: track all URLs ever added
        self._completed_count = 0
        self._total_count = 0
        self._history = load_history()

    def add_urls(self, urls: list[str]) -> None:
        """Add URLs to download queue, skipping duplicates and already-downloaded."""
        for url in urls:
            # Skip duplicate URLs already in queue or active
            if url in self._queued_urls:
                continue
            self._queued_urls.add(url)

            vid = extract_video_id(url)
            if vid and vid in self._history:
                result = DownloadResult(url=url, success=True, video_id=vid, skipped=True)
                self.download_finished.emit(url, result)
                continue
            self._queue.append(url)
        self._total_count += len(urls)
        self.queue_updated.emit(len(self._queue))
        self._start_next()

    def _start_next(self) -> None:
        """Spawn workers up to max_workers from queue. Fills all free slots at once."""
        started = 0
        while self._queue and len(self._active) < self.max_workers:
            url = self._queue.pop(0)
            worker = DownloadWorker(url, self.output_dir, self.cookie_browser, parent=self)
            worker.progress.connect(self._on_progress)
            worker.finished_download.connect(self._on_worker_finished)
            self._active[url] = worker
            self.download_started.emit(url)
            worker.start()
            started += 1
        return started

    @Slot(str, float)
    def _on_progress(self, url: str, percent: float) -> None:
        self.download_progress.emit(url, percent)

    @Slot(str, object)
    def _on_worker_finished(self, url: str, result: DownloadResult) -> None:
        """Handle worker completion: clean up and schedule next."""
        worker = self._active.pop(url, None)
        if worker:
            worker.wait()
            worker.deleteLater()  # Prevent memory leak
        self._completed_count += 1
        # Save to history on successful download
        if result.success and result.video_id:
            self._history.add(result.video_id)
            save_history(self._history)
        self.download_finished.emit(url, result)
        self.queue_updated.emit(len(self._queue))

        # Delay only applies between finishing one download and starting next replacement
        # This prevents TikTok rate-limiting, not slowing parallel downloads
        if self._queue:
            if self.delay > 0:
                QTimer.singleShot(int(self.delay * 1000), self._start_next)
            else:
                self._start_next()
        elif not self._active:
            self.all_finished.emit()

    def cancel_url(self, url: str) -> None:
        """Cancel a specific active download."""
        worker = self._active.get(url)
        if worker:
            worker.cancel()

    def cancel_all(self) -> None:
        """Cancel all active downloads and clear queue."""
        self._queue.clear()
        for worker in self._active.values():
            worker.cancel()
        self.queue_updated.emit(0)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def queue_count(self) -> int:
        return len(self._queue)
