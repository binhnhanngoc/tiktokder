# Phase 4 — Tests

**Status:** ✅ complete (2026-05-02) · **Priority:** P1 · **Effort:** S (~2h) · **Risk:** Low

## Context

- Files: new `test_health_check.py` (project root, matching existing convention), additions to `test_settings_split.py` (or new `test_health_widgets.py`).
- Covers Phases 1–3.

## Goal

Lock in 6 health signals at the data layer + smoke the UI plumbing. No GUI screenshot tests — too brittle for what's a small visual change.

## Requirements

- ≥1 test per signal (6 total).
- 1 test for `compute_health` orchestrator wiring + cache load/save.
- 1 test for `record_fetch_outcome` mutating the cache.
- 1 test for the `dismiss_issue` flow.
- 2 widget smoke tests: pill color flips on `set_health_report`; settings group rebuilds rows on `set_health_report`.
- 1 integration-ish test: synthetic SavedChannel + HistoryRecord fixtures → `compute_health` returns the expected issue IDs.

## Architecture

```
test_health_check.py
├── test_stale_channel_threshold     (14d info, 31d warn)
├── test_auth_wall_likely_signal     (empty fetch + cookies set)
├── test_no_new_downloads_30d        (saved channel but no recent history)
├── test_login_required_marker       (record_fetch_outcome → flagged)
├── test_cookies_old_thresholds      (60d warn, 121d error)
├── test_yt_dlp_outdated_thresholds  (cached version compare)
├── test_compute_health_empty_inputs
├── test_compute_health_caches_pypi
├── test_dismiss_issue_persists_across_loads
└── test_record_fetch_outcome_writes_cache

test_health_widgets.py  (or extend test_settings_split.py)
├── test_status_pill_color_flips_on_severity
├── test_settings_health_group_rebuilds_on_report
└── test_dismiss_button_emits_dismiss_signal
```

## Related Code Files

**Create:**
- `test_health_check.py`.
- Optionally `test_health_widgets.py` — or fold into `test_settings_split.py` if smaller.

**Read for context:**
- `test_history_records.py` — fixture pattern for HistoryRecord lists.
- `test_saved_channels_store.py` — fixture pattern for SavedChannel.
- `test_settings_split.py` — Qt widget test bootstrap (`QApplication` fixture).

## Implementation Steps

1. Write `test_health_check.py` with a `monkeypatch`-friendly `now` injection:
   ```python
   def test_stale_channel_threshold():
       channels = [SavedChannel(url="...", last_fetched_at=_iso_days_ago(20))]
       report = compute_health(channels, [], _cfg(), now=_fixed_now())
       assert any(i.id.startswith("stale_fetch:") and i.severity == "info" for i in report.issues)
   ```
2. Each signal test isolates one trigger: build only the inputs that fire it, assert exactly that issue ID appears.
3. PyPI cache test: monkeypatch `urllib.request.urlopen` to return a fake JSON response, assert `compute_health(..., check_yt_dlp=True)` populates the cache; second call within 24h doesn't hit network.
4. Widget tests: build a `QApplication` once via pytest fixture (already exists in `test_settings_split.py` — reuse).
5. Pill color test: `widget.set_health_report(_report_with_warn())`; assert `widget.health_pill.property("severity") == "warn"`.
6. Settings group rebuild test: `panel.set_health_report(_report_with_3_issues())`; assert `panel.health_list.count() == 3`.
7. Dismiss test: spy on signal via `QSignalSpy` (or simple list-append slot); click row's "×" button; assert signal fired with right ID.

## Todo List

- [x] `test_health_check.py` — 26 tests (6 signals + orchestrator + cache + dismissals + CLI + frozen branch + FB cookies dispatch).
- [x] `test_health_widgets.py` — 8 widget smoke tests (pill flips, settings rebuild, dismiss/fix signals, manual refresh, empty state).
- [x] All tests pass under `pytest -v` — 428/428 across the full suite.
- [x] Coverage: `health_check.py` 87%, `health_signals.py` 85%, combined 86% — meets ≥85% target.

## Success Criteria

- All new tests pass on CI.
- Existing test suite stays green (no regressions in `test_saved_channels_store.py`, `test_history_records.py`).
- `pytest --cov=health_check` reports ≥85%.

## Risks

| Risk | Mitigation |
|---|---|
| Time-based assertions flaky | Always inject `now` parameter; never use real `datetime.now()` in tests. |
| Qt fixture collisions | Reuse existing `qapp` fixture pattern from `test_settings_split.py`. |
| Network test hits real PyPI | Always monkeypatch urlopen; never rely on real network. |

## Security Considerations

None.

## Next Steps

Plan complete. Ship to `main`. Move on to in-app player plan (`260502-1502-in-app-player`).
