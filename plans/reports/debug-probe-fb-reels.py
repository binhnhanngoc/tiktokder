"""One-shot probe that mirrors FacebookFetcher.run() so we can see what the
Playwright scraper actually sees on the duttonranchpplus reels page.

Run:  python plans/reports/debug_probe_fb_reels.py
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.facebook.com/duttonranchpplus/reels/"
MAX_SCROLLS = 8
HEADLESS = True


def _clean(href: str) -> str | None:
    if "/reel/" in href:
        m = re.search(r"(https?://(?:www\.)?facebook\.com/reel/\d+)", href)
        return m.group(1) if m else None
    if "/videos/" in href:
        m = re.search(r"(https?://(?:www\.)?facebook\.com/[\w.]+/videos/\d+)", href)
        return m.group(1) if m else None
    if "/watch" in href and "v=" in href:
        m = re.search(r"(https?://(?:www\.)?facebook\.com/watch/?\?v=\d+)", href)
        return m.group(1) if m else None
    return None


def main() -> int:
    print(f"[probe] target: {URL}")
    print(f"[probe] max_scrolls={MAX_SCROLLS} headless={HEADLESS}")
    seen: set[str] = set()
    per_scroll: list[int] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            page = ctx.new_page()
            print("[probe] goto…")
            page.goto(URL, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(2000)
            print(f"[probe] landed url:  {page.url}")
            print(f"[probe] page title:  {page.title()!r}")

            login_marker_count = page.evaluate(
                "() => document.querySelectorAll('form[action*=login], #login_form, "
                "input[name=email][type=email]').length"
            )
            cookie_dialog = page.evaluate(
                "() => !!document.querySelector('[data-cookiebanner], [aria-label*=Allow], "
                "[role=dialog]')"
            )
            print(f"[probe] login markers: {login_marker_count}  cookie/dialog: {cookie_dialog}")

            for i in range(MAX_SCROLLS):
                links = page.eval_on_selector_all(
                    "a[href]", "els => els.map(e => e.href)"
                )
                added = 0
                for h in links:
                    c = _clean(h)
                    if c and c not in seen:
                        seen.add(c)
                        added += 1
                per_scroll.append(added)
                print(f"[probe] scroll {i + 1}/{MAX_SCROLLS}: anchors={len(links)} new_videos={added} total={len(seen)}")

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2500)

            sample = list(seen)[:5]
            print("[probe] sample urls:")
            for s in sample:
                print(f"   - {s}")

            html_len = page.evaluate("() => document.documentElement.outerHTML.length")
            anchor_count = page.evaluate("() => document.querySelectorAll('a[href]').length")
            video_anchors = page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href]'))"
                ".map(a => a.href).filter(h => /\\/(reel|videos|watch)/.test(h)).length"
            )
            print(f"[probe] html_len={html_len} anchors={anchor_count} video_anchors={video_anchors}")

            browser.close()
    except PlaywrightTimeout as e:
        print(f"[probe] TIMEOUT: {e}")
        return 2
    except Exception as e:
        print(f"[probe] ERROR: {e!r}")
        return 3

    print(f"[probe] DONE. total_unique_videos={len(seen)} per_scroll={per_scroll}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
