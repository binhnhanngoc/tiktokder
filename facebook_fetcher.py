"""Fetch video URLs from Facebook profiles/pages using Playwright browser automation.

yt-dlp cannot list videos from Facebook profiles — only download individual videos.
This module uses Playwright to scrape reel/video links from a Facebook profile page,
then emits them through the same VideoInfo signal interface as ChannelFetcher.
"""

import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from PySide6.QtCore import QThread, Signal

from channel_fetcher import VideoInfo


# Matches Facebook reel/video URLs in href attributes
_VIDEO_LINK_RE = re.compile(
    r"https?://(?:www\.)?facebook\.com/(?:reel|watch/?\?v=|[\w.]+/videos)/\S+"
)


class FacebookFetcher(QThread):
    """Scrape video/reel URLs from a Facebook profile page via Playwright."""

    video_found = Signal(object)  # VideoInfo
    error = Signal(str)
    finished_fetch = Signal(int)  # total count

    def __init__(
        self,
        page_url: str,
        max_scrolls: int = 10,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.page_url = page_url
        self.max_scrolls = max_scrolls
        self._cancelled = False

    def run(self) -> None:
        """Launch headless browser, navigate to profile, scrape video links."""
        count = 0
        seen_urls: set[str] = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate to the profile's reels/videos tab
                url = self._normalize_url(self.page_url)
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.wait_for_timeout(2000)

                # Scroll to load more content
                for _ in range(self.max_scrolls):
                    if self._cancelled:
                        break

                    # Extract all video links on current page
                    links = page.eval_on_selector_all(
                        "a[href]", "els => els.map(e => e.href)"
                    )
                    new_found = False
                    for href in links:
                        if self._cancelled:
                            break
                        # Clean URL: strip query params for dedup
                        clean = self._clean_video_url(href)
                        if clean and clean not in seen_urls:
                            seen_urls.add(clean)
                            new_found = True
                            video_id = self._extract_id(clean)
                            video = VideoInfo(
                                url=clean,
                                title=f"Facebook video {video_id}",
                                duration=None,
                                view_count=None,
                                upload_date=None,
                                video_id=video_id,
                            )
                            self.video_found.emit(video)
                            count += 1

                    # Scroll down for more content
                    page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                    page.wait_for_timeout(1500)

                    # Stop if no new videos found after scroll
                    if not new_found:
                        break

                browser.close()

        except PlaywrightTimeout:
            self.error.emit("Timed out loading Facebook page")
        except Exception as e:
            self.error.emit(f"Facebook scraping failed: {e}")

        self.finished_fetch.emit(count)

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Ensure URL points to reels/videos tab if it's a plain profile URL."""
        url = url.strip()
        # If already on reels/videos tab, use as-is
        if "sk=reels" in url or "sk=videos" in url or "/reels" in url or "/videos" in url:
            return url
        # Append reels tab for profile URLs
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}sk=reels_tab"

    @staticmethod
    def _clean_video_url(href: str) -> str | None:
        """Extract and clean a Facebook video/reel URL, or return None if not a video."""
        if "/reel/" in href:
            # Extract: facebook.com/reel/DIGITS
            match = re.search(r"(https?://(?:www\.)?facebook\.com/reel/\d+)", href)
            return match.group(1) if match else None
        if "/videos/" in href:
            match = re.search(r"(https?://(?:www\.)?facebook\.com/[\w.]+/videos/\d+)", href)
            return match.group(1) if match else None
        if "/watch" in href and "v=" in href:
            match = re.search(r"(https?://(?:www\.)?facebook\.com/watch/?\?v=\d+)", href)
            return match.group(1) if match else None
        return None

    @staticmethod
    def _extract_id(url: str) -> str:
        """Extract numeric video/reel ID from URL."""
        match = re.search(r"/(\d+)/?$", url)
        if match:
            return match.group(1)
        match = re.search(r"v=(\d+)", url)
        if match:
            return match.group(1)
        return "unknown"
