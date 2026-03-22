# Code Review: Facebook Video Download Feature

**Date:** 2026-03-22
**Reviewer:** code-reviewer
**Scope:** Facebook URL support added to url_parser, CLI, GUI, and tests

---

## Scope

- **Files reviewed:** `url_parser.py`, `main.py`, `gui/url_input_panel.py`, `gui/channel_browser.py`, `gui/main_window.py`, `test_tiktokder.py`, `downloader.py`, `download_engine.py`, `channel_fetcher.py`, `config.py`
- **LOC changed:** ~120 (across 6 files)
- **Tests:** 102/102 passing
- **Focus:** Regex correctness, backward compatibility, edge cases, security

---

## Overall Assessment

Solid implementation. Facebook URL support added cleanly alongside existing TikTok functionality. Backward compatibility preserved. Good test coverage for the new patterns. A few regex edge cases and one validation gap need attention.

---

## Critical Issues

### 1. FACEBOOK_URL_PATTERN lacks end-of-string anchor (Medium-High)

**File:** `url_parser.py:24-28`

The regex uses `re.match()` (start-anchored) but has no `$` end anchor, combined with `\S*` which matches greedily. This causes two problems:

**a) Matches bare domain with no path:**
```python
validate_facebook_url("https://www.facebook.com")  # True -- too permissive
```

**b) Partial prefix matching on injected domains:**
```python
validate_facebook_url("https://www.facebook.com.evil.com/videos/123")  # True
validate_facebook_url("https://fb.watch.evil.com/abc")  # True
```

The match succeeds because it matches `https://www.facebook.com` as a prefix, ignoring `.evil.com/...`.

**Impact:** Low in practice since yt-dlp resolves the actual URL and would fail on non-Facebook domains. But it weakens the validation layer.

**Fix:** Add `(?:[/?#]|$)` after the domain to ensure the domain boundary is respected:
```python
FACEBOOK_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.watch|fb\.com)"
    r"(?:[/?#](?:/[\w.]+)?(?:/(?:videos?|watch|reel|posts|story)/?\S*)?.*)?$",
    re.IGNORECASE,
)
```

Or simpler -- add a lookahead after the domain:
```python
FACEBOOK_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.watch|fb\.com)"
    r"(?:/[\w.]+)?(?:/(?:videos?|watch|reel|posts|story)/?\S*)?$",
    re.IGNORECASE,
)
```
Adding `$` at end would be the minimal fix.

---

## High Priority

### 2. --facebook-page argument not validated (High)

**File:** `main.py:67-70`

The `--facebook-page` code path passes the URL directly to the download queue without any validation. Compare with `args.url` (line 54) which calls `validate_url()`.

```python
# Line 67-70: No validation!
else:
    # --facebook-page
    urls = [args.facebook_page]
    console.print(f"[cyan]Scraping Facebook page: {args.facebook_page}[/cyan]")
```

**Fix:**
```python
else:
    # --facebook-page
    if not is_facebook_page_url(args.facebook_page):
        console.print(f"[red]Error: Invalid Facebook page URL: {args.facebook_page}[/red]")
        sys.exit(1)
    urls = [args.facebook_page]
    console.print(f"[cyan]Scraping Facebook page: {args.facebook_page}[/cyan]")
```

Requires importing `is_facebook_page_url` in `main.py`.

### 3. channel_fetcher.py hardcodes TikTok URL fallback (High)

**File:** `channel_fetcher.py:72`

```python
if not url and video_id:
    url = f"https://www.tiktok.com/@_/video/{video_id}"
```

When a Facebook page is browsed via the Channel tab, any entry without a URL will get a TikTok fallback URL. This will silently fail or download the wrong content.

**Fix:** Pass the platform context to `ChannelFetcher` or detect platform from the channel URL:
```python
if not url and video_id:
    if "facebook.com" in self.channel_url or "fb." in self.channel_url:
        url = f"https://www.facebook.com/watch/?v={video_id}"
    else:
        url = f"https://www.tiktok.com/@_/video/{video_id}"
```

---

## Medium Priority

### 4. FACEBOOK_PAGE_PATTERN too strict for real-world page URLs

**File:** `url_parser.py:31-34`

Pattern: `r"https?://(?:www\.|m\.)?facebook\.com/[\w.]+/?$"`

- Missing `web.` subdomain (included in FACEBOOK_URL_PATTERN but not here)
- Missing `fb.com` short domain
- Does not handle `/profile.php?id=12345` format (numeric profile pages)
- Does not handle pages with hyphens in their name (e.g. `facebook.com/my-page-name`)

**Fix:** Align with FACEBOOK_URL_PATTERN domains and allow hyphens:
```python
FACEBOOK_PAGE_PATTERN = re.compile(
    r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.com)/[\w.\-]+/?$",
    re.IGNORECASE,
)
```

### 5. `detect_platform` does not detect Facebook page URLs on fb.com or web.facebook.com

**File:** `url_parser.py:67-74`

A Facebook page on `web.facebook.com` or `fb.com` won't match `FACEBOOK_PAGE_PATTERN` (which only allows `www.` and `m.`), so `detect_platform` might fall through to FACEBOOK_URL_PATTERN -- but bare `https://fb.com/pagename` may not match that either depending on the path structure. Could cause `None` return for valid Facebook page URLs.

### 6. Rich markup injection in console output (Low-Medium)

**File:** `main.py:55, 70`

User-controlled URLs in f-strings passed to `console.print()` with Rich markup. If URL contains `[red]` or similar brackets, Rich interprets them as markup.

**Impact:** Cosmetic only (garbled terminal output). Not exploitable for code execution.

**Fix:** Use `rich.markup.escape()`:
```python
from rich.markup import escape
console.print(f"[red]Error: Invalid URL: {escape(args.url)}[/red]")
```

---

## Low Priority

### 7. `downloader.py` docstring still says "TikTok" only

**File:** `downloader.py:1`

```python
"""yt-dlp wrapper for downloading TikTok videos."""
```

Should mention Facebook too for accuracy.

### 8. `download_engine.py` skip logic uses `extract_video_id` (TikTok-specific)

**File:** `download_engine.py:90`

The `extract_video_id()` function only extracts TikTok video IDs (`/video/(\d+)`). Facebook video IDs will never match, so Facebook re-downloads are never skipped by the history system. This is a functional gap rather than a bug -- downloads will work, just won't be deduplicated.

### 9. Missing test: batch file with mixed TikTok + Facebook URLs

No test verifies that `read_batch_file` + `validate_url` works correctly with a mix of both platforms in one file.

---

## Positive Observations

1. **Clean separation of concerns** -- URL parsing isolated in `url_parser.py`, not scattered across modules
2. **Good test coverage** -- 102 tests, all passing; Facebook tests cover valid/invalid/edge cases
3. **Backward compatibility preserved** -- All existing TikTok functionality untouched; unified `validate_url()` is additive
4. **Consistent API design** -- `is_page_or_channel_url()` and `validate_url()` provide clean unified interfaces
5. **GUI updates minimal and appropriate** -- Placeholder text and tab labels updated without structural changes

---

## Recommended Actions (Priority Order)

1. **Add `$` anchor to `FACEBOOK_URL_PATTERN`** -- prevents prefix matching on injected domains
2. **Validate `--facebook-page` argument in main.py** -- match the validation done for `args.url`
3. **Fix `channel_fetcher.py` TikTok URL fallback** -- platform-aware fallback for Facebook video IDs
4. **Align `FACEBOOK_PAGE_PATTERN` domains** with `FACEBOOK_URL_PATTERN` (add `web.`, `fb.com`, hyphens)
5. **Add mixed-platform batch file test**
6. **Escape Rich markup** in user-facing URL output (nice-to-have)

---

## Metrics

- **Test Coverage:** 102 tests, all passing
- **Linting Issues:** 0 syntax errors
- **Type Safety:** Good -- uses `str | None` unions, `re.compile` typed patterns
- **Security:** 1 medium (regex prefix match), 1 validation gap, 1 cosmetic (Rich injection)

---

## Unresolved Questions

1. Should `validate_facebook_url("https://www.facebook.com")` (bare domain, no path) return True? Currently it does. This seems too permissive.
2. Should Facebook video ID extraction be implemented for download deduplication, or is relying on yt-dlp's filename-based dedup sufficient?
3. Is `channel_fetcher.py` expected to work with Facebook pages via yt-dlp's flat extraction, or does Facebook require a different scraping approach?
