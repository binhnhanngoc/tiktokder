"""TikTok-specific browser sub-panel — wires ChannelFetcher (yt-dlp flat playlist)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from channel_fetcher import ChannelFetcher
from gui.base_browser_panel import BaseBrowserPanel


class TikTokBrowserPanel(BaseBrowserPanel):
    """Browse TikTok channels/profiles via yt-dlp flat-playlist extraction."""

    def __init__(self, cookie_browser: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(
            placeholder="Paste TikTok channel URL (e.g. https://www.tiktok.com/@username)...",
            parent=parent,
        )
        self.cookie_browser = cookie_browser

    def _create_fetcher(self, url: str):
        return ChannelFetcher(url, self.cookie_browser, parent=self)

    def _start_status_text(self) -> str:
        return "Fetching TikTok videos..."
