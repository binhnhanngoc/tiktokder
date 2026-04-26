"""Standalone verification: prove cookies-file path actually lifts the 10-reel cap.

Usage:
    python plans/reports/verify-fb-cookies-loaded.py path/to/cookies.txt [URL]

Compares two fetches against the same URL — anonymous vs cookies-loaded —
and prints how many reels each found. If the cookies file is valid for a
logged-in session, the cookies run should comfortably exceed 10.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from anywhere — add the project root (two parents up) to path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from facebook_fetcher import FacebookFetcher
from facebook_cookies import filter_facebook, load_netscape_cookies


def fetch(url: str, cookies_file: str | None, label: str, max_scrolls: int = 8) -> int:
    """Run FacebookFetcher synchronously (without Qt event loop) and return count."""
    print(f"\n=== {label}: cookies_file={cookies_file!r}")
    found: list[str] = []
    fetcher = FacebookFetcher(url, max_scrolls=max_scrolls, cookies_file=cookies_file)
    # Bypass QThread — call run() directly. Connect signals so we can count.
    fetcher.video_found.connect(lambda v: found.append(v.url))
    fetcher.error.connect(lambda msg: print(f"  [error] {msg}"))
    fetcher.run()
    print(f"  found={len(found)} reels")
    if found:
        for u in found[:3]:
            print(f"    - {u}")
    return len(found)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cookies_file = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else "https://www.facebook.com/duttonranchpplus/reels/"

    print(f"target: {url}")
    parsed = filter_facebook(load_netscape_cookies(cookies_file))
    print(f"cookies parsed (facebook.com only): {len(parsed)}")
    if parsed:
        names = sorted({c["name"] for c in parsed})[:8]
        print(f"  names sample: {names}")

    anon = fetch(url, None, "anonymous")
    auth = fetch(url, cookies_file, "with cookies")

    print("\n=== verdict")
    if auth > anon:
        print(f"  COOKIE INJECTION WORKING: anon={anon} -> with-cookies={auth}")
    elif auth == anon and anon > 0:
        print(f"  no improvement ({anon} vs {auth}) — cookies may be stale or this profile is fully open")
    else:
        print(f"  cookies didn't help: anon={anon}, with-cookies={auth}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
