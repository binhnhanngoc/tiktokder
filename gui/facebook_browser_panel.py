"""Facebook-specific browser sub-panel — wires Playwright-based FacebookFetcher."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QSpinBox, QWidget

from facebook_fetcher import FacebookFetcher, PLAYWRIGHT_AVAILABLE
from gui.base_browser_panel import BaseBrowserPanel
from gui.icons import icon


class FacebookBrowserPanel(BaseBrowserPanel):
    """Browse Facebook pages/profiles via Playwright scraping."""

    def __init__(
        self,
        cookies_file: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            placeholder="Paste Facebook page URL (e.g. https://www.facebook.com/pagename)...",
            parent=parent,
        )
        # Path to Netscape cookies.txt — when set, gets handed to FacebookFetcher
        # so the scrape runs as a logged-in session instead of anonymous.
        self.cookies_file = cookies_file

        # "Max scrolls" budget per fetch — exposed because Facebook lazy-loads
        # videos slowly and the right value depends on profile size.
        self.scrolls_spin = QSpinBox()
        self.scrolls_spin.setRange(1, 50)
        self.scrolls_spin.setValue(10)
        self.scrolls_spin.setPrefix("Scrolls: ")
        self.scrolls_spin.setToolTip("Max scroll iterations per fetch (higher = more videos, slower)")
        # Insert just before the Browse button (last item in the top row).
        self._top_row.insertWidget(self._top_row.count() - 1, self.scrolls_spin)

        # "Load more" resumes scraping from the current state — same URL,
        # but the fetcher seeds its dedup set with already-known URLs so it
        # only emits videos newly revealed by additional scrolling.
        self.load_more_btn = QPushButton("Load more")
        self.load_more_btn.setIcon(icon("mdi6.refresh"))
        self.load_more_btn.setEnabled(False)
        self.load_more_btn.clicked.connect(self._on_load_more)
        # Slot in after Deselect All (index 2) so it sits with the table-side
        # controls rather than the right-aligned Download button.
        self._bottom_row.insertWidget(2, self.load_more_btn)

    def _create_fetcher(self, url: str):
        if not PLAYWRIGHT_AVAILABLE:
            self.status_label.setText(
                "Error: Facebook scraping requires Playwright. "
                "Install: pip install playwright && playwright install chromium"
            )
            return None
        return FacebookFetcher(
            url,
            max_scrolls=self.scrolls_spin.value(),
            cookies_file=self.cookies_file,
            parent=self,
        )

    def _start_status_text(self) -> str:
        return "Fetching Facebook videos (browser scraping)..."

    def _on_load_more(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        if self._fetcher is not None and self._fetcher.isRunning():
            return
        if not PLAYWRIGHT_AVAILABLE:
            self.status_label.setText(
                "Error: Facebook scraping requires Playwright. "
                "Install: pip install playwright && playwright install chromium"
            )
            return

        seen = {v.url for v in self._videos}
        fetcher = FacebookFetcher(
            url,
            max_scrolls=self.scrolls_spin.value(),
            seed_seen_urls=seen,
            cookies_file=self.cookies_file,
            parent=self,
        )
        self.load_more_btn.setEnabled(False)
        self._start_fetcher(fetcher)

    def _on_fetch_done(self, total: int) -> None:
        super()._on_fetch_done(total)
        # Override the base "Found N" message so the user sees cumulative
        # progress across initial fetch + Load more clicks.
        cumulative = len(self._videos)
        if cumulative != total:
            self.status_label.setText(
                f"Found {cumulative} videos total (+{total} this fetch)"
            )
        self.load_more_btn.setEnabled(cumulative > 0)
