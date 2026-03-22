# Code Review: TikTok Batch Downloader

**Date:** 2026-03-21
**Files:** `url_parser.py`, `downloader.py`, `main.py`, `requirements.txt`
**LOC:** ~165
**Focus:** Security, correctness, concurrency, edge cases

## Overall Assessment

Clean, well-structured small CLI tool. Good use of dataclasses, type hints, and rich progress. Several issues need attention -- most are medium priority, two are high.

---

## Critical Issues

None.

## High Priority

### H1. Unhandled exception from `future.result()` in `download_batch`

**File:** `downloader.py:111`

`future.result()` can raise if `_download_with_delay` throws an unexpected exception (e.g., `KeyboardInterrupt`, `SystemExit`, or yt-dlp raising something before/after the try-catch in `download_video`). The `time.sleep(delay)` on line 105 is outside the try-catch, so a `KeyboardInterrupt` during sleep propagates unhandled.

```python
# Current
for future in as_completed(futures):
    result = future.result()  # can raise

# Fix
for future in as_completed(futures):
    try:
        result = future.result()
    except KeyboardInterrupt:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    except Exception as e:
        url = futures[future]
        result = DownloadResult(url=url, success=False, error=str(e))
    results.append(result)
```

### H2. URL regex allows non-video URLs, potential for SSRF-adjacent misuse

**File:** `url_parser.py:8-10`

The regex `TIKTOK_URL_PATTERN` matches profile URLs, explore pages, and other non-video TikTok paths. Combined with the `--user` mode passing unvalidated URLs directly to yt-dlp, there's no strong input boundary.

Also: `validate_tiktok_url` uses `match()` (anchored at start) but doesn't anchor at end -- a URL like `https://tiktok.com/@user/video/123?redirect=http://evil.com` would pass. Not exploitable via yt-dlp, but worth tightening.

```python
# Use fullmatch or add $ anchor
TIKTOK_URL_PATTERN = re.compile(
    r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/(?:@[\w.]+/video/\d+|[\w]+)/?(?:\?[^\s]*)?"
)
# And use fullmatch:
def validate_tiktok_url(url: str) -> bool:
    return bool(TIKTOK_URL_PATTERN.fullmatch(url.strip()))
```

### H3. `--user` mode URLs bypass `validate_tiktok_url`

**File:** `main.py:52-53`

When `--user` is used, `build_user_url` constructs a URL that is never validated. If `username` contains path traversal chars like `../` or encoded slashes, the constructed URL could be malformed. The username is directly interpolated into a URL string.

```python
# Fix in build_user_url:
def build_user_url(username: str) -> str:
    username = username.lstrip("@")
    if not re.fullmatch(r"[\w.]{1,30}", username):
        raise ValueError(f"Invalid TikTok username: {username}")
    return f"https://www.tiktok.com/@{username}"
```

---

## Medium Priority

### M1. Import inside loop

**File:** `downloader.py:83`

`from url_parser import extract_video_id` is inside a for-loop. Move to top of file.

### M2. `outtmpl` filename uses unsanitized title

**File:** `downloader.py:30`

`%(title).50s` truncates but doesn't sanitize. yt-dlp does sanitize filenames internally, but the template allows special chars in theory. Also, `.50s` truncation could cut mid-multibyte char. Low risk since yt-dlp handles this, but worth noting.

### M3. No validation of `--workers` range

**File:** `main.py:21`

`--workers` accepts any integer including 0 or negative. Add bounds.

```python
parser.add_argument("--workers", type=int, default=3, choices=range(1, 11),
                    metavar="N", help="Concurrent downloads 1-10 (default: 3)")
```

### M4. `--delay` accepts negative values

**File:** `main.py:22`

No lower bound. A negative delay would cause `time.sleep` to return immediately (no error), but zero delay with multiple workers could trigger rate limiting.

### M5. `read_batch_file` doesn't validate URLs

**File:** `url_parser.py:26-41`

URLs from batch file are never validated against `validate_tiktok_url`. Only the single-URL mode validates. Non-TikTok URLs would be passed to yt-dlp, which handles them but defeats the tool's purpose.

```python
# In main.py after reading batch:
urls = [u for u in urls if validate_tiktok_url(u)]
invalid = len(raw_urls) - len(urls)
if invalid:
    console.print(f"[yellow]Skipped {invalid} invalid URL(s)[/yellow]")
```

### M6. No graceful `KeyboardInterrupt` handling in `main()`

Users pressing Ctrl+C get an ugly traceback. Wrap `main()` call.

```python
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)
```

---

## Low Priority

### L1. Global `console` instances duplicated

Both `main.py` and `downloader.py` create their own `Console()`. Consider sharing or accepting as parameter.

### L2. `extract_video_id` returns None for short URLs

Short URLs (`vm.tiktok.com/ZMxxx`) don't contain `/video/ID`. The skip-already-downloaded feature won't work for these -- they'll always re-download. Could resolve short URLs first, but YAGNI unless users report it.

### L3. `requirements.txt` version pinning

`>=2024.0.0` is loose. For reproducibility, pin exact versions or use a lockfile.

---

## Positive Observations

- Clean module separation (parser / downloader / CLI)
- Good use of `dataclass` for structured results
- Deduplication in batch file reader
- Skip-already-downloaded is a nice UX feature
- Progress bar with rich is well-implemented
- Type hints throughout

---

## Recommended Actions (Priority Order)

1. **H1** -- Wrap `future.result()` in try-except
2. **H3** -- Validate username input in `build_user_url`
3. **M1** -- Move import to top of file
4. **M5** -- Validate batch file URLs
5. **M3/M4** -- Bound `--workers` and `--delay`
6. **M6** -- Handle KeyboardInterrupt gracefully
7. **H2** -- Tighten URL regex (lower urgency since yt-dlp is the actual consumer)

## Metrics

| Metric | Value |
|--------|-------|
| Type Coverage | ~90% (good hints, missing some return narrowing) |
| Test Coverage | 0% (no tests found) |
| Linting Issues | 1 (import inside loop) |
| Security Issues | 2 (username injection, unanchored regex) |

## Unresolved Questions

- Is `--user` mode intended to download all videos from a profile? yt-dlp handles this but the skip logic won't work well since profile scrape returns playlist entries, not individual `/video/ID` URLs.
- Should short URL resolution be added to make skip-downloaded work for `vm.tiktok.com` links?
