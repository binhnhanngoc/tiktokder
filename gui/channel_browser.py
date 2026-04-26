"""Channel/Page browser — thin QTabWidget wrapper around platform sub-panels.

Re-exports `ChannelBrowser` so existing `MainWindow` imports keep working.
The wrapper auto-selects the matching sub-panel when an external caller
fills `url_input` and calls `_on_browse()` (the cross-link from MainWindow).
"""

from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from gui.facebook_browser_panel import FacebookBrowserPanel
from gui.tiktok_browser_panel import TikTokBrowserPanel
from url_parser import detect_platform


class ChannelBrowser(QWidget):
    """Two-tab browser: TikTok and Facebook panels with independent state."""

    download_requested = Signal(list)  # list[str] of URLs

    def __init__(
        self,
        cookie_browser: str | None = None,
        cookies_file: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.cookie_browser = cookie_browser
        self.cookies_file = cookies_file

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self.tiktok_panel = TikTokBrowserPanel(cookie_browser=cookie_browser)
        self.facebook_panel = FacebookBrowserPanel(cookies_file=cookies_file)
        self._tabs.addTab(self.tiktok_panel, "TikTok")
        self._tabs.addTab(self.facebook_panel, "Facebook")
        layout.addWidget(self._tabs)

        self.tiktok_panel.download_requested.connect(self.download_requested.emit)
        self.facebook_panel.download_requested.connect(self.download_requested.emit)

    @property
    def url_input(self):
        """Active sub-panel's URL input — keeps ``MainWindow._on_channel_url`` working."""
        return self._active_panel().url_input

    def _active_panel(self):
        return self._tabs.currentWidget()

    def _on_browse(self) -> None:
        """Dispatch browse to the panel matching the URL platform.

        Detects platform from the URL currently typed in the active panel and
        switches tabs if needed before triggering the per-panel browse.
        """
        url = self._active_panel().url_input.text().strip()
        target_panel = self._panel_for_url(url) or self._active_panel()
        if target_panel is not self._active_panel():
            # Move the URL across so the user sees it on the right sub-tab.
            target_panel.url_input.setText(url)
            self._tabs.setCurrentWidget(target_panel)
        target_panel._on_browse()

    def _panel_for_url(self, url: str):
        platform = detect_platform(url)
        if platform == "facebook":
            return self.facebook_panel
        if platform == "tiktok":
            return self.tiktok_panel
        return None

    @Slot(str)
    def set_cookie_browser(self, value: str | None) -> None:
        """Propagate cookie-browser setting to TikTok panel (FB scraper ignores it)."""
        self.cookie_browser = value
        self.tiktok_panel.cookie_browser = value

    @Slot(str)
    def set_cookies_file(self, value: str | None) -> None:
        """Propagate cookies.txt path to the Facebook panel (TikTok ignores it)."""
        self.cookies_file = value
        self.facebook_panel.cookies_file = value
