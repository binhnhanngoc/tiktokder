# Phase 1 — Browse panel filter + sort row

## Context Links

- Reference: `gui/library_panel.py` (`_build_filter_row`, `_NumericItem`, debounce timer)
- Target: `gui/base_browser_panel.py` (shared by TikTok + Facebook browse)
- Consumer: `gui/saved_channels_panel.py` reads `browser_panel._videos` for "Download new only" — must NOT be affected by filter

## Overview

- **Priority:** P2
- **Status:** pending
- **Description:** Add a top filter row + search box + sortable headers to `BaseBrowserPanel` so users can narrow large channel listings before downloading. Mirrors LibraryPanel idioms.

## Key Insights

- Top filter row beats inline column filters here — `BaseBrowserPanel` uses raw `QTableWidget` with `setCellWidget(row, 0, checkbox)`. A `QSortFilterProxyModel` swap would be a much larger refactor with no UX win. Top row matches the pattern users already know from Library.
- `_videos: list[VideoInfo]` is the source of truth and is read by `SavedChannelsPanel` for "Download new only". Filtering must hide rows in the table only — never mutate `_videos`. Implementation: stash each row's matching `VideoInfo` reference on the cell's UserRole, then call `self.table.setRowHidden(row, not matches)`.
- `_on_video_found` currently inserts directly into the table. After filter row exists, it must call the predicate and apply `setRowHidden` immediately so freshly fetched rows respect the active filter.
- Sortable headers via `self.table.setSortingEnabled(True)` plus a numeric-aware `_NumericItem` for Duration / Views / Date columns (date items sort by the original `YYYYMMDD` string which is already lexicographic-sortable, but numeric-int avoids "—" comparison issues).
- Bottom-row "Select All / Deselect All" must operate on **visible rows only** (otherwise users select hidden rows by accident). Update `_set_all_checks` to skip rows where `isRowHidden(row)`.
- "Download Selected" already iterates by row; same fix applies — only emit URLs for visible+checked rows.

## Requirements

### Functional
- Search box debounced 200ms; matches title (case-insensitive substring).
- Quality combo populated dynamically from observed values per fetch (clear+repopulate at end of fetch).
- From/To date checkboxes + `QDateEdit` controls; disabled until checked. Date compares against `VideoInfo.upload_date` (`YYYYMMDD` form).
- Sortable headers: click to sort by Title, Duration, Quality, Views, Date.
- Filter applies to currently fetched videos AND to rows added during ongoing fetch.

### Non-functional
- No mutation of `self._videos`. Filter is view-only.
- No reflow flicker — disable sorting during bulk inserts in `load_from_state`, re-enable after.

## Architecture

```
BaseBrowserPanel
├── url_input row (existing)
├── progress_bar (existing)
├── status_label (existing)
├── ── new ── filter row (search + quality + from/to date)
├── table (now sortable, _NumericItem for numeric cols)
└── bottom row (select all/none, download selected)

filter signal flow:
    search/combo/dateedit → debounce timer (200ms) → _apply_filters()
    _on_video_found(video) → insertRow → setRowHidden(row, not _matches(video))
```

## Related Code Files

**Modify:**
- `gui/base_browser_panel.py` — add filter row, debounce timer, `_NumericItem`-backed cells, `_apply_filters`, row-hidden visibility check in `_set_all_checks` + `_on_download`.

**Read (no edits):**
- `gui/library_panel.py` — `_build_filter_row`, `_NumericItem`, debounce idiom
- `gui/saved_channels_panel.py` — confirms `_videos` consumption pattern

**Create:** none.

## Implementation Steps

1. Lift `_NumericItem` from `library_panel.py` into a shared module: keep it in `library_panel.py` for now and **import** it from `base_browser_panel.py`. (DRY without overengineering.) If the import creates a cycle, move it to `gui/_table_items.py` and update both call sites.
2. In `BaseBrowserPanel.__init__`, between status_label and table:
   - Build `_filter_row` QHBoxLayout with: `search_input` (QLineEdit, placeholder "Search title…"), `quality_combo` (QComboBox, default "Quality: All"), `from_date_check` + `from_date_edit`, `to_date_check` + `to_date_edit`, addStretch.
   - Wire each control to `self._search_timer.start()` (single QTimer, 200ms, singleShot, calls `_apply_filters`).
3. Set `self.table.setSortingEnabled(True)` after column setup. Default sort: Date desc.
4. Replace plain `QTableWidgetItem` with `_NumericItem` for Duration (sort by seconds), Views (sort by raw int), Date (sort by `YYYYMMDD` int — fall back to 0 when missing).
5. Stash `VideoInfo` on the title cell's `Qt.ItemDataRole.UserRole` so `_apply_filters` can re-evaluate without scanning text cells.
6. Add `_apply_filters(self)`:
   - Disable sorting (perf).
   - For each row, fetch `VideoInfo` from UserRole, run predicate (search, quality, from/to date), call `setRowHidden(row, not matches)`.
   - Re-enable sorting.
   - Update status_label with "Showing N of M".
7. Update `_on_video_found` to apply the predicate to the new row immediately (or call `_apply_filters` once after insert — simpler, slightly slower; acceptable since fetch is human-paced).
8. Add `_rebuild_quality_combo` called in `_on_fetch_done(total)` — preserves selection like LibraryPanel does.
9. Update `_set_all_checks(value)` to skip `self.table.isRowHidden(row)`.
10. Update `_on_download` to skip hidden rows.

## Todo List

- [ ] Move/import `_NumericItem` (decide location).
- [ ] Add filter row UI in `BaseBrowserPanel.__init__`.
- [ ] Add debounce timer + signal wiring.
- [ ] Add `_apply_filters` method.
- [ ] Convert numeric cells to `_NumericItem`.
- [ ] Stash `VideoInfo` on title cell UserRole.
- [ ] Enable `setSortingEnabled` + default sort.
- [ ] `_on_video_found` applies filter to new row.
- [ ] `_rebuild_quality_combo` after fetch.
- [ ] Hide-aware `_set_all_checks` + `_on_download`.
- [ ] Manual smoke: TikTok + Facebook browse, large list (>100 videos), confirm filter + sort + select-all-visible behavior.

## Success Criteria

- Searching "foo" hides rows whose title doesn't contain "foo".
- Quality combo lists only qualities present in current fetch.
- From/To date narrows view by `upload_date`.
- Click on Duration/Views/Date headers sorts numerically (not lexically).
- "Select All" only checks visible rows.
- "Download Selected" only emits URLs of visible+checked rows.
- `_videos` count unchanged after filter (no mutation).

## Risks

- **Numeric sort on missing values**: `view_count=None`, `duration=None`, `upload_date=None` rows. Mitigation: store 0 (or -1 for "missing first" UX) as `_NumericItem._sort_value`.
- **Quality combo flicker** on each fetch — mitigated by `blockSignals` during rebuild (matches LibraryPanel pattern).
- **`setRowHidden` + `setSortingEnabled` interaction**: hidden rows persist visibility across sorts. Verified working in LibraryPanel pattern; smoke test required.
- **Saved-channel restore path** (`load_from_state`) — calls `_on_video_found` per row. Filter applies automatically; no extra change needed.

## Security Considerations
None — filtering is view-only on data already in memory.

## Next Steps

- Proceed to Phase 2 (Date column) which makes the date filter useful.
- Phase 1 ships fine without Phase 2; date filter just won't match anything until Date column is populated.
