"""Fetch video URLs from Facebook profiles/pages using Playwright browser automation.

yt-dlp cannot list videos from Facebook profiles — only download individual videos.
This module uses Playwright to scrape reel/video links from a Facebook profile page,
then emits them through the same VideoInfo signal interface as ChannelFetcher.

Playwright is optional — when missing, FacebookFetcher emits an error signal instead.
"""

import re

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeout = Exception  # fallback so except clause doesn't raise NameError

from PySide6.QtCore import QThread, Signal

from channel_fetcher import VideoInfo
from facebook_cookies import filter_facebook, load_netscape_cookies


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
        seed_seen_urls: set[str] | None = None,
        cookies_file: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.page_url = page_url
        self.max_scrolls = max_scrolls
        # Pre-seeded dedup set lets "Load more" suppress already-shown videos
        # so the loop only emits new ones once Facebook lazy-loads further.
        self._seed_seen_urls = set(seed_seen_urls) if seed_seen_urls else set()
        # Optional Netscape cookies.txt — when set, fetcher loads it as a
        # logged-in FB session, which lifts the 10-reel anonymous cap.
        self.cookies_file = cookies_file
        self._cancelled = False

    def run(self) -> None:
        """Launch headless browser, navigate to profile, scrape video links."""
        if not PLAYWRIGHT_AVAILABLE:
            self.error.emit(
                "Facebook page scraping requires Playwright. "
                "Install with: pip install playwright && playwright install chromium"
            )
            self.finished_fetch.emit(0)
            return

        count = 0
        # Seed with already-known URLs so "Load more" suppresses duplicates.
        seen_urls: set[str] = set(self._seed_seen_urls)
        # Allow a few empty iterations before giving up — Facebook's lazy
        # loader is slow and the first scrolls after a "Load more" usually
        # see only the cached cards before new ones get rendered.
        empty_streak = 0
        EMPTY_TOLERANCE = 3

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                # A real-looking context plus optional cookies — when the user
                # supplies a Netscape cookies.txt we inject it before goto so
                # the very first request is authenticated and FB serves the
                # full reel feed instead of the anonymous 10-card preview.
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                    locale="en-US",
                )
                self._inject_cookies_if_any(context)
                page = context.new_page()

                # Navigate to the profile's reels/videos tab.
                # Use ``domcontentloaded`` instead of ``networkidle`` because
                # logged-in FB pages stream presence/notification traffic
                # continuously and never go idle, which would deadline-kill
                # the goto when cookies are in play. The fixed 3.5s settle
                # below replaces the lost idle-wait.
                url = self._normalize_url(self.page_url)
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(3500)

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

                    # Scroll to absolute bottom — triggers FB's intersection
                    # observer more reliably than a fixed-pixel scrollBy.
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2500)

                    if new_found:
                        empty_streak = 0
                    else:
                        empty_streak += 1
                        if empty_streak >= EMPTY_TOLERANCE:
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

    def _inject_cookies_if_any(self, context) -> None:
        """Load cookies.txt into ``context`` if the user configured a file.

        Failures are surfaced via ``error.emit`` but don't abort — the fetcher
        still tries the page anonymously, which at worst yields the same
        preview cap as before. That keeps the feature graceful when the file
        path is stale or the user typo'd it.
        """
        if not self.cookies_file:
            return
        try:
            cookies = filter_facebook(load_netscape_cookies(self.cookies_file))
        except Exception as e:
            self.error.emit(f"Could not read cookies file: {e}")
            return
        if not cookies:
            self.error.emit(
                "No facebook.com cookies found in the configured cookies file. "
                "Continuing anonymously (10-reel cap may apply)."
            )
            return
        try:
            context.add_cookies(cookies)
        except Exception as e:
            self.error.emit(f"Could not apply cookies: {e}")

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
