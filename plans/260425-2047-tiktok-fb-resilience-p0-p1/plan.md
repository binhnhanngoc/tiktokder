---
title: "TikTok/FB Resilience P0+P1 — Detection-Evasion Hardening"
description: "Phased plan to add gaussian-jittered pacing, per-platform defaults, yt-dlp retry tuning, FB login-wall fast-fail, tenacity retry policy, and fb.watch pre-resolution."
status: completed
priority: P1
effort: 3h
branch: main
tags: [resilience, rate-limiting, tiktok, facebook, yt-dlp, retry]
created: 2026-04-25
completed: 2026-04-25
---

# TikTok/FB Resilience — P0 + P1 Implementation Plan

## Goal
Reduce silent FB blocks and TikTok throttling/captcha incidents by replacing fixed pacing, adding per-platform defaults, hardening yt-dlp retry config, fast-failing on login walls, wrapping `download_video` in `tenacity`, and pre-resolving `fb.watch` shortlinks. Scope is P0 + P1 from `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` only.

## Out of Scope
Token bucket / circuit breaker (P2), cookie pool rotation (single-user desktop), `nodriver` browser fallback (P4), captcha solver. Already-done items skipped: `curl_cffi`, `ImpersonateTarget("chrome","136")`, `cookiesfrombrowser`, `throttled_rate`, `socket_timeout`, `buffersize`.

## Source Reports
- `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` (synthesis)
- `plans/reports/researcher-1-260425-1302-tiktok-rate-limits.md`
- `plans/reports/researcher-2-260425-1302-facebook-rate-limits.md`
- `plans/reports/researcher-3-260425-1302-backoff-strategies.md`
- `plans/reports/researcher-4-260425-1304-proxy-fingerprinting.md`

## Phases

| # | Phase | Priority | Effort | Status | Depends |
|---|---|---|---|---|---|
| 01 | [Platform defaults + jittered pacing](phase-01-platform-defaults-and-jittered-pacing.md) | P0 | 35m | completed | — |
| 02 | [yt-dlp retry tuning](phase-02-yt-dlp-retry-tuning.md) | P0 | 25m | completed | 01 |
| 03 | [FB login-wall fast-fail](phase-03-fb-login-wall-fast-fail.md) | P0 | 20m | completed | 01 |
| 04 | [Tenacity retry policy](phase-04-tenacity-retry-policy.md) | P1 | 50m | completed | 02, 03 |
| 05 | [fb.watch shortlink pre-resolution](phase-05-fb-shortlink-pre-resolution.md) | P1 | 30m | completed | 03 |
| 06 | [Tests + verification](phase-06-tests-and-verification.md) | P1 | 30m | completed | 01–05 |

## Dependency Graph
```
01 ──┬──> 02 ──┐
     └──> 03 ──┼──> 04 ──> 06
              └──> 05 ─────^
```

## High-Level Acceptance Criteria
- TikTok URLs run with `delay≈1.5±0.5s` gaussian, `workers=3`, `retries=10`.
- Facebook URLs run with `delay≈3.0±1.5s` gaussian, `workers=1`, `retries=2`, no retry on login-wall.
- `download_video` raises typed exceptions: `LoginRequired`, `RateLimited`, `PermanentFailure`, `TransientFailure`.
- `fb.watch/...` 302→login is detected before yt-dlp invocation.
- `time.sleep(delay)` in `download_batch` is gone; replaced by `_jittered_sleep(mean, std, floor)`.
- All existing tests still pass; new tests cover platform detection, jitter bounds, login-wall markers, retry classification, shortlink resolution.
- `requirements.txt` adds `tenacity>=8.0.0`.

## Rollback Strategy
Each phase is a separate commit. Reverting phase N restores prior behavior without touching later phases (phase files isolate changes by module). Phase 06 is test-only and never blocks rollback.

## Backwards Compatibility
- `AppConfig.delay` and `AppConfig.workers` retained as global defaults; new `PlatformDefaults` overrides only when platform is detected. Saved configs from prior versions load unchanged.
- `download_video(url, output_dir, ...)` keeps current positional signature; new optional kwargs added at the end.
- CLI `--delay` and `--workers` keep current semantics; per-platform splits are *defaults*, not flags (user override still wins).

## Risk Summary
- **Med:** `tenacity` decorator changes exception surface — mitigated by typed exception module + adapter back to existing `DownloadResult.error` string.
- **Med:** Per-platform routing in `download_batch` requires URL→platform classification at submit time — mitigated by reusing `url_parser.detect_platform`.
- **Low:** Gaussian jitter floor needs to never go negative — mitigated by `max(floor, sample)` clamp + unit test.
- **Low:** `fb.watch` HEAD pre-resolve adds 1 round-trip — mitigated by 5s timeout, fail-open on network error (fall through to yt-dlp).

## Success Metrics (manual)
- TikTok 50-URL batch: zero captcha redirects in 3 consecutive runs (was: occasional captchas at workers=5/delay=0.5).
- Facebook 10-URL batch: login-wall URLs surface within 2s with `error="login_required"`, never retry.
- yt-dlp `[download] Got server HTTP 429` triggers tenacity backoff, logs `Retry-After` honored.
