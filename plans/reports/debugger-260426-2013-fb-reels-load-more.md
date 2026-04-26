# Debug Report — "Load more" stuck at 10 reels on `/duttonranchpplus/reels/`

**Date:** 2026-04-26
**URL:** https://www.facebook.com/duttonranchpplus/reels/
**Component:** `facebook_fetcher.py` + `gui/facebook_browser_panel.py`
**Status:** ROOT CAUSE FOUND — not a code bug, but an auth/cookie gap.

## TL;DR

For this URL, **no — you cannot load more than 10 videos** with the current Playwright scraper. Facebook serves only the first batch (10 reels) to **unauthenticated** sessions on a profile's `/reels/` tab, and disables the lazy-load infinite-scroll until login. Our headless Chromium has no FB cookie, so scroll fires but FB returns nothing new. "Load more" is blameless — the browser has nothing more to discover.

## Evidence (Playwright probes)

`plans/reports/debug-probe-fb-reels.py` (headless, our app's exact scroll mechanism):

```
landed url:    https://www.facebook.com/duttonranchpplus/reels/
title:         'Dutton Ranch Reels | Facebook'
login_markers: 3        cookie/dialog: True
scroll 1: anchors=24 new_videos=10 total=10
scroll 2-8: anchors=24 new_videos=0  total=10   ← DOM frozen
html_len=19_521_201   anchors=24   video_anchors=12
```

`debug-probe-fb-reels-v2.py` (headed, mouse-wheel + `End` key + `scrollTo`):

```
login_markers=4
scroll 1: new=10 total=10
scroll 2-6: new=0  total=10        ← same plateau, same DOM size
```

Anchor count never moves off 24. HTML size never grows. Whether headless or headed, whether wheel/keyboard/scrollTo, FB does not lazy-load any further cards. The 4 `login_markers` (login form / email input present in DOM) are the smoking gun: the page rendered an embedded login wall and gated more content behind it.

## Why "Load more" can't fix this

`FacebookFetcher.run()` (lines 81-121) does the right thing — scroll, harvest `a[href]`, dedup, re-scroll up to `max_scrolls`, exit on 3 empty streaks. The dedup-seeding for "Load more" (`gui/facebook_browser_panel.py:67-72`) also works. The bug is upstream of all of that: the browser session is anonymous, so the FB feed API stops at the first 10 cards. Any scroll loop, however clever, will harvest the same 10 anchors.

`README.md:99` already documents the asymmetry: cookie browser is wired for TikTok via yt-dlp, but **Facebook scraping ignores cookies** and always launches a fresh anonymous Chromium.

## Fix options (in increasing complexity)

### A. Surface the cap — small UX fix (recommended first)

Right now the user sees "Found 10 videos total" and clicks Load more repeatedly with no feedback that the source itself is exhausted. Detect when 2-3 consecutive Load-more clicks return zero new videos and display:

> Facebook returned no additional videos. The page may be limited to 10 reels for anonymous browsing — log-in via cookies is required to see more.

That is a 5-line change in `_on_fetch_done` of `gui/facebook_browser_panel.py` plus a `last_fetch_added` field on the panel.

### B. Pass real Chrome cookies into Playwright (proper fix)

Mirror the TikTok cookie setting for Facebook. Two paths:

1. **`launch_persistent_context`** with the user's Chrome `User Data\Default` directory — easiest to wire, but locks Chrome out while running and exposes the whole profile.
2. **Export cookies from Chrome/Firefox** (e.g. `yt-dlp --cookies-from-browser chrome --print-to-file ...` or `browser_cookie3`) and inject them via `context.add_cookies(...)` before `page.goto`. Cleaner, no profile coupling.

Either way, after auth FB will lazy-load the full reel feed and the existing scroll loop will scale to hundreds of items.

### C. Switch reels resolution to yt-dlp's flat playlist

yt-dlp now supports `https://www.facebook.com/{name}/reels/` as a playlist URL (Generic-extractor + dash). Worth a probe (`yt-dlp -J --flat-playlist <url>`) — if it works it sidesteps Playwright entirely for the listing step.

## Recommendation

Ship **A** today (1-line UX fix prevents the "looks broken" perception), then plan **B** for the next session — extending the cookie-browser setting to also feed the Facebook fetcher is the only durable answer to the 10-reel cap.

## Artefacts left in repo

- `plans/reports/debug-probe-fb-reels.py` — anonymous headless probe
- `plans/reports/debug-probe-fb-reels-v2.py` — headed + mixed-scroll probe (also supports `chrome` arg for persistent-context test)

Both are diagnostic-only and safe to delete.

## Unresolved questions

1. Does this same 10-reel cap apply to **all** profiles, or only some (algorithmic / region-gated)? Worth a second probe on a different page before we surface the message in (A).
2. Does FB cap differently on `?sk=reels_tab` vs `/reels/` paths? Our `_normalize_url` skips appending `sk=reels_tab` because `/reels` already matches — quick to test if it changes the cap.
3. For (B), do we want a single cookie source for both TikTok and Facebook, or per-platform? The Settings panel currently scopes the dropdown to TikTok in the help text.

**Status:** DONE
**Summary:** Confirmed via two Playwright probes that FB hard-caps anonymous sessions at 10 reels for this URL — DOM never grows past 24 anchors regardless of scroll strategy. "Load more" code is correct; the gap is missing cookie-auth in the Facebook scraper path.
