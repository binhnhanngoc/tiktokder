"""TikTok-specific browser sub-panel — wires ChannelFetcher (yt-dlp flat playlist)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from channel_fetcher import ChannelFetcher
from gui.base_browser_panel import BaseBrowserPanel


class TikTokBrowserPanel(BaseBrowserPanel):
    """Browse TikTok channels/profiles via yt-dlp flat-playlist extraction."""

    def __init__(
        self,
        cookie_browser: str | None = None,
        cookies_file: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            placeholder="Paste TikTok channel URL (e.g. https://www.tiktok.com/@username)...",
            parent=parent,
        )
        self.cookie_browser = cookie_browser
        # Optional Netscape cookies.txt — when set, takes precedence over
        # cookie_browser inside ChannelFetcher's apply_cookies() call.
        self.cookies_file = cookies_file

    def _create_fetcher(self, url: str):
        return ChannelFetcher(
            url,
            cookie_browser=self.cookie_browser,
            cookies_file=self.cookies_file,
            parent=self,
        )

    def _start_status_text(self) -> str:
        return "Fetching TikTok videos..."
