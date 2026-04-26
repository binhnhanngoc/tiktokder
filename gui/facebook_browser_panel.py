"""Facebook-specific browser sub-panel — wires Playwright-based FacebookFetcher."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from facebook_fetcher import FacebookFetcher, PLAYWRIGHT_AVAILABLE
from gui.base_browser_panel import BaseBrowserPanel


class FacebookBrowserPanel(BaseBrowserPanel):
    """Browse Facebook pages/profiles via Playwright scraping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            placeholder="Paste Facebook page URL (e.g. https://www.facebook.com/pagename)...",
            parent=parent,
        )

    def _create_fetcher(self, url: str):
        if not PLAYWRIGHT_AVAILABLE:
            self.status_label.setText(
                "Error: Facebook scraping requires Playwright. "
                "Install: pip install playwright && playwright install chromium"
            )
            return None
        return FacebookFetcher(url, parent=self)

    def _start_status_text(self) -> str:
        return "Fetching Facebook videos (browser scraping)..."
