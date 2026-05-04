# Phase 01 — History resolver wiring + `✓` column

## Context Links
- Plan overview: [plan.md](plan.md)
- Brainstorm: [`../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md`](../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md)
- Existing resolver pattern: `gui/main_window.py:165-166` (saved-channels panel)

## Overview
- **Priority:** P0 (blocks all later phases)
- **Status:** completed
- **Description:** Plumb a `history_ids_resolver` callback into
  `BaseBrowserPanel` and render a sortable `✓` column whose cells reflect
  whether `video.video_id ∈ history`. No filter combo yet — that lands in
  Phase 02.

## Key Insights
- `engine._history` is a `set[str]` of video IDs already exposed via
  `MainWindow` to `SavedChannelsPanel`. Same lambda pattern reused here.
- Column insertion shifts every existing column index — keep the
  `_COL_*` constants as the single source of truth.
- `NumericItem(int_status, glyph)` keeps sort stable and re-uses the
  Duration/Views idiom.

## Requirements
- Functional:
  - `BaseBrowserPanel` accepts `history_ids_resolver: Callable[[], set[str]] | None` (attribute, not constructor arg, mirroring `SavedChannelsPanel`).
  - Table inserts new column at index 1 between checkbox and Title.
  - Cell shows `✓` for downloaded, blank otherwise.
  - Tooltip on `✓` cell shows `Downloaded {YYYY-MM-DD HH:MM}` from `HistoryRecord.downloaded_at` when retrievable; falls back to plain "Downloaded" when record missing.
  - Column header: `✓` (single-char). Fixed width ~28 px via `setSectionResizeMode(_COL_DOWNLOADED, QHeaderView.ResizeMode.ResizeToContents)`.
- Non-functional:
  - Resolver call is O(1) (set lookup); per-row render stays O(1).
  - No regressions on existing column sort, filter, or save/restore paths.

## Architecture
```
MainWindow
  ├─ engine._history (set[str])
  ├─ engine._history_records ({video_id: HistoryRecord}) — already exists
  └─ injects two callables onto each BaseBrowserPanel:
      ├─ history_ids_resolver:    lambda: set(engine._history)
      └─ history_record_resolver: lambda vid: engine._history_records.get(vid)

BaseBrowserPanel._on_video_found(v)
  └─ writes _COL_DOWNLOADED cell using both resolvers
```

## Related Code Files
- Modify: `gui/base_browser_panel.py`, `gui/main_window.py`.
- Read for context: `gui/saved_channels_panel.py:471` (resolver pattern),
  `download_engine.py:130` (signal — used in Phase 03 only),
  `gui/_table_items.py` (`NumericItem`).
- No new files.

## Implementation Steps
1. **Add column constants** in `gui/base_browser_panel.py`:
   ```python
   _COL_CHECK = 0
   _COL_DOWNLOADED = 1
   _COL_TITLE = 2
   _COL_DURATION = 3
   _COL_QUALITY = 4
   _COL_VIEWS = 5
   _COL_DATE = 6
   _HEADERS = ("", "✓", "Title", "Duration", "Quality", "Views", "Date")
   ```
2. **Add resolver attributes** to `BaseBrowserPanel.__init__`:
   ```python
   self.history_ids_resolver: Callable[[], set[str]] | None = None
   self.history_record_resolver: Callable[[str], object | None] | None = None
   ```
3. **Configure header sizing** after `setHorizontalHeaderLabels`:
   ```python
   self.table.horizontalHeader().setSectionResizeMode(
       _COL_DOWNLOADED, QHeaderView.ResizeMode.ResizeToContents
   )
   ```
4. **Update `_on_video_found`** to populate the new cell using a new helper
   `_make_downloaded_item(video) -> NumericItem` that:
   - Reads `self.history_ids_resolver()` if set, else `set()`.
   - Returns `NumericItem(1, "✓")` with tooltip when downloaded.
   - Returns `NumericItem(0, "")` otherwise.
5. **Update default sort column** from `_COL_DATE` index `5` → `6` (the
   constant moves automatically; verify at `sortByColumn`).
6. **Wire `MainWindow`**:
   ```python
   for tab in (self.tiktok_tab, self.facebook_tab):
       panel = tab.channels_panel.browser_panel
       panel.history_ids_resolver = lambda: set(self.engine._history)
       panel.history_record_resolver = self.engine._history_records.get
   ```
   (Verify the exact attribute name on `engine` — `_history_records` may be
   named differently; fall back to `None` if absent and tooltip degrades to
   plain "Downloaded".)
7. **Compile check:** `python -m py_compile gui/base_browser_panel.py gui/main_window.py`.

## Todo List
- [x] Add column constants + headers tuple.
- [x] Add resolver attributes (default `None`).
- [x] Add `_make_downloaded_item` helper.
- [x] Update `_on_video_found` to write cell.
- [x] Set column resize mode in init.
- [x] Wire resolvers in `MainWindow.__init__`.
- [x] Verify default sort still hits Date column.
- [x] py_compile passes.

## Success Criteria
- Browse a saved TikTok channel that has at least one already-downloaded
  video — that row shows `✓`; new rows blank.
- Clicking the `✓` header sorts downloaded rows together.
- Hovering the `✓` cell shows download timestamp tooltip.
- No regression in existing tests (`test_base_browser_panel.py`,
  `test_saved_channels_panel.py`).

## Risk Assessment
- **Risk:** wrong `engine` attribute name for history records → tooltip degraded.
  - Mitigation: `getattr(engine, "_history_records", None)` + None-safe lookup.
- **Risk:** column shift breaks downstream callers reading `_COL_TITLE` by integer literal.
  - Mitigation: grep for raw `1` / `2` indices in `gui/`; replace any with constants.

## Security Considerations
None — pure UI plumbing on local data.

## Next Steps
Phase 02 wires the combo + predicate that consumes the resolver.
