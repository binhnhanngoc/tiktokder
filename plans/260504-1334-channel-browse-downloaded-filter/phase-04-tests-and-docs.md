# Phase 04 — Tests + docs sync

## Context Links
- Plan overview: [plan.md](plan.md)
- Depends on: phase-01, phase-02, phase-03

## Overview
- **Priority:** P1 (gate for merge)
- **Status:** completed
- **Description:** Cover the new column + combo + persistence + live update
  paths with `pytest` cases. Update README and any docs files that mention
  channel-browse filters.

## Key Insights
- `test_base_browser_panel.py` already constructs the panel with a fake
  fetcher and pumps videos in — extend it. No need for full GUI app.
- Tests must inject a deterministic `history_ids_resolver` returning a
  controlled set so they are not coupled to `engine`.
- Docs note in README must say the filter exists, defaults to `All`, and
  persists per platform.

## Requirements
- Test cases:
  1. **Column rendered** — when resolver reports `{"abc"}` and a video has
     `video_id="abc"`, the `_COL_DOWNLOADED` cell text is `"✓"`.
  2. **`New only` hides downloaded rows.**
  3. **`Downloaded only` hides new rows.**
  4. **`All` shows everything.**
  5. **Status label** reads `Found N — showing M (K already downloaded)`
     when filter active.
  6. **`set_downloaded_filter` is signal-blocked** — programmatic restore
     must NOT trigger a duplicate `_apply_filters` cascade. Assert via spy.
  7. **`on_history_changed` coalesces** — call 5 times in a row, advance
     the Qt event loop past 100 ms, observe `_refresh_downloaded_state`
     called exactly once.
  8. **`Select All` skips hidden rows** when `New only` filter is active
     and some rows are downloaded → only new rows get checked.
  9. **AppConfig round-trip** — write+read both new fields.

- Docs:
  - `README.md` "Features → Channel Browse Filters" bullet appended.
  - `docs/codebase-summary.md` (or whichever doc lists `BaseBrowserPanel`
    responsibilities) updated.

## Architecture
No code architecture changes; test files only.

## Related Code Files
- Modify: `test_base_browser_panel.py`, `test_config.py` (if exists; else
  add a small round-trip test inline).
- Modify: `README.md`, `docs/*.md` as relevant.
- Read for context: existing tests in `test_base_browser_panel.py` for
  style.

## Implementation Steps
1. **Extend `test_base_browser_panel.py`**:
   - Helper `_make_panel_with_history(qtbot, history_ids: set[str])`.
   - One test per case enumerated above.
   - Use `QSignalSpy` or a method-level monkeypatch for the coalesce test.
2. **Add AppConfig test** — either extend `test_config.py` if present, or
   add `test_app_config_browse_filter_roundtrip` using `tmp_path`.
3. **Update README.md** — append to existing "Channel Browse Filters"
   bullet:
   ```markdown
   plus a Downloaded filter (`All` / `New only` / `Downloaded only`) and
   a sortable `✓` marker column. Per-platform setting persists across
   relaunches.
   ```
4. **Update `docs/codebase-summary.md`** (or `docs/system-architecture.md`)
   `BaseBrowserPanel` section — note the new resolver hooks and combo.
5. **Run** `pytest -v test_base_browser_panel.py test_config.py` (or full
   suite if quick).
6. **Lint** — `ruff check gui/base_browser_panel.py gui/main_window.py
   config.py` (if ruff is the project linter).

## Todo List
- [x] Test: `✓` cell rendered when video.id ∈ history.
- [x] Test: `New only` predicate.
- [x] Test: `Downloaded only` predicate.
- [x] Test: `All` predicate.
- [x] Test: status-label breadcrumb format.
- [x] Test: `set_downloaded_filter` signal-blocked.
- [x] Test: `on_history_changed` coalesce 5→1.
- [x] Test: `Select All` skips hidden rows under `New only`.
- [x] Test: `AppConfig` round-trip both fields.
- [x] README updated.
- [x] codebase-summary / system-architecture updated.
- [x] All tests pass.

## Success Criteria
- `pytest -v` exits 0.
- README clearly mentions the new filter.
- `docs/` reflects the new resolver hooks on `BaseBrowserPanel`.

## Risk Assessment
- **Risk:** `test_base_browser_panel.py` imports may not include `qtbot`.
  - Mitigation: existing tests already use the harness — copy-paste pattern.
- **Risk:** coalesce test is timing-flaky on slow CI.
  - Mitigation: use `qtbot.wait(150)` + assert call-count instead of
    timing-sensitive comparisons.

## Security Considerations
None.

## Next Steps
Merge ready after tests + docs land. No follow-up phase planned. Possible
future enhancement (out of scope): downloaded-count badge in saved-channel
list.
