"""Probe NeonNewZealand FB page across plain / reels / videos tabs to compare
against duttonranchpplus result (10-reel anonymous cap)."""
from __future__ import annotations

import re

from playwright.sync_api import sync_playwright

VARIANTS = [
    ("plain",       "https://www.facebook.com/NeonNewZealand"),
    ("reels-path",  "https://www.facebook.com/NeonNewZealand/reels/"),
    ("videos-path", "https://www.facebook.com/NeonNewZealand/videos"),
    ("sk-reels",    "https://www.facebook.com/NeonNewZealand?sk=reels_tab"),
]
MAX_SCROLLS = 8


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


def probe(p, label: str, url: str) -> None:
    print(f"\n=== {label}: {url}")
    seen: set[str] = set()
    per_scroll: list[int] = []
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="en-US",
    )
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(2000)
        print(f"   landed:  {page.url}")
        print(f"   title:   {page.title()!r}")
        login = page.evaluate(
            "() => document.querySelectorAll('form[action*=login], #login_form, input[name=email]').length"
        )
        print(f"   login_markers={login}")

        for i in range(MAX_SCROLLS):
            anchors = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            added = 0
            for h in anchors:
                c = _clean(h)
                if c and c not in seen:
                    seen.add(c)
                    added += 1
            per_scroll.append(added)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2500)
        anchor_count = page.evaluate("() => document.querySelectorAll('a[href]').length")
        video_anchor_count = page.evaluate(
            "() => Array.from(document.querySelectorAll('a[href]'))"
            ".map(a => a.href).filter(h => /\\/(reel|videos|watch)/.test(h)).length"
        )
        print(f"   per_scroll={per_scroll}  total_unique={len(seen)}")
        print(f"   final anchors={anchor_count} video_anchors={video_anchor_count}")
        if seen:
            for s in list(seen)[:3]:
                print(f"     - {s}")
    except Exception as e:
        print(f"   ERROR: {e!r}")
    finally:
        browser.close()


def main() -> None:
    with sync_playwright() as p:
        for label, url in VARIANTS:
            probe(p, label, url)


if __name__ == "__main__":
    main()
