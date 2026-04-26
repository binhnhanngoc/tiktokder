# Phase 01 — Platform Defaults & Gaussian-Jittered Pacing

## Context Links
- Synthesis: `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` §3, §4 (P0 items 1–2)
- Backoff research: `plans/reports/researcher-3-260425-1302-backoff-strategies.md` §pacing
- Code: `downloader.py:110-161`, `config.py:39-50`, `download_engine.py:65-77`

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** ~35 min
- **Description:** Replace fixed `time.sleep(delay)` in `download_batch` with gaussian-jittered helper. Add `PlatformDefaults` dataclass exposing per-platform `delay`, `workers`, `retries`. Wire platform detection at batch dispatch.

## Key Insights
- Constant `time.sleep(d)` produces a flat cadence histogram → easy ML signal. Gaussian (truncated) mimics human pacing.
- TikTok and Facebook have asymmetric tolerance: FB needs ~3× delay, ~⅓ concurrency, ~⅕ retry budget vs TikTok.
- Platform detection already exists (`url_parser.detect_platform`) — reuse, don't duplicate.
- `AppConfig.delay`/`workers` must remain as user-set globals; `PlatformDefaults` is the *fallback when user hasn't overridden*.

## Requirements
**Functional**
- `_jittered_sleep(mean: float, std: float, floor: float) -> None` returns after sleeping `max(floor, gauss(mean, std))` seconds.
- `PlatformDefaults` dataclass with `delay_mean`, `delay_std`, `delay_floor`, `workers`, `retries` fields.
- Module-level constants `TIKTOK_DEFAULTS` and `FACEBOOK_DEFAULTS` in `config.py`.
- Helper `get_platform_defaults(url: str) -> PlatformDefaults` returning the right preset; falls back to TikTok defaults for unknown.
- `download_batch` calls `_jittered_sleep` instead of `time.sleep(delay)`; `delay` parameter becomes `delay_mean` (keyword-compatible).

**Non-functional**
- Zero new third-party deps (uses stdlib `random`).
- Backwards compat: `download_batch(..., delay=1.0)` keeps working; treated as `delay_mean`.
- Deterministic in tests via injectable `random.Random` seed.

## Architecture
```
config.py
├── PlatformDefaults (dataclass)
├── TIKTOK_DEFAULTS = PlatformDefaults(1.5, 0.5, 0.2, 3, 10)
├── FACEBOOK_DEFAULTS = PlatformDefaults(3.0, 1.5, 0.5, 1, 2)
└── get_platform_defaults(url) -> PlatformDefaults

downloader.py
├── _jittered_sleep(mean, std, floor)  # uses random.gauss + clamp
└── download_batch(...)
     └── replaces time.sleep(delay) → _jittered_sleep(...)
```

**Data flow:** URL → `detect_platform` → `get_platform_defaults` → if user did not override `workers`/`delay`, apply preset → submit to `ThreadPoolExecutor` with platform-aware delay → after each future completes, call `_jittered_sleep`.

## Related Code Files
**Modify**
- `D:\Projects\tiktokder\config.py` — add dataclass + constants + helper.
- `D:\Projects\tiktokder\downloader.py` — add `_jittered_sleep`, replace `time.sleep`, accept `PlatformDefaults` (optional kwarg) in `download_batch`.
- `D:\Projects\tiktokder\download_engine.py` — `DownloadEngine.__init__` accepts platform-aware delay/workers; `_on_worker_finished` jittered `QTimer.singleShot`.
- `D:\Projects\tiktokder\main.py` — when `--delay`/`--workers` not specified, derive from URL via `get_platform_defaults`.

**Create** — none

**Delete** — none

## Implementation Steps

1. **Add `PlatformDefaults` to `config.py`** below `AppConfig`:
   - Fields: `delay_mean: float`, `delay_std: float`, `delay_floor: float`, `workers: int`, `retries: int`.
2. **Add module constants** `TIKTOK_DEFAULTS` and `FACEBOOK_DEFAULTS` per synthesis §3.
3. **Add `get_platform_defaults(url: str) -> PlatformDefaults`** in `config.py` — uses `url_parser.detect_platform`. Move import inside function to avoid circular import.
4. **In `downloader.py`** add `_jittered_sleep(mean: float, std: float, floor: float, rng: random.Random | None = None) -> None`:
   - `rng = rng or random` (module-level)
   - `delay = max(floor, rng.gauss(mean, std))`
   - `time.sleep(delay)`
5. **Update `download_batch` signature**: keep `delay: float = 1.0` for compat; add `delay_std: float = 0.3` (relative 30%) and `delay_floor: float = 0.2`.
6. **Replace `time.sleep(delay)` (line 146)** with `_jittered_sleep(delay, delay_std, delay_floor)`.
7. **Update `DownloadEngine.__init__`** to accept `delay_std: float = 0.3, delay_floor: float = 0.2`; replace `QTimer.singleShot(int(self.delay * 1000), ...)` with sample → `QTimer.singleShot(int(sample*1000), ...)`.
8. **Update `main.py`** `parse_args`: when `--delay` and `--workers` are *both* the argparse default sentinel (use `default=None`, then resolve), call `get_platform_defaults(urls[0])` to populate. If user passed values explicitly, use them as-is.
9. **Smoke-run** `python main.py <single-tiktok-url>` and `python main.py <single-fb-url>` to confirm no regressions.

## Todo List
- [ ] Add `PlatformDefaults` dataclass to `config.py`
- [ ] Add `TIKTOK_DEFAULTS` and `FACEBOOK_DEFAULTS` module constants
- [ ] Add `get_platform_defaults(url)` helper
- [ ] Add `_jittered_sleep()` to `downloader.py`
- [ ] Replace `time.sleep(delay)` at `downloader.py:146`
- [ ] Extend `download_batch` signature with `delay_std`, `delay_floor`
- [ ] Wire jitter into `DownloadEngine._on_worker_finished` `QTimer`
- [ ] Update `main.py` to fall back to platform defaults when `--delay`/`--workers` unset
- [ ] Manual smoke test: 1 TikTok URL + 1 FB URL

## Success Criteria
- `import config; config.TIKTOK_DEFAULTS.delay_mean == 1.5`
- `_jittered_sleep(1.5, 0.5, 0.2)` returns after a duration in `[0.2, ~3.0]`s in 1000 trials (statistical bound).
- `download_batch` with TikTok URLs sleeps `~1.5±0.5s` between completions; with FB URLs, `~3.0±1.5s`.
- Existing tests pass (`pytest test_*.py -q`).
- No new external dependency added.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `random.gauss` produces negative number → `time.sleep(-x)` raises | High (~16% per call) | Medium | `max(floor, sample)` clamp |
| Mixed-platform batch (TikTok + FB URLs interleaved) gets wrong delay | Medium | Medium | Apply per-URL: detect platform inside `_download_with_delay` and sleep with platform-specific params |
| Circular import `config ↔ url_parser` | Low | Low | Lazy-import `detect_platform` inside `get_platform_defaults` |
| User confused by jitter ("why is each download a different wait?") | Low | Low | Add brief docstring; expose `delay` as the *mean*, document in `--help` |

## Security Considerations
- None new. Jitter source is `random` (non-cryptographic, fine for timing). No PII or auth surface change.

## Next Steps
- Phase 02 builds on the per-platform `retries` value to wire `get_ydl_opts` retry tuning.
- Phase 03 uses `PlatformDefaults.workers` for FB serial-download default.
