# Phase 02 — `apply_cookies()` Helper + yt-dlp Wiring

## Context Links
- Phase 01 (config foundation): `./phase-01-config-and-migration.md`
- Brainstorm: `plans/reports/brainstorm-260427-0013-tiktok-cookies-parity.md`

## Overview
- **Priority:** P2
- **Status:** completed
- **Depends on:** Phase 01
- **Effort:** S (~30 min)
- **Description:** Extract a small `apply_cookies()` helper, then wire `tiktok_cookies_file` into yt-dlp at both TikTok call sites — `downloader.py:64-66` (downloads) and `channel_fetcher.py:65-66` (profile scrapes).

## Key Insights
- yt-dlp accepts `cookiefile` (path string) or `cookiesfrombrowser` (tuple). They are mutually exclusive in practice — passing both is undefined behavior.
- Helper centralizes precedence: file > browser > none. DRY across 2 (eventually 3) call sites.

## Requirements
**Functional**
- New helper sets `cookiefile` if a valid path is provided, else `cookiesfrombrowser` if browser set, else nothing
- TikTok download path uses helper
- TikTok profile scrape path uses helper
- FB download path (if it currently passes `cookiesfrombrowser` for FB at all) reviewed; helper used if applicable

**Non-functional**
- Helper signature is small + testable in isolation (no I/O beyond `Path.exists()`)
- Existing behavior unchanged when only `cookie_browser` is set

## Architecture
```python
# downloader.py (or yt_dlp_helpers.py if file >200 LOC after change)

def apply_cookies(
    ydl_opts: dict,
    browser: str | None,
    file_path: Path | None,
) -> None:
    """Mutate ydl_opts to add cookie source. File takes precedence."""
    if file_path and file_path.exists():
        ydl_opts["cookiefile"] = str(file_path)
    elif browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)
```

## Related Code Files
**Modify:**
- `downloader.py` — add helper, replace inline cookie wiring at lines ~64-66
- `channel_fetcher.py` — replace inline `cookiesfrombrowser` at lines ~65-66 with helper call

**Read for context:**
- `config.py` — confirm field names from Phase 01
- `retry_policy.py` — error classification (cookies failures surface here)

**Create:**
- `yt_dlp_helpers.py` *only if* `downloader.py` exceeds 200 LOC after the helper is added

## Implementation Steps
1. **Helper draft** — Add `apply_cookies()` function in `downloader.py` (top-level, near other helpers).
2. **Downloader wiring** — at the TikTok branch (lines 64-66), replace existing `cookiesfrombrowser` assignment with `apply_cookies(ydl_opts, config.tiktok_cookie_browser, config.tiktok_cookies_file)`.
3. **Channel fetcher wiring** — `channel_fetcher.py` lines 65-66, same replacement: `apply_cookies(opts, config.tiktok_cookie_browser, config.tiktok_cookies_file)`.
4. **FB downloader review** — if `downloader.py` currently passes `cookiesfrombrowser` for FB, switch to helper with `(None, config.facebook_cookies_file)` so file-only behavior preserved. If FB never used `cookiesfrombrowser`, leave untouched (helper unused for FB downloads).
5. **Modularization check** — `wc -l downloader.py`. If >200, extract helper to new `yt_dlp_helpers.py` and import.
6. **Compile check** — `python -m py_compile downloader.py channel_fetcher.py`
7. **Smoke test** — set `tiktok_cookies_file` to a test Netscape file in dev config; run `python main.py "https://www.tiktok.com/@tiktok/video/<id>" --output /tmp/test` with yt-dlp verbose flag; confirm `[cookies] Loading cookie jar` log line.

## Todo List
- [x] Add `apply_cookies()` helper in new `yt_dlp_helpers.py` (downloader.py was already 493 LOC)
- [x] Wire helper into `get_ydl_opts()` (collapses prior inline branching) — covers both TikTok + FB downloads through one path
- [x] Wire helper into `channel_fetcher.py` and add `cookies_file` parameter
- [x] Threaded `tiktok_cookies_file` through `DownloadEngine` → `DownloadWorker` → `download_video`; routed per-platform inside worker
- [x] Compile all touched files
- [x] Verified helper precedence with 6-case unit test (see Phase 04)

## Success Criteria
- yt-dlp verbose log shows cookie jar loaded from path when `tiktok_cookies_file` set
- yt-dlp verbose log shows browser-based extraction when only `cookie_browser` set (unchanged behavior)
- Neither set → no cookie-related opts in `ydl_opts` dict
- Both set → file wins (precedence asserted)
- No regression on FB download / scrape

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| `Path.exists()` racing with file rotation | Acceptable for desktop tool; yt-dlp will surface its own error if file vanishes mid-run |
| Helper file extraction breaks imports | Update import in both call sites if extracted |
| Old config still has `cookies_file` key during transition | Phase 01 migration shim handles this |
| `cookiesfrombrowser` tuple shape varies (some yt-dlp versions accept dict) | Keep tuple form `(browser,)` — matches existing call site, current tested format |

## Security Considerations
- Cookie file content not logged
- Helper does not validate cookie freshness — stale cookies surface as `login_required` via existing retry policy
- File path treated as trusted (user-provided in Settings)

## Next Steps
- Phase 03 wires the Settings UI to populate `tiktok_cookies_file`
- Phase 04 adds unit test for `apply_cookies()` precedence + integration smoke
