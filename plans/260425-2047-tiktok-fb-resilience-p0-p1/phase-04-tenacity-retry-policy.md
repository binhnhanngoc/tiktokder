# Phase 04 — Tenacity Retry Policy with Retry-After Awareness

## Context Links
- Synthesis: `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` §2.7, §4 (P1 item 6)
- Backoff research: `plans/reports/researcher-3-260425-1302-backoff-strategies.md` §tenacity, §retry-after
- Code: `downloader.py:86-107` (post-Phase-03), `requirements.txt`

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** ~50 min
- **Description:** Add `tenacity>=8.0.0` dep. Create `retry_policy.py` module with custom `RateLimited` / `LoginRequired` / `TransientFailure` exceptions, `_is_retryable` predicate, and a `tenacity` decorator that honors `Retry-After`. Wrap `download_video` so transient failures retry with decorrelated jitter; permanent failures (login_required/private/not_found) skip retry.

## Key Insights
- Decorrelated jitter (`min(cap, rand(base, prev*3))`) is the AWS/Polly default — best at smoothing retry herds.
- yt-dlp's `DownloadError` does not expose HTTP `Retry-After` header directly. Workaround: parse `"Retry-After: N"` from message text when present; else fall back to decorrelated-jitter wait.
- Tenacity's `retry_if_exception` predicate must look at the typed exception, not error string. Hence we *raise* a typed exception inside `download_video` and let tenacity catch it.
- Two retry layers will exist: yt-dlp inner (Phase 02) + tenacity outer (this phase). Total budget = `tenacity_attempts × yt_dlp_retries`. Cap tenacity to small N (3) so total stays bounded.

## Requirements
**Functional**
- New module `retry_policy.py` exporting:
  - Exceptions: `LoginRequired`, `Private`, `NotFound`, `RateLimited(retry_after: float | None)`, `TransientFailure`, `PermanentFailure`.
  - `parse_retry_after(msg: str) -> float | None` — pulls `Retry-After: N` (seconds) or HTTP-date (best-effort) from text.
  - `_is_retryable(exc: BaseException) -> bool` — returns True only for `RateLimited`, `TransientFailure`.
  - `decorrelated_jitter(base=2.0, cap=60.0)` factory returning a stateful wait function for tenacity.
  - `with_retry(max_attempts: int = 3)` decorator factory composing `retry`, `stop_after_attempt`, `retry_if_exception(_is_retryable)`, custom `wait` (Retry-After-aware → decorrelated jitter fallback).
- `download_video` raises typed exception (mapped from `_classify_error` kind):
  - `login_required` → `LoginRequired`
  - `private` → `Private`
  - `not_found` → `NotFound`
  - `rate_limited` → `RateLimited(retry_after=parse_retry_after(msg))`
  - `transient`/`unknown` → `TransientFailure`
- A new wrapper `download_video_with_retry(url, ...)` applies `@with_retry()` and converts terminal exception back to `DownloadResult(success=False, error=<kind>)`. Public API stays compatible: callers continue to call `download_video` (which now goes through retry).
- `requirements.txt` gains `tenacity>=8.0.0`.

**Non-functional**
- Decorator must work with sync code (yt-dlp is sync). No asyncio.
- Predicate must be picklable (no closures over thread-local state) so `ThreadPoolExecutor` works.
- Retry attempt count and last wait logged at INFO via `before_sleep_log(logger, logging.INFO)`.

## Architecture
```
retry_policy.py
├── class LoginRequired(Exception)
├── class Private(Exception)
├── class NotFound(Exception)
├── class RateLimited(Exception):
│       def __init__(self, msg, retry_after: float | None = None)
├── class TransientFailure(Exception)
├── class PermanentFailure(Exception)
├── parse_retry_after(msg) -> float | None
├── _is_retryable(exc) -> bool      # True for RateLimited, TransientFailure
├── decorrelated_jitter(base=2.0, cap=60.0) -> wait callable
├── retry_after_aware_wait(base=2.0, cap=60.0) -> wait callable
│       (if RateLimited.retry_after set → use it; else decorrelated jitter)
└── with_retry(max_attempts=3) -> decorator

downloader.py
├── _kind_to_exception(kind, msg) -> Exception
├── _do_download(url, output_dir, ...)        # raw, raises typed exc
└── download_video = with_retry()(_do_download_returning_result)
    OR keep download_video signature; internally call retried _do_download
    and convert exceptions in a final `try/except` to DownloadResult.
```

**Data flow:**
```
download_video(url)
  -> [tenacity wraps]
       -> _do_download
            -> yt-dlp ... DownloadError
            -> kind = _classify_error
            -> raise _kind_to_exception(kind)
       -> tenacity: _is_retryable(exc)?
            -> True (RateLimited / TransientFailure)
                 -> wait = retry_after or decorrelated_jitter sample
                 -> retry up to max_attempts
            -> False (LoginRequired / Private / NotFound)
                 -> propagate
  -> caller catches typed exc → DownloadResult(error=<kind>)
```

## Related Code Files
**Modify**
- `D:\Projects\tiktokder\downloader.py` — wrap `download_video` body with tenacity; map `_classify_error` kind → typed exception; convert terminal exception back to `DownloadResult`.
- `D:\Projects\tiktokder\requirements.txt` — add `tenacity>=8.0.0`.
- `D:\Projects\tiktokder\config.py` — expose `MAX_RETRY_ATTEMPTS_TIKTOK=3`, `MAX_RETRY_ATTEMPTS_FACEBOOK=2` (tenacity layer, separate from yt-dlp `retries`).

**Create**
- `D:\Projects\tiktokder\retry_policy.py` — exceptions, predicate, wait fn, decorator factory.

**Delete** — none.

## Implementation Steps

1. **Add `tenacity>=8.0.0` to `requirements.txt`.**
2. **Install:** `pip install -r requirements.txt` (user runs locally).
3. **Create `retry_policy.py`** with the exception hierarchy. Make `RateLimited` accept `retry_after: float | None` (default None) and store it as attribute.
4. **Implement `parse_retry_after(msg)`** — regex `r"Retry-After:\s*(\d+)"` first; if not found return `None`. (HTTP-date format optional, skip for v1 — covered by decorrelated fallback.)
5. **Implement `decorrelated_jitter(base=2.0, cap=60.0)`** as a closure over `prev` state. Returns a callable that tenacity calls per attempt; signature `wait(retry_state) -> float`. Algorithm: `prev = min(cap, random.uniform(base, prev * 3)); return prev`. Initialize `prev = base`.
6. **Implement `retry_after_aware_wait`** — wraps `decorrelated_jitter`. If the last `retry_state.outcome.exception()` is `RateLimited` with non-None `retry_after`, return that value (capped at `cap`). Else delegate to decorrelated_jitter.
7. **Implement `with_retry(max_attempts=3)`** decorator factory that composes:
   ```python
   from tenacity import retry, stop_after_attempt, retry_if_exception, before_sleep_log
   return retry(
       stop=stop_after_attempt(max_attempts),
       retry=retry_if_exception(_is_retryable),
       wait=retry_after_aware_wait(),
       before_sleep=before_sleep_log(logger, logging.INFO),
       reraise=True,
   )
   ```
8. **Refactor `download_video` in `downloader.py`:**
   - Extract current body into `_do_download(url, output_dir, ...) -> dict` (returns yt-dlp `info` on success; raises typed exception on failure).
   - In except block, build typed exc: `raise _kind_to_exception(kind, msg, retry_after=parse_retry_after(msg))`.
   - Apply `@with_retry(max_attempts=...)` to `_do_download` (or a thin wrapper).
   - In `download_video`, call retried `_do_download`, return `DownloadResult(success=True, ...)`. Catch `(LoginRequired, Private, NotFound, RateLimited, TransientFailure, PermanentFailure)` → return `DownloadResult(success=False, error=<kind>)`.
9. **Per-platform `max_attempts`:** read `PlatformDefaults.retries` from Phase 01? No — yt-dlp's `retries` is the inner layer. Use a *separate* `MAX_RETRY_ATTEMPTS_*` constant from `config.py` (3 for TikTok, 2 for FB) for the tenacity layer. Look up via platform.
10. **Logging:** add `logger = logging.getLogger(__name__)` to `retry_policy.py`. Tenacity's `before_sleep_log` logs each retry attempt with the wait duration.

## Todo List
- [ ] Add `tenacity>=8.0.0` to `requirements.txt`
- [ ] Run `pip install -r requirements.txt`
- [ ] Create `retry_policy.py` with exception hierarchy
- [ ] Implement `parse_retry_after`
- [ ] Implement `decorrelated_jitter` factory
- [ ] Implement `retry_after_aware_wait`
- [ ] Implement `with_retry` decorator factory
- [ ] Add `MAX_RETRY_ATTEMPTS_TIKTOK=3`, `MAX_RETRY_ATTEMPTS_FACEBOOK=2` to `config.py`
- [ ] Refactor `download_video` to raise typed exceptions
- [ ] Apply `@with_retry()` to download path
- [ ] Convert terminal exception → `DownloadResult` in `download_video`
- [ ] Verify `before_sleep_log` produces visible retry traces
- [ ] Compile-check entire `downloader.py`

## Success Criteria
- `pip install tenacity` succeeds; `import tenacity` in module works.
- `RateLimited(retry_after=5).retry_after == 5`.
- `parse_retry_after("HTTP 429: Retry-After: 30")` returns `30.0`.
- `_is_retryable(LoginRequired())` returns `False`; `_is_retryable(RateLimited())` returns `True`.
- `download_video(<known-login-wall-url>)` calls yt-dlp **once** (no retries), returns `DownloadResult(error="login_required")`.
- `download_video(<flaky-url>)` retries up to 3 times on transient failure, then succeeds or returns `DownloadResult(error="transient")`.
- Logs show "Retrying ... in N seconds" entries during transient failures.
- All Phase 01–03 tests still pass.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `tenacity` version mismatch with frozen Python (PyInstaller) | Low | Medium | `>=8.0.0` is widely compatible. Add to `build.py` `hidden_imports` if needed |
| `decorrelated_jitter` closure state shared across threads (race) | Medium | Low | Use thread-local random.Random or instantiate per-decorator-call. Most calls re-instantiate per `download_video` invocation, so risk is small. Document |
| Combined retry budget too long: `3 × 10 = 30` total HTTP attempts per URL | Medium | Medium | tenacity layer focuses on coarse failures; reduce `MAX_RETRY_ATTEMPTS_FACEBOOK` to 2; tune `cap=60s` so worst-case wait per outer retry is bounded |
| Typed exceptions shadow original message → users can't see "why" | Medium | Low | Pass original `msg` into typed exception; log at WARNING when re-raising terminal failure |
| `cookiesfrombrowser` failure path not classified | Low | Low | Catch `BrowserCookieError` separately, classify as `PermanentFailure` (don't retry — won't fix itself) |

## Security Considerations
- `parse_retry_after` accepts only digits — no eval / regex injection surface.
- Typed exceptions do not leak cookies or auth tokens (only error class string surfaces).

## Next Steps
- Phase 05 short-circuits `fb.watch` URLs *before* this retry layer engages — saves wasted retry budget on guaranteed-fail URLs.
- Phase 06 adds unit tests covering predicate, parser, and decorator.
