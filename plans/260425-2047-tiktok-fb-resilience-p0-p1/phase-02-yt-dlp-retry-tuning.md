# Phase 02 — yt-dlp Retry Tuning

## Context Links
- Synthesis: `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` §2.7, §4 (P0 items 3–4)
- Backoff research: `plans/reports/researcher-3-260425-1302-backoff-strategies.md` §yt-dlp-config
- Code: `downloader.py:50-69` (`get_ydl_opts`)

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** ~25 min
- **Description:** Add `extractor_retries`, `file_access_retries`, `fragment_retries`, `sleep_interval_requests`, `sleep_interval`, `max_sleep_interval` to `get_ydl_opts`. Bump `retries` 5→10 (or platform-specific). Add `retry_sleep_functions` for HTTP/fragment/extractor layers with exp+jitter.

## Key Insights
- yt-dlp picks `uniform(sleep_interval, max_sleep_interval)` between requests when both set — this is *another* random pacing layer below `download_batch`'s loop.
- Default retries are too low for FB (which 429s aggressively); too generous for FB if we retry past login-walls. Phase 03 fast-fails; this phase adjusts the base retry count to per-platform.
- `retry_sleep_functions` keys: `"http"`, `"fragment"`, `"extractor"` — accept callable `n -> seconds`.
- Avoid `--retries infinite` (broken in some yt-dlp versions, #10109).

## Requirements
**Functional**
- `get_ydl_opts(output_dir, cookie_browser, retries=10, ...)` accepts a `retries` override param.
- New fields added to opts dict:
  - `extractor_retries=5`
  - `file_access_retries=3`
  - `fragment_retries=10`
  - `sleep_interval_requests=0.75`
  - `sleep_interval=2.0`
  - `max_sleep_interval=8.0`
  - `retry_sleep_functions={"http": ..., "fragment": ..., "extractor": ...}`
- `download_video(url, output_dir, ...)` accepts platform-aware `retries` (derived from `PlatformDefaults`).

**Non-functional**
- No new dependency (uses stdlib `random`).
- Retry callables must be picklable (no closures over thread-local state) — they're lambdas using stdlib `random` only.

## Architecture
```
downloader.py
└── get_ydl_opts(output_dir, cookie_browser=None, retries=10)
     └── opts.update({
           "retries": retries,
           "extractor_retries": 5,
           "file_access_retries": 3,
           "fragment_retries": 10,
           "sleep_interval_requests": 0.75,
           "sleep_interval": 2.0,
           "max_sleep_interval": 8.0,
           "retry_sleep_functions": {
               "http": lambda n: min(60, 2**n + random.uniform(0, 1)),
               "fragment": lambda n: min(30, 2**n),
               "extractor": lambda n: min(120, 5 * (2**n)),
           },
         })
```

**Data flow:** `download_batch` → looks up `PlatformDefaults.retries` for the URL's platform → passes to `download_video(retries=…)` → `get_ydl_opts(retries=…)` → yt-dlp uses across HTTP/fragment/extractor failure paths.

## Related Code Files
**Modify**
- `D:\Projects\tiktokder\downloader.py` — extend `get_ydl_opts` signature + opts dict; thread `retries` through `download_video` and `download_batch`.

**Create** — none.

**Delete** — none.

## Implementation Steps

1. **Add `import random`** at top of `downloader.py` (if not already present).
2. **Extend `get_ydl_opts` signature** to `(output_dir: str, cookie_browser: str | None = None, retries: int = 10)`.
3. **Add the new opts fields** to the dict per the Architecture block. Place after `socket_timeout`, before `impersonate`.
4. **Define `retry_sleep_functions`** as a module-level dict literal (or constant) and reference it — keeps `get_ydl_opts` readable.
5. **Extend `download_video` signature** to accept `retries: int = 10`, pass through to `get_ydl_opts`.
6. **Extend `download_batch`** to accept platform-aware `retries`. Inside the per-URL submission, look up platform via `detect_platform(url)`, fetch `get_platform_defaults(url).retries`, pass to `download_video`.
7. **Compile-check:** `python -c "from downloader import get_ydl_opts; print(get_ydl_opts('./tmp')['retry_sleep_functions']['http'](2))"` — confirm callable returns positive number.
8. **Manual smoke:** run a known-403 URL and confirm yt-dlp logs show "Retrying" with increasing waits.

## Todo List
- [ ] Add `import random` to `downloader.py`
- [ ] Extend `get_ydl_opts(retries=10, …)` signature
- [ ] Add `extractor_retries`, `file_access_retries`, `fragment_retries`
- [ ] Add `sleep_interval_requests`, `sleep_interval`, `max_sleep_interval`
- [ ] Add `retry_sleep_functions` for `http`/`fragment`/`extractor`
- [ ] Thread `retries` through `download_video` → `download_batch`
- [ ] Compile-check the callables produce positive seconds
- [ ] Smoke test against a transient-failure URL

## Success Criteria
- `get_ydl_opts('./x')['retries'] == 10` (default).
- `get_ydl_opts('./x', retries=2)['retries'] == 2` (FB override).
- `get_ydl_opts('./x')['retry_sleep_functions']['http'](0)` returns a value in `[0.0, 2.0]`.
- `get_ydl_opts('./x')['retry_sleep_functions']['extractor'](3)` returns `min(120, 40)` = 40.
- yt-dlp accepts the opts dict without `KeyError`/`TypeError` on initialization.
- Existing tests pass.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| yt-dlp version installed doesn't support `retry_sleep_functions` | Low | Medium | `requirements.txt` already pins `yt-dlp>=2024.0.0`; supported since 2023.07.06. Verify version on smoke test |
| Combined `sleep_interval=2.0` + `_jittered_sleep` (Phase 01) compounds delay → users complain "slow" | Medium | Low | Document in `--help`; sleep_interval applies *per yt-dlp request*, jitter applies *between videos* — different layers |
| `retry_sleep_functions` callable raising swallows exception inside yt-dlp | Low | Medium | Lambdas use only `min`, `max`, `**`, `random.uniform` — no failure modes |
| FB `retries=2` too aggressive in transient outages | Medium | Low | Phase 04 (tenacity) sits above this layer and adds own retry budget |

## Security Considerations
- None new.

## Next Steps
- Phase 03 catches login-wall errors before they consume the retry budget set here.
- Phase 04 wraps `download_video` with `tenacity` — outer retry layer; this phase is yt-dlp's *inner* retry config.
