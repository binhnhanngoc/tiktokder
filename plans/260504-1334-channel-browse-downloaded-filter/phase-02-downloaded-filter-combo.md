# Phase 02 — Downloaded filter combo + predicate

## Context Links
- Plan overview: [plan.md](plan.md)
- Brainstorm: [`../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md`](../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md)
- Depends on: [phase-01-history-resolver-and-checkmark-column.md](phase-01-history-resolver-and-checkmark-column.md)

## Overview
- **Priority:** P0
- **Status:** completed
- **Description:** Add the 3-state `Downloaded:` combo to the existing filter
  row, extend `_matches` predicate, and update status-label breadcrumb.

## Key Insights
- All filter signals already funnel through `self._search_timer` (200 ms
  debounce) — combo just hooks the same timer.
- `_matches` predicate runs per-row in `_apply_filters`; downloaded check is
  one set-membership lookup.
- Status text comes from `_apply_filters` end-of-method; extend the
  filtered-out branch.

## Requirements
- Functional:
  - New `QComboBox` placed between `Quality:` and `From` toggles.
  - Three items: `Downloaded: All` (data `"all"`), `New only` (`"new"`),
    `Downloaded only` (`"downloaded"`).
  - Default selection: `"all"` (Phase 03 will override from `AppConfig`).
  - Predicate AND-combines with existing search/quality/date filters.
  - Status label format when filter is non-default and any rows are hidden:
    `Found N videos — showing M (K already downloaded)`.
- Non-functional:
  - No new debounce timer; reuse `_search_timer`.
  - Combo respects `blockSignals` during programmatic load (Phase 03 needs
    this when restoring from config).

## Architecture
```
filter row:
  [Quality ▾] [Downloaded ▾] [☐ From …] [☐ To …]
                  │
_matches(video):
  needle / quality / date pass …
  AND downloaded_filter check:
      mode = "all"        → True
      mode = "new"        → video.video_id ∉ history
      mode = "downloaded" → video.video_id ∈ history
```

## Related Code Files
- Modify: `gui/base_browser_panel.py`.
- Read for context: existing `_build_filter_row` (lines ~155-194 today;
  shifted by Phase 01).
- No new files.

## Implementation Steps
1. **Add combo in `_build_filter_row`** (insert after `quality_combo` row addition):
   ```python
   self.downloaded_combo = QComboBox()
   self.downloaded_combo.addItem("Downloaded: All", "all")
   self.downloaded_combo.addItem("New only", "new")
   self.downloaded_combo.addItem("Downloaded only", "downloaded")
   row.addWidget(self.downloaded_combo)
   ```
2. **Wire to debounce timer** — extend the existing `for sig in (...)` block:
   ```python
   self.downloaded_combo.currentIndexChanged,
   ```
3. **Cache history set per filter pass** — at top of `_apply_filters`,
   compute once:
   ```python
   self._cached_history_ids = (
       self.history_ids_resolver() if self.history_ids_resolver else set()
   )
   ```
   Then `_matches` reads from `self._cached_history_ids` instead of calling
   the resolver per row (O(N) → O(1) resolver calls).
4. **Extend `_matches`**:
   ```python
   mode = self.downloaded_combo.currentData()
   if mode in ("new", "downloaded"):
       is_downloaded = (video.video_id or "") in self._cached_history_ids
       if mode == "new" and is_downloaded:
           return False
       if mode == "downloaded" and not is_downloaded:
           return False
   ```
5. **Update `_apply_filters` status-label tail** to break out the
   downloaded count when relevant:
   ```python
   downloaded_total = sum(
       1 for v in self._videos
       if (v.video_id or "") in self._cached_history_ids
   )
   if visible == total:
       self.status_label.setText(f"Found {total} videos")
   else:
       self.status_label.setText(
           f"Found {total} videos — showing {visible} ({downloaded_total} already downloaded)"
       )
   ```
6. **Compile check.**

## Todo List
- [x] Combo widget added with three items + data values.
- [x] Combo wired to `_search_timer`.
- [x] `_apply_filters` caches history ids once per pass.
- [x] `_matches` enforces downloaded predicate.
- [x] Status label includes `(K already downloaded)` breadcrumb.
- [x] py_compile passes.

## Success Criteria
- Selecting `New only` hides every row whose `✓` cell is set.
- Selecting `Downloaded only` shows only `✓` rows.
- Selecting `All` restores prior view.
- Status label updates live as combo changes.
- `Select All` + `Download Selected` skip hidden rows (existing behavior).

## Risk Assessment
- **Risk:** combo selection mid-fetch could leave new rows un-filtered.
  - Mitigation: `_on_video_found` already calls `_apply_filters` at end of
    each insertion, so each new row re-checks the predicate — covered.
- **Risk:** `video.video_id` may be `None` for legacy state restores.
  - Mitigation: predicate uses `(v.video_id or "")` and treats empty string
    as "not in history" → row classed as new. Acceptable.

## Security Considerations
None.

## Next Steps
Phase 03 persists combo state in `AppConfig` and adds live updates via
`engine.history_changed`.
