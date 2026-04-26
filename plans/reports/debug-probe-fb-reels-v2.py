"""Variant probe: try different scroll mechanisms + storage_state from Chrome
to test whether the login wall (not the scroll method) is the gate.

Run: python plans/reports/debug-probe-fb-reels-v2.py [chrome]
  no arg  -> anonymous, using mouse-wheel + keyboard scrolls
  chrome  -> reuse logged-in Chrome cookies via persistent context
"""
from __future__ import annotations

import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = "https://www.facebook.com/duttonranchpplus/reels/"
MAX_SCROLLS = 6


def _clean(href: str) -> str | None:
    if "/reel/" in href:
        m = re.search(r"(https?://(?:www\.)?facebook\.com/reel/\d+)", href)
        return m.group(1) if m else None
    return None


def main() -> int:
    use_chrome = len(sys.argv) > 1 and sys.argv[1] == "chrome"
    print(f"[v2] target={URL}  chrome_profile={use_chrome}")
    seen: set[str] = set()
    per_scroll: list[int] = []

    with sync_playwright() as p:
        if use_chrome:
            user_data = os.path.join(
                os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data"
            )
            print(f"[v2] using user-data-dir: {user_data}")
            ctx = p.chromium.launch_persistent_context(
                user_data,
                headless=False,
                channel="chrome",
                args=["--profile-directory=Default"],
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        else:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

        page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3500)
        print(f"[v2] landed url: {page.url}")
        print(f"[v2] title:      {page.title()!r}")
        login = page.evaluate(
            "() => document.querySelectorAll('form[action*=login], #login_form, input[name=email]').length"
        )
        print(f"[v2] login_markers={login}")

        for i in range(MAX_SCROLLS):
            anchors = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            added = 0
            for h in anchors:
                c = _clean(h)
                if c and c not in seen:
                    seen.add(c)
                    added += 1
            per_scroll.append(added)
            print(f"[v2] scroll {i + 1}: anchors={len(anchors)} new={added} total={len(seen)}")

            # Mix scroll strategies — wheel, keyboard, and direct scrollTo
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(800)
            page.keyboard.press("End")
            page.wait_for_timeout(800)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2200)

        print(f"[v2] DONE total={len(seen)} per_scroll={per_scroll}")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
