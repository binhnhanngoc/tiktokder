# Brainstorm — TikTok Cookies Parity with Facebook

**Date:** 2026-04-27
**Status:** Design approved, ready for `/ck:plan`
**Trigger:** Defensive parity — preempt TikTok rate limits before they bite, mirror FB cookies.txt UX.

---

## Problem Statement

Facebook already supports a Netscape `cookies.txt` path (lifts 10-reel anon cap on Playwright profile scrapes). TikTok currently supports cookies *only* via `cookie_browser` (yt-dlp's `cookiesfrombrowser` flag → Chrome/Firefox/Edge DB extraction).

`cookie_browser` is brittle:
- Chrome locks cookie DB while running → silent extraction failure
- Linux Chromium encrypted-cookie variants are flaky
- Doesn't work in headless / CI / packaged-app scenarios

No live failure observed — this is a **defensive add** to lift anonymous rate limits on profile scrapes and downloads before they trigger.

## Requirements

- Add `tiktok_cookies_file: Path | None` to config, parallel to FB's `cookies_file`
- Wire into yt-dlp `cookiefile` opt at **both** TikTok call sites:
  - `downloader.py:64-66` (individual + batch downloads)
  - `channel_fetcher.py:65-66` (profile scrapes via flat-playlist)
- Precedence: file > browser > none (file path more reliable, takes priority)
- Settings UI: path picker under TikTok group, alongside existing `cookie_browser`
- Tooltip mirrors FB wording ("Export via 'Get cookies.txt LOCALLY' extension while logged in")
- Auto-save + propagate to in-flight engine state (per existing settings pattern)

## Approaches Evaluated

| # | Approach | Pros | Cons | Verdict |
|---|----------|------|------|---------|
| **A** | Minimal mirror (parallel field, same UX as FB) | KISS, ~50 LOC, consistent | Two parallel paths still | **Selected** |
| B | Unified per-platform cookie struct | Cleaner for 3+ platforms | Refactor scope, YAGNI today | Defer until 3rd platform |
| C | Harden `cookie_browser` only (lock detection) | Smallest change | Doesn't solve headless/CI; cookies still missing | Rejected — wrong layer |

## Final Solution (Approach A)

### Config
- New field: `AppConfig.tiktok_cookies_file: Path | None = None`
- Existing `cookies_file` stays as FB-only (rename optional — see "Open Questions")

### Helper (DRY)
Extract small helper used by both TikTok call sites and FB downloader:

```python
def apply_cookies(ydl_opts: dict, browser: str | None, file_path: Path | None) -> None:
    """File takes precedence over browser. No-op if both None."""
    if file_path and file_path.exists():
        ydl_opts["cookiefile"] = str(file_path)
    elif browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)
```

Place in `downloader.py` (or a new `yt_dlp_helpers.py` if file >200 LOC).

### Call Sites

| File | Line | Change |
|------|------|--------|
| `downloader.py` | 64–66 | Replace inline cookie wiring with `apply_cookies()` for TikTok branch |
| `channel_fetcher.py` | 65–66 | Replace inline `cookiesfrombrowser` with `apply_cookies()` |
| `gui/settings_panel.py` | ~152–180 area (after FB cookies block) | Mirror block under TikTok group |
| `config.py` | (TikTok section) | Add `tiktok_cookies_file` field + serializer |

### UI Layout (Settings → TikTok group)
```
TikTok
├── Cookie Browser    [None ▾]    (existing)
└── Cookies File      [_________] [Browse]   (new)
   tooltip: "Optional. Overrides Cookie Browser. Export via
            'Get cookies.txt LOCALLY' extension while logged in."
```

## Out of Scope (deliberately)

- **aria2c integration** — no perf complaint, defer to YAGNI
- **Cookie expiry detection** — yt-dlp will surface auth errors via existing `retry_policy.py` classification; no proactive UI nag
- **Auto-export from browser** — too fragile (Chrome encrypted), ship manual export path
- **Unified cookie struct** (Approach B) — wait for 3rd platform

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| User exports wrong domain (FB cookies into TT field) | yt-dlp ignores non-matching domains silently — harmless |
| Stale cookies → silent download fails | Existing `retry_policy.py` already classifies `login_required`; surfaced to user |
| Both `cookie_browser` + `tiktok_cookies_file` set | Precedence is documented (file wins); consistent with helper logic |
| Helper extraction grows `downloader.py` past 200 LOC | Split into `yt_dlp_helpers.py` per modularization rule |

## Success Criteria

- TikTok download with `tiktok_cookies_file` set → yt-dlp receives `cookiefile` opt (verifiable via `--verbose` log line `[cookies] Loading cookie jar from ...`)
- TikTok profile scrape with cookies → exceeds anonymous video count ceiling on a known large account
- Settings UI: path picker saves, persists across restart, propagates to running engine
- No regression on FB cookies path or existing `cookie_browser` flow
- All existing tests pass; new test covers `apply_cookies()` precedence

## Implementation Effort

~50–80 LOC across 4 files. Single phase, no migration needed (new optional field).

## Resolved Decisions

1. **Rename** `cookies_file` → `facebook_cookies_file` bundled into this change for symmetry. Config migration shim required (read old key, write new key on first save).

## Open Questions

1. Should the helper live in `downloader.py` or a new `yt_dlp_helpers.py`? **Depends on resulting file size — defer until implementation.**
