# Brainstorm — Show/Hide Downloaded Videos in Channels Browse

- Date: 2026-05-04
- Scope: TikTok + Facebook Channels sub-tab → browser panel below saved-channel list
- Owner: nnbin

## Problem

Channels browse currently shows every video the fetcher returns. After several
"Download all new" runs, a saved channel's panel is dominated by already-grabbed
clips. User cannot quickly tell which rows are new vs old, and `Select All` ticks
both. Goal: let user **show, hide, or isolate** downloaded videos.

## Constraints / Reuse

- Detection is already cheap: `engine._history` (set of `video_id`) is exposed
  to UI via `history_ids_resolver` already wired in `gui/main_window.py:165-166`.
- `BaseBrowserPanel` already owns the filter row, debounced timer, and
  `setRowHidden` plumbing — bulk actions correctly skip hidden rows.
- `download_engine.py:130` emits `history_changed` after each persist —
  free hook for live row-marker refresh.
- `VideoInfo.video_id` is the dedup key in history.
- `AppConfig` (`config.py:82`) is the canonical settings home; adding
  per-platform string fields fits existing pattern.

## Decisions (locked-in via AskUserQuestion)

| # | Choice | Decision |
|---|--------|----------|
| 1 | Filter control | **3-state combo** `Downloaded: All / New only / Downloaded only` next to `Quality:` |
| 2 | Row marker (when shown) | **Checkmark icon column** (~24 px, sortable) before Title |
| 3 | Persistence | **Per-platform**, stored in `AppConfig` (`tiktok_browse_downloaded_filter`, `facebook_browse_downloaded_filter`) |
| 4 | Bulk action behavior | **Hidden rows ignored** — same convention as Search/Quality/Date filters today |

## Final Design

### UI

Filter row gains one control between `Quality:` and `From`:

```
[Quality: All ▾] [Downloaded: All ▾] [☐ From …] [☐ To …]
                       ├─ All
                       ├─ New only
                       └─ Downloaded only
```

Table gains one column at index 1 (between checkbox and Title):

```
│ ☐ │ ✓ │ Title                          │ Duration │ Quality │ Views │ Date │
│ ☐ │   │ Brand new clip                 │ 0:42     │ 1080p   │  12k  │ 5-04 │
│ ☐ │ ✓ │ Already grabbed last week      │ 0:31     │ 720p    │  88k  │ 4-26 │
```

- Header: `✓` (single-char) — narrow fixed-width column.
- Cell: `✓` glyph for downloaded, blank for new.
- Sortable via `NumericItem` (1 = downloaded, 0 = new) so user can group by
  status without changing the filter.
- Tooltip on the `✓` cell: `Downloaded YYYY-MM-DD HH:MM` (sourced from
  `HistoryRecord.downloaded_at`) — small affordance, no extra clicks.

Status label gets a count breadcrumb when the filter is active:
`Found 42 videos — showing 18 (24 already downloaded)`.

### Data flow

```
MainWindow injects history_ids_resolver onto BaseBrowserPanel
        │
BaseBrowserPanel
  ├─ on _on_video_found → write ✓ cell (resolver.contains(video_id))
  ├─ on filter change   → _apply_filters() also checks downloaded predicate
  ├─ on history_changed → _refresh_downloaded_column()  (light: rewrite cells + re-apply filter)
  └─ on _matches(video) → AND-in downloaded-state filter
```

`history_changed` already fires on every successful download, so a freshly
grabbed video flips its row from blank to ✓ in the same panel without a manual
refresh.

### Persistence

Two new `AppConfig` string fields, default `"all"`:

```python
tiktok_browse_downloaded_filter: str = "all"      # all | new | downloaded
facebook_browse_downloaded_filter: str = "all"
```

`MainWindow` reads these at startup and writes to the appropriate
`BaseBrowserPanel` setter; combo-change handler writes back through the
existing settings-persist path.

### Saved-channel cache interaction

`CachedVideo` does **not** store downloaded-state — it's recomputed at render
time from the live history set. Reason: user can manually delete a downloaded
file and re-download from the same browse panel without restart. Keeps
single-source-of-truth at history layer.

### "Download all new" interaction

`SavedChannelsPanel._download_all_new` already filters with the same history
set, so behavior is unchanged. The new filter is purely a **view** layer on
top of an existing predicate.

## Files to Touch

| File | Change |
|------|--------|
| `gui/base_browser_panel.py` | New combo, new column, new predicate clause, new resolver hook, new `history_changed` listener |
| `gui/main_window.py` | Wire `history_ids_resolver` + `engine.history_changed` to both browser panels; load/save AppConfig values |
| `config.py` | Two new `AppConfig` string fields |
| `gui/_table_items.py` | (No-op or tiny) — reuse `NumericItem` for downloaded sort key |
| `test_base_browser_panel.py` | New tests: marker render, filter predicate, status label, persistence round-trip |

Estimated diff: ~150–200 LOC across `base_browser_panel.py` + `main_window.py`,
plus tests. No new files.

## Risks

| Risk | Mitigation |
|------|-----------|
| Inserting a column shifts every existing column index | Centralised `_COL_*` constants already exist — bump them in one place |
| `history_changed` can fire often during batch downloads | `_refresh_downloaded_column()` is O(rows) and `_apply_filters` is already debounced for the typical path; wrap the listener in a 100 ms `QTimer.singleShot` coalescer |
| Sort by ✓ column should stay stable | Use `NumericItem(int_status, glyph)` — same pattern as Duration/Views |
| Default `"all"` may surprise existing users used to the old view | Same outcome as today; opt-in change is correct default |
| Saved-channel cache may include videos missing from `engine._history` after history-pruning trim (10k cap) | Treat missing → "new" — false positive risk is acceptable; user can re-download which dedup-skips anyway |

## Out of Scope (Won't Build Now)

- Showing downloaded badge in the **saved-channel list** itself (right now it
  just shows `Videos` count). Useful, but a separate brainstorm.
- Hiding downloaded videos from the **Library** tab (Library *is* the history;
  inverting it would need a different conversation).
- Bulk "Re-download all marked downloaded" action — easy follow-up if asked.

## Success Criteria

1. Toggling combo to `New only` hides every row whose `video_id ∈ history`.
2. Selecting a downloaded saved-channel after fresh download shows updated `✓`
   without manual `Browse` re-click (live update via `history_changed`).
3. Combo state persists across app relaunches per platform.
4. `Select All` + `Download Selected` ignore hidden rows (regression-safe;
   covered by existing convention).
5. Status label shows accurate `Found N — showing M (K already downloaded)`.
6. Existing saved-channel cache tests pass unchanged (cache schema untouched).

## Open Questions

1. Should the `✓` column be **toggleable** (right-click header → hide column)
   for users who never want to see it? Default-visible feels right for now.
2. When user picks `Downloaded only`, should `Download Selected` button rename
   to `Re-download Selected` or just keep one label? Suggest: keep label
   uniform for KISS; tooltip clarifies.
3. Should the combo include a fourth option `Downloaded — by date desc` (sort
   shortcut)? Probably overkill — sortable column already covers it.
