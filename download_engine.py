"""QThread-based download engine with Qt signals for GUI progress updates."""

import os
import random
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from config import (
    HistoryRecord,
    add_history_record,
    get_platform_defaults,
    load_history,
)
from downloader import DownloadResult, download_video
from url_parser import detect_platform, extract_video_id


# Order matches yt-dlp's writethumbnail extension preference (jpg first on most
# extractors; webp is increasingly common; png is the rare case). TikTok's CDN
# returns thumbnails with no recognized image content-type, so yt-dlp lands
# them as ``.image`` — content is real JPEG/WebP bytes, only the extension is
# generic. We probe for it last so platforms with proper extensions still win.
_THUMB_EXTS = (".jpg", ".jpeg", ".webp", ".png", ".image")


def _resolve_thumbnail_sidecar(video_path: str | None) -> str | None:
    """Return path to a thumbnail sidecar next to ``video_path``, else ``None``.

    yt-dlp's ``writethumbnail`` lands beside the video as
    ``{basename}.{jpg|webp|png}``. We probe each extension in order; first
    match wins. ``os.path.exists`` is cheaper than ``os.listdir`` on uploader
    folders that may hold thousands of files.
    """
    if not video_path:
        return None
    base, _ext = os.path.splitext(video_path)
    for ext in _THUMB_EXTS:
        candidate = base + ext
        if os.path.exists(candidate):
            return candidate
    return None


class DownloadWorker(QThread):
    """Worker thread that downloads a single video and emits progress signals."""

    progress = Signal(str, float)       # (url, percent 0-100)
    finished_download = Signal(str, object)  # (url, DownloadResult)
    finished_with_info = Signal(str, object, object)  # (url, DownloadResult, info dict)

    def __init__(
        self, url: str, output_dir: str, cookie_browser: str | None = None,
        force_overwrite: bool = False,
        quality: str = "best",
        write_subs: bool = False,
        write_thumb: bool = False,
        cookies_file: str | None = None,
        tiktok_cookies_file: str | None = None,
        page_hint: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.url = url
        self.output_dir = output_dir
        self.cookie_browser = cookie_browser
        self.force_overwrite = force_overwrite
        self.quality = quality
        self.write_subs = write_subs
        self.write_thumb = write_thumb
        self.cookies_file = cookies_file
        self.tiktok_cookies_file = tiktok_cookies_file
        self.page_hint = page_hint
        self._cancelled = False
        self._info: dict | None = None

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
            # FB reels need auth cookies for current extractor HTML; route the
            # configured FB cookies.txt to yt-dlp on FB. Skip browser cookie DB
            # for FB to avoid the locked-DB issue while Chrome/Edge is running.
            # On TikTok, route the optional tiktok_cookies_file (file path wins
            # over browser DB inside the helper / get_ydl_opts).
            is_fb = detect_platform(self.url) == "facebook"
            cookies = None if is_fb else self.cookie_browser
            cookies_file = self.cookies_file if is_fb else self.tiktok_cookies_file
            result, info = download_video(
                self.url, self.output_dir,
                progress_hook=_progress_hook,
                cookie_browser=cookies,
                cookies_file=cookies_file,
                force_overwrite=self.force_overwrite,
                quality=self.quality,
                write_subs=self.write_subs,
                write_thumb=self.write_thumb,
                page_hint=self.page_hint,
                return_info=True,
            )
            self._info = info
        except Exception as e:
            result = DownloadResult(url=self.url, success=False, error=str(e))
            self._info = None
        self.finished_with_info.emit(self.url, result, self._info)
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
    history_changed = Signal()              # emitted after a HistoryRecord is persisted

    def __init__(
        self,
        output_dir: str = "./downloads",
        max_workers: int = 3,
        delay: float = 1.0,
        cookie_browser: str | None = None,
        delay_std: float = 0.3,
        delay_floor: float = 0.2,
        quality: str = "best",
        write_subs: bool = False,
        write_thumb: bool = False,
        history_max_entries: int | None = None,
        cookies_file: str | None = None,
        tiktok_cookies_file: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.delay = delay
        self.delay_std = delay_std
        self.delay_floor = delay_floor
        self.cookie_browser = cookie_browser
        self.cookies_file = cookies_file
        self.tiktok_cookies_file = tiktok_cookies_file
        self.quality = quality
        self.write_subs = write_subs
        self.write_thumb = write_thumb
        self.history_max_entries = history_max_entries
        self._queue: list[str] = []
        self._active: dict[str, DownloadWorker] = {}
        self._queued_urls: set[str] = set()  # Dedup: track all URLs ever added
        self._forced_urls: set[str] = set()  # URLs to download with overwrite (force)
        # Optional source-page URL per queued video — used by path_builder so
        # /reel/<id> downloads land in the page folder instead of unknown_uploader.
        self._url_to_page_hint: dict[str, str] = {}
        self._completed_count = 0
        self._total_count = 0
        self._history = load_history()

    def add_urls(
        self,
        urls: list[str],
        force: bool = False,
        page_hint: str | None = None,
    ) -> None:
        """Add URLs to download queue, skipping duplicates and already-downloaded.

        When `force=True`, the history check is bypassed and the worker is
        instructed to overwrite any existing file on disk. When `page_hint`
        is set (e.g. the source page URL for a batch of FB reels scraped
        from a profile), the same hint is associated with every queued URL
        so each download lands in `<platform>/<page>/`.
        """
        for url in urls:
            # Skip duplicate URLs already in queue or active
            if url in self._queued_urls:
                continue
            self._queued_urls.add(url)
            if page_hint:
                self._url_to_page_hint[url] = page_hint

            vid = extract_video_id(url)
            if not force and vid and vid in self._history:
                result = DownloadResult(url=url, success=True, video_id=vid, skipped=True)
                self.download_finished.emit(url, result)
                continue
            if force:
                self._forced_urls.add(url)
            self._queue.append(url)
        self._total_count += len(urls)
        self.queue_updated.emit(len(self._queue))
        self._start_next()

    def _start_next(self) -> None:
        """Spawn workers up to max_workers from queue. Fills all free slots at once."""
        started = 0
        while self._queue and len(self._active) < self.max_workers:
            url = self._queue.pop(0)
            force = url in self._forced_urls
            self._forced_urls.discard(url)
            worker = DownloadWorker(
                url, self.output_dir, self.cookie_browser,
                force_overwrite=force,
                quality=self.quality,
                write_subs=self.write_subs,
                write_thumb=self.write_thumb,
                cookies_file=self.cookies_file,
                tiktok_cookies_file=self.tiktok_cookies_file,
                page_hint=self._url_to_page_hint.get(url),
                parent=self,
            )
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
        info: dict | None = worker._info if worker else None
        if worker:
            worker.wait()
            worker.deleteLater()  # Prevent memory leak
        self._completed_count += 1
        # Stamp file_path from yt-dlp info so the GUI can offer
        # "Open in Explorer" without re-reading history.
        if result.success and not result.file_path and info:
            files = info.get("requested_downloads") or []
            first = files[0] if files else {}
            result.file_path = first.get("filepath") or info.get("filename")
        # Save to history on successful download (rich record + dedup-id set).
        if result.success and result.video_id:
            self._history.add(result.video_id)
            record = self._build_record(url, result, info)
            try:
                add_history_record(record, max_entries=self.history_max_entries)
                self.history_changed.emit()
            except Exception:
                # History persistence is best-effort — never fail the download.
                pass
        self.download_finished.emit(url, result)
        self.queue_updated.emit(len(self._queue))

        # Delay only applies between finishing one download and starting next replacement
        # This prevents TikTok rate-limiting, not slowing parallel downloads.
        # Platform-aware gaussian jitter: pick params from the *next* URL when known.
        if self._queue:
            next_url = self._queue[0]
            defaults = get_platform_defaults(next_url)
            # User-set self.delay overrides the per-platform mean only when explicitly set;
            # treat 1.0 (current default sentinel) and any positive value as user intent.
            mean = self.delay if self.delay > 0 else defaults.delay_mean
            std = self.delay_std if self.delay_std > 0 else defaults.delay_std
            floor = self.delay_floor if self.delay_floor > 0 else defaults.delay_floor
            sample = max(floor, random.gauss(mean, std))
            QTimer.singleShot(int(sample * 1000), self._start_next)
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

    def retry_url(self, url: str, force: bool = False, page_hint: str | None = None) -> None:
        """Re-queue a URL that previously finished (failed/cancelled/skipped).

        Removes URL from the dedup set so add_urls doesn't filter it out.
        Active downloads are left alone (caller should ensure URL is not active).
        When `force=True`, the history check is bypassed and the file is
        overwritten on disk. `page_hint` overrides any stored hint for `url`.
        """
        self._queued_urls.discard(url)
        self.add_urls([url], force=force, page_hint=page_hint)

    def retry_urls(
        self,
        urls: list[str],
        force: bool = False,
        page_hint: str | None = None,
    ) -> None:
        """Bulk re-queue previously finished URLs.

        See `retry_url` for the meaning of `force` and `page_hint`.
        """
        for url in urls:
            self._queued_urls.discard(url)
        self.add_urls(urls, force=force, page_hint=page_hint)

    def _build_record(
        self,
        url: str,
        result: DownloadResult,
        info: dict | None,
    ) -> HistoryRecord:
        """Compose a HistoryRecord from yt-dlp metadata + DownloadResult."""
        info = info or {}
        files = info.get("requested_downloads") or []
        first = files[0] if files else {}
        file_path = first.get("filepath") or info.get("filename")
        height = first.get("height") or info.get("height")
        if isinstance(height, int) and height > 0:
            quality_str = f"{height}p"
        else:
            quality_str = self.quality
        size = (
            first.get("filesize")
            or first.get("filesize_approx")
            or info.get("filesize")
            or info.get("filesize_approx")
        )
        description = info.get("description")
        if isinstance(description, str):
            description = description.strip() or None
        else:
            description = None
        return HistoryRecord(
            video_id=result.video_id or str(info.get("id", "")),
            platform=detect_platform(url),
            uploader=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
            title=result.title or info.get("title"),
            url=url,
            quality=quality_str,
            file_path=file_path,
            size_bytes=size if isinstance(size, int) else None,
            downloaded_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            description=description,
            thumbnail_path=_resolve_thumbnail_sidecar(file_path),
        )

    def clear_dedup(self, urls: list[str] | None = None) -> None:
        """Drop URLs from dedup tracking so they can be re-queued.

        Pass None to clear the entire dedup set (used when 'Clear All' wipes the table).
        """
        if urls is None:
            self._queued_urls.clear()
        else:
            for url in urls:
                self._queued_urls.discard(url)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def queue_count(self) -> int:
        return len(self._queue)
