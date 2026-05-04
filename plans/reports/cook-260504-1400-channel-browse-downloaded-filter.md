---
type: implementation-report
plan: ../260504-1334-channel-browse-downloaded-filter/plan.md
date: 2026-05-04
status: completed
---

# Cook report — channel-browse Downloaded filter

## Outcome
- All 4 phases shipped on `main`. Compile + 485-test suite green.

## Files touched
- `gui/base_browser_panel.py` — column shift, `_COL_DOWNLOADED`, `_make_downloaded_item`, `downloaded_combo`, `_cached_history_ids`, `set_downloaded_filter`, `on_history_changed`, `_refresh_downloaded_state`, 100 ms coalesce timer.
- `gui/main_window.py` — resolver wiring on both browser panels, lazy `HistoryRecord` cache invalidated on `engine.history_changed`, restore + persist + connect of per-platform combo state, `_save_browse_filter` slot.
- `config.py` — `tiktok_browse_downloaded_filter` + `facebook_browse_downloaded_filter` (`"all"` default).
- `test_base_browser_panel.py` — 9 new tests + 2 patched for column shift.
- `test_config.py` — 2 round-trip tests.
- `README.md` — Channel Browse Filters bullet extended.
- `docs/codebase-summary.md`, `docs/code-standards.md`, `docs/project-changelog.md` — updated module summary, public API note, Unreleased entry.

## Departures from plan
- Engine has no `_history_records` dict; instead added `_lookup_history_record` on `MainWindow` with a lazy by-id cache (`_history_records_cache`) invalidated on `engine.history_changed`. Tooltip degrades to plain "Downloaded" when record is missing — exactly the fallback the plan called out.
- Existing `test_table_sorting_enabled_default_date_desc` and `test_live_insert_with_active_filter_and_sort_keeps_visibility_correct` referenced raw integers (5 / 1) for column indices; switched them to `_COL_DATE` / `_COL_TITLE` imports — needed because Phase 1 shifts indices.

## Verification
- `python -m py_compile config.py gui/base_browser_panel.py gui/main_window.py` — clean.
- `python -m pytest -q` — 485 passed, 1 unrelated `pytest.mark.slow` warning.

## Unresolved questions
None. The brainstorm-locked decisions (visible by default, uniform button label, sortable column instead of a 4th combo option) all landed unchanged.
