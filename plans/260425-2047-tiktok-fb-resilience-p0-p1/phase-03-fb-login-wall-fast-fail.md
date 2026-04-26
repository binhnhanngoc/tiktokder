# Phase 03 — Facebook Login-Wall Fast-Fail

## Context Links
- Synthesis: `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` §3, §4 (P0 item 5)
- FB research: `plans/reports/researcher-2-260425-1302-facebook-rate-limits.md` §login-walls
- Code: `downloader.py:86-107` (`download_video`)

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** ~20 min
- **Description:** Detect FB login-wall markers in `yt_dlp.DownloadError` messages. Mark `DownloadResult.error="login_required"` (typed) and skip retries. Stops compounding the FB penalty from repeatedly hitting `/login` redirects.

## Key Insights
- FB blocks **silently**: 302 → `/login`, returned page contains predictable HTML markers.
- yt-dlp surfaces these as `DownloadError`/`ExtractorError` with the page body partially in the message.
- Markers from FB defaults (synthesis §3): `'id="login_form"'`, `'id="loginbutton"'`, `'You must log in to continue'`, `'class="uiInterstitialContent"'`.
- Retrying past a login wall *increases* FB penalty (account flag risk). Must not invoke yt-dlp again on this error class.

## Requirements
**Functional**
- Helper `_classify_error(exc: Exception) -> str` returns one of: `"login_required"`, `"private"`, `"not_found"`, `"rate_limited"`, `"transient"`, `"unknown"`.
- `download_video` catches `yt_dlp.utils.DownloadError` and uses classifier to populate `DownloadResult.error`.
- When classification is `"login_required"`, `"private"`, or `"not_found"` → mark non-retryable (consumed by Phase 04 tenacity predicate).
- Login-wall markers stored as a constant tuple (`FB_LOGIN_WALL_MARKERS`) in `config.py` so Phase 05 can reuse.

**Non-functional**
- Substring matching is case-insensitive on the marker text where appropriate (markers are HTML literals, but error messages may include extras).
- Classifier is a pure function — easy to unit-test.

## Architecture
```
config.py
└── FB_LOGIN_WALL_MARKERS = (
        'id="login_form"',
        'id="loginbutton"',
        'You must log in to continue',
        'class="uiInterstitialContent"',
        'login.php',
    )

downloader.py
├── ErrorKind = Literal["login_required", "private", "not_found",
│                       "rate_limited", "transient", "unknown"]
├── _classify_error(exc) -> ErrorKind
└── download_video(...)
     except DownloadError as e:
         kind = _classify_error(e)
         return DownloadResult(url=url, success=False, error=kind, …)
```

**Data flow:** yt-dlp raises `DownloadError(msg)` → `_classify_error` substring-matches `msg` → returns kind → `DownloadResult.error` becomes the kind string (machine-readable, not just human text). Phase 04 reads this string in the retry predicate.

## Related Code Files
**Modify**
- `D:\Projects\tiktokder\config.py` — add `FB_LOGIN_WALL_MARKERS` tuple.
- `D:\Projects\tiktokder\downloader.py` — add `_classify_error`, refactor `download_video` exception block.

**Create** — none.

**Delete** — none.

## Implementation Steps

1. **Add `FB_LOGIN_WALL_MARKERS` constant** to `config.py` (top-level, after imports).
2. **Add `from typing import Literal`** in `downloader.py` (if not present).
3. **Add `ErrorKind` type alias** and `_classify_error(exc: Exception) -> str` to `downloader.py`. Logic:
   - `msg = str(exc)`
   - If any marker in `FB_LOGIN_WALL_MARKERS` appears in `msg` → `"login_required"`
   - elif `"login" in msg.lower() and ("required" in msg.lower() or "redirect" in msg.lower())` → `"login_required"`
   - elif `"private" in msg.lower()` → `"private"`
   - elif any of `("404", "not found", "Video unavailable")` → `"not_found"`
   - elif any of `("HTTP Error 429", "rate limit", "too many requests")` → `"rate_limited"`
   - elif any of `("HTTP Error 5", "connection", "timeout", "temporarily")` → `"transient"`
   - else → `"unknown"`
4. **Refactor `download_video` except block** (`downloader.py:106-107`):
   ```python
   except yt_dlp.utils.DownloadError as e:
       kind = _classify_error(e)
       return DownloadResult(url=url, success=False, error=kind)
   except Exception as e:
       return DownloadResult(url=url, success=False, error=str(e))
   ```
   Keep raw `Exception` branch as catch-all for non-yt-dlp errors.
5. **Update `DownloadResult` docstring** to note `error` is now a kind string for known classes (`"login_required"`, etc.) or raw message otherwise.
6. **Adjust progress display** in `download_batch` (line 157): map kind string to user-friendly text:
   - `login_required` → `"Login required"`
   - `private` → `"Private/restricted"`
   - `rate_limited` → `"Rate limited"`
   - else → as-is.

## Todo List
- [ ] Add `FB_LOGIN_WALL_MARKERS` to `config.py`
- [ ] Add `_classify_error` helper to `downloader.py`
- [ ] Refactor `download_video` exception handling to use classifier
- [ ] Map error kinds to user-friendly strings in batch progress output
- [ ] Update `DownloadResult` docstring
- [ ] Compile-check classifier with synthesized error strings

## Success Criteria
- `_classify_error(DownloadError('... id="login_form" ...'))` returns `"login_required"`.
- `_classify_error(DownloadError('HTTP Error 429: Too Many Requests'))` returns `"rate_limited"`.
- `_classify_error(DownloadError('Video unavailable'))` returns `"not_found"`.
- `download_video(<known-FB-login-wall-url>, ...)` returns `DownloadResult(success=False, error="login_required")` *without* invoking yt-dlp retry loop more than once.
- Existing tests pass.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Marker substring matches false positive (e.g. legitimate page contains `login.php` as text) | Low | Low | Markers anchor on HTML structure (`id=`, `class=`) — false-positive risk is small. `login.php` listed last and only triggers if no other class matches |
| FB changes login-wall HTML between releases | Medium | Medium | Markers are a tuple — easy to extend. Document update path in `config.py` comment |
| User-supplied error message format varies across yt-dlp versions | Low | Low | Classifier is permissive, falls back to `"unknown"` (which Phase 04 treats as retryable) |
| Classifier hides original message → debugging harder | Medium | Medium | Add `logger.debug(f"Classified error: {kind} from {msg}")` so verbose mode preserves raw text |

## Security Considerations
- No new auth surface. Classifier is read-only string matching. No PII logged at INFO level (raw msg only at DEBUG).

## Next Steps
- Phase 04 (tenacity) consumes the `error` kind to decide retry/no-retry.
- Phase 05 reuses `FB_LOGIN_WALL_MARKERS` for the `fb.watch` HEAD-redirect pre-check.
