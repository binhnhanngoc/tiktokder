---
title: "Show/hide downloaded videos in Channels browse"
description: "3-state Downloaded filter combo + checkmark column + per-platform AppConfig persistence + live history_changed updates on BaseBrowserPanel for TikTok and Facebook."
status: completed
priority: P2
effort: 4h
branch: main
tags: [gui, channel-browse, ux, history]
created: 2026-05-04
completed: 2026-05-04
blockedBy: []
blocks: []
---

# Plan — Channel browse Downloaded filter

## Goals

1. Add **3-state combo** `Downloaded: All / New only / Downloaded only` to
   `BaseBrowserPanel` filter row.
2. Add **`✓` column** showing downloaded state per row, sortable, with
   `downloaded_at` tooltip.
3. Persist combo state **per platform** in `AppConfig`.
4. **Live update** the column + filter via existing
   `download_engine.history_changed` signal.

## Brainstorm reference

- Design doc: [`../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md`](../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md)
- Locked decisions (combo style, marker style, persistence scope, bulk-action
  behavior) all confirmed via AskUserQuestion.

## Phases

| # | Phase | Status | File |
|---|-------|--------|------|
| 1 | History resolver wiring + `✓` column | completed | [phase-01-history-resolver-and-checkmark-column.md](phase-01-history-resolver-and-checkmark-column.md) |
| 2 | 3-state Downloaded combo + filter predicate | completed | [phase-02-downloaded-filter-combo.md](phase-02-downloaded-filter-combo.md) |
| 3 | AppConfig persistence + live history_changed updates | completed | [phase-03-persist-and-live-update.md](phase-03-persist-and-live-update.md) |
| 4 | Tests + docs sync | completed | [phase-04-tests-and-docs.md](phase-04-tests-and-docs.md) |

## Dependencies

- Phase 1 → no blockers; lays the column + resolver plumbing.
- Phase 2 → depends on Phase 1 (uses resolver in `_matches`).
- Phase 3 → depends on Phase 1+2 (combo must exist; column must rerender on signal).
- Phase 4 → depends on 1–3; gate for merge.

## Files Touched (full set across phases)

- `gui/base_browser_panel.py` — column, combo, predicate, resolver hook, signal listener.
- `gui/main_window.py` — wire resolver + `history_changed` to both panels; load/save combo state.
- `config.py` — two new `AppConfig` fields.
- `test_base_browser_panel.py` — new test cases.
- `README.md` + `docs/codebase-summary.md` (or equivalent) — feature note.

## Constraints

- YAGNI/KISS/DRY — reuse `_search_timer` debounce; reuse `NumericItem` for
  sort key; do not introduce new modules unless `base_browser_panel.py`
  exceeds 500 LOC after edits (current count ~490).
- No mutation of `_videos` list — same rule as existing filters.
- `CachedVideo` schema **unchanged** — downloaded-state recomputed at render
  time so manually-deleted files are correctly marked "new" again.
- `Select All` / `Download Selected` keep the existing "skip hidden rows"
  convention.

## Unresolved questions (carry forward from brainstorm)

1. Should `✓` column be user-hideable (right-click header)? **Decision:** out
   of scope; default visible.
2. Rename `Download Selected` → `Re-download Selected` when filter is
   `Downloaded only`? **Decision:** keep label uniform; tooltip optional in
   Phase 2.
3. `Downloaded — by date desc` extra combo option? **Decision:** rejected;
   sortable column covers it.
