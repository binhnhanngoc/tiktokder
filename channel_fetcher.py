"""QThread worker for fetching channel/page video listings via yt-dlp."""

from dataclasses import dataclass

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget
from PySide6.QtCore import QThread, Signal


@dataclass
class VideoInfo:
    """Metadata for a single video discovered from a channel."""

    url: str
    title: str
    duration: int | None  # seconds
    view_count: int | None
    upload_date: str | None  # YYYYMMDD
    video_id: str


class ChannelFetcher(QThread):
    """Fetches video list from a TikTok channel/profile URL using yt-dlp."""

    video_found = Signal(object)  # VideoInfo
    error = Signal(str)
    finished_fetch = Signal(int)  # total count

    def __init__(
        self,
        channel_url: str,
        cookie_browser: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.channel_url = channel_url
        self.cookie_browser = cookie_browser
        self._cancelled = False

    def run(self) -> None:
        """Extract video list from channel using flat playlist extraction."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "impersonate": ImpersonateTarget("chrome", "136"),
        }
        if self.cookie_browser:
            opts["cookiesfrombrowser"] = (self.cookie_browser,)

        count = 0
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.channel_url, download=False)
                if not info:
                    self.error.emit("No data returned for channel")
                    self.finished_fetch.emit(0)
                    return

                entries = info.get("entries", [])
                for entry in entries:
                    if self._cancelled:
                        break
                    if not entry:
                        continue

                    video_id = str(entry.get("id", ""))
                    url = entry.get("url") or entry.get("webpage_url") or ""
                    # Build full URL if only ID available (platform-aware)
                    if not url and video_id:
                        if "facebook.com" in self.channel_url or "fb.com" in self.channel_url or "fb.watch" in self.channel_url:
                            url = f"https://www.facebook.com/video/{video_id}"
                        else:
                            url = f"https://www.tiktok.com/@_/video/{video_id}"

                    video = VideoInfo(
                        url=url,
                        title=entry.get("title", "Untitled"),
                        duration=entry.get("duration"),
                        view_count=entry.get("view_count"),
                        upload_date=entry.get("upload_date"),
                        video_id=video_id,
                    )
                    self.video_found.emit(video)
                    count += 1

        except Exception as e:
            self.error.emit(str(e))

        self.finished_fetch.emit(count)

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True
