# Phase 06 — Tests & Verification

## Context Links
- All preceding phases (01–05).
- Existing test files: `test_tiktokder.py`, `test_config.py`, `test_download_engine.py`, `test_channel_fetcher.py`.
- Synthesis: `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` §5 (anti-patterns to avoid in tests).

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** ~30 min
- **Description:** Unit tests for jitter helper, platform-defaults selection, error classifier, login-wall markers, retry policy (predicate + parser + decorator), shortlink resolver. Manual verification checklist for end-to-end runs against TikTok and Facebook URLs.

## Key Insights
- All five preceding phases are testable in isolation with stdlib mocks — no live network calls in unit tests.
- For tenacity decorator, test with a mock function that raises typed exceptions in sequence and assert call count + cumulative wait.
- For `resolve_fb_shortlink`, mock `curl_cffi.requests.Session.get` with `unittest.mock.patch`.
- For `_jittered_sleep`, inject a seeded `random.Random` to make timing deterministic; assert sample distribution is within expected bounds across 1000 trials.

## Requirements
**Functional**
- New test files (Python) added — kept under 200 lines each, kebab-cased only if creating new modules; following project convention `test_*.py`:
  - `test_retry_policy.py` — covers exceptions, predicate, parser, decorator behavior.
  - `test_facebook_resolver.py` — covers shortlink detection + mocked redirect/body-marker resolution.
  - Extend `test_config.py` — `PlatformDefaults`, `get_platform_defaults`, `FB_LOGIN_WALL_MARKERS`.
  - Extend `test_tiktokder.py` (or create `test_downloader.py` if too large) — `_jittered_sleep`, `_classify_error`.
- Manual verification checklist documented (steps for human to run + expected behavior).

**Non-functional**
- Tests run in <5s total (no network).
- Use `pytest` (already in `requirements.txt`).
- Use `unittest.mock.patch` for HTTP and yt-dlp mocking.

## Architecture
**Test matrix:**

| Component | Unit | Integration | Manual |
|---|---|---|---|
| `_jittered_sleep` | ✅ bounds + seeded determinism | — | — |
| `PlatformDefaults` / `get_platform_defaults` | ✅ TikTok/FB/unknown | — | — |
| `_classify_error` | ✅ all kinds + edge cases | — | — |
| `FB_LOGIN_WALL_MARKERS` | ✅ no false positives on benign HTML | — | — |
| `parse_retry_after` | ✅ digit + missing + invalid | — | — |
| `decorrelated_jitter` | ✅ growth pattern + cap | — | — |
| `_is_retryable` | ✅ all exception classes | — | — |
| `with_retry` decorator | ✅ retry count + reraise behavior | — | — |
| `is_fb_shortlink` | ✅ positive + negative | — | — |
| `resolve_fb_shortlink` | ✅ mocked 302→login, 302→canonical, 200+marker, timeout | — | — |
| `download_video` end-to-end | — | ✅ mock yt-dlp ydl.extract_info | ✅ live URL |
| `download_batch` jitter+platform | — | ✅ mock download_video | ✅ live URLs |

## Related Code Files
**Modify**
- `D:\Projects\tiktokder\test_config.py` — extend with platform-defaults and login-wall marker tests.
- `D:\Projects\tiktokder\test_tiktokder.py` — extend with `_jittered_sleep` + `_classify_error` tests (or split into `test_downloader.py` if file size warrants).

**Create**
- `D:\Projects\tiktokder\test_retry_policy.py` — exceptions, predicate, parser, decorator.
- `D:\Projects\tiktokder\test_facebook_resolver.py` — shortlink detect + resolve.

**Delete** — none.

## Implementation Steps

1. **`test_retry_policy.py`** — write cases:
   - `test_rate_limited_stores_retry_after`
   - `test_parse_retry_after_seconds`
   - `test_parse_retry_after_missing_returns_none`
   - `test_is_retryable_login_required_false`
   - `test_is_retryable_rate_limited_true`
   - `test_is_retryable_transient_failure_true`
   - `test_decorrelated_jitter_growth_within_cap` — assert `wait <= cap` for 100 iterations
   - `test_with_retry_calls_max_attempts_on_transient` — mock fn raising `TransientFailure`; assert called 3 times then re-raises
   - `test_with_retry_no_retry_on_login_required` — mock fn raising `LoginRequired`; assert called once

2. **`test_facebook_resolver.py`** — write cases:
   - `test_is_fb_shortlink_positive` (`fb.watch/abc`)
   - `test_is_fb_shortlink_negative` (`facebook.com/watch?v=`)
   - `test_resolve_redirect_to_login_returns_login_required` — mock 302 with `Location: /login/?next=...`
   - `test_resolve_redirect_to_canonical_returns_ok` — mock 302 to `facebook.com/watch?v=123`
   - `test_resolve_200_with_login_marker_returns_login_required` — mock 200 with `id="login_form"` in body
   - `test_resolve_200_clean_returns_ok`
   - `test_resolve_timeout_returns_unknown_fail_open`

3. **Extend `test_config.py`:**
   - `test_platform_defaults_tiktok_values`
   - `test_platform_defaults_facebook_values`
   - `test_get_platform_defaults_tiktok_url`
   - `test_get_platform_defaults_facebook_url`
   - `test_get_platform_defaults_unknown_url_falls_back_to_tiktok`
   - `test_fb_login_wall_markers_not_empty`
   - `test_fb_login_wall_markers_no_false_positive_on_benign_html`

4. **Extend `test_tiktokder.py`** (or new `test_downloader.py`):
   - `test_jittered_sleep_respects_floor` — seeded RNG, assert `>= floor`
   - `test_jittered_sleep_distribution_centered_on_mean` — 1000 samples, mean within `±0.1` of `mu`, std within `±0.1` of `sigma`
   - `test_classify_error_login_required` (each marker variant)
   - `test_classify_error_rate_limited`
   - `test_classify_error_not_found`
   - `test_classify_error_transient`
   - `test_classify_error_unknown_fallback`

5. **Run tests:** `pytest -q` from project root. Expected: all green, <5s.

6. **Manual verification checklist** (document in this file under "Manual Verification" below; not a test file). Operator runs through after merge.

## Manual Verification Checklist

After all phases merged, run from project root in a real shell:

1. **TikTok single video (happy path):**
   ```
   python main.py https://www.tiktok.com/@scout2015/video/6718335390845095173
   ```
   - Expected: video downloads to `./downloads/`, exit 0, no captcha redirect in logs.

2. **TikTok 10-URL batch with default delay:**
   ```
   python main.py --batch sample_urls_tiktok.txt
   ```
   - Expected: 10 videos download, between-completions wait visibly varies (gaussian), no two waits identical.

3. **Facebook fb.watch login-walled URL:**
   ```
   python main.py https://fb.watch/<known-private-or-login-walled-id>/
   ```
   - Expected: surfaces `error: login_required` in <2s, no yt-dlp retry storm in logs.

4. **Facebook public reel:**
   ```
   python main.py https://www.facebook.com/<public-page>/videos/<id>/
   ```
   - Expected: downloads successfully, delay between downloads ~3s ±1.5s.

5. **Mixed batch (TikTok + FB interleaved):**
   ```
   python main.py --batch sample_mixed.txt
   ```
   - Expected: TikTok URLs use ~1.5s delay, FB URLs use ~3.0s delay (per-URL, not per-batch average).

6. **Retry behavior (synthetic):** trigger transient failure (network blip during download) and confirm logs show `Retrying ... in N seconds`. Cap at 3 outer attempts.

7. **Existing test suite:** `pytest -q` — all green.

8. **GUI smoke (Windows):** launch `python app.py`, queue 3 URLs (mix), confirm UI updates with new error categories ("Login required", "Rate limited") instead of raw exception strings.

## Todo List
- [ ] Write `test_retry_policy.py` (~9 cases)
- [ ] Write `test_facebook_resolver.py` (~7 cases, mocked)
- [ ] Extend `test_config.py` (~7 cases)
- [ ] Extend `test_tiktokder.py` or create `test_downloader.py` (~7 cases)
- [ ] Run full pytest, confirm all green
- [ ] Walk through manual verification checklist above
- [ ] Update `docs/codebase-summary.md` with new modules (`retry_policy.py`, `facebook_resolver.py`)

## Success Criteria
- `pytest -q` passes for all new + existing tests in <5s.
- Coverage of new modules ≥80% (use `pytest --cov` if available; not enforced).
- All 8 manual checklist items pass on a Windows 11 dev machine.
- No regressions in existing GUI flow (downloads, history, cookie passthrough).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Mocked tests pass but real FB endpoint rejects pre-resolved URL | Medium | Medium | Manual checklist item 3+4 catches this on real URLs |
| Gaussian distribution test is statistical → flaky CI | Low | Low | Use seeded RNG; assert distribution shape, not exact values; 1000-sample buffer |
| `pytest --cov` not configured → coverage not enforced | Medium | Low | Coverage is informational; success criteria primary |
| Tenacity test slow due to actual sleep | Medium | Medium | Mock `tenacity.wait` to return 0 in tests; or use `tenacity.wait_none()` override |
| Manual checklist requires user to know "known login-walled URL" | Medium | Low | Document in checklist that any private FB video works, e.g. content from a friends-only post |

## Security Considerations
- Tests must not log real cookies or credentials in fixtures. Use synthetic strings.
- No real account credentials in test files — `cookiesfrombrowser` mocked, never invoked.

## Next Steps
- Once merged, monitor real-world TikTok 50-URL batch and FB 10-URL batch. If captcha incidents persist, escalate to P2 (token bucket / circuit breaker — out of current scope).
- Future enhancement: add `pytest --cov` to CI pipeline; add a `make test` target.

## Unresolved Questions
1. Should `pytest --cov` threshold be enforced in CI? (Outside this plan's scope; flag for project-manager.)
2. Manual verification step 8 (GUI smoke) — should it be automated via `pytest-qt`? (Defer to a follow-up plan; current effort budget excludes GUI test framework setup.)
