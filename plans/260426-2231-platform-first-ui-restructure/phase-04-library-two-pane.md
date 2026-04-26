# Phase 04 — Library two-pane (uploader sidebar + history table)

**Status:** pending
**Effort:** 0.5d
**Depends on:** Phase 02

## Context Links
- Plan: `plan.md`
- Brainstorm: §3.2.3
- Replaces: `gui/history_tab.py` Library presentation (filters/search/right-click menu logic ports as-is).

## Overview
Per-platform Library sub-tab: left pane = uploader list with video counts; right pane = filtered history table. Uses `history.json` directly — no schema change. Filters scoped to current platform implicitly (records loaded with `platform == self.platform`).

## Key Insights
- Reuse `_format_size`, `_format_date`, `_open_path`, context-menu logic from `gui/history_tab.py`. Move into `gui/library_panel.py` or a small `gui/_history_helpers.py` to avoid leaving orphan code in deprecated `history_tab.py`.
- Uploader sidebar = `QListWidget` with custom rows (`★ uploader (count)`). Star = uploader is in `saved_channels` for this platform.
- "All" pseudo-row at top → unfilters by uploader.
- `library_active_uploader` per platform stored in `AppState` for snapshot restore.

## Requirements
**Functional**
- Left pane: Uploader list, sorted by count desc; star prefix if uploader has a saved channel; counts in parens.
- Click uploader → table filters; click "All" → unfilters.
- Right pane: existing columns (Title / Quality / Size / Date / Path) — drop the redundant Platform column (whole tab is platform-scoped).
- Search box filters within selected uploader (or all).
- Right-click menu identical to current `HistoryTab` menu (Open file / Open folder / Re-download / Copy URL / Remove from history).
- Refresh on `engine.history_changed`.

**Non-functional**
- Uploader recompute uses Counter; O(n) per refresh — acceptable for 10k records.

## Architecture
```
gui/library_panel.py          (NEW, ~180 LOC)
  class LibraryPanel(QWidget):
    def __init__(self, platform: str, saved_store, parent=None)
    signals: redownload_requested(str url), remove_history_requested(str video_id)
    method: refresh()
    method: set_active_uploader(name | None)
    method: active_uploader() -> str | None

gui/_history_helpers.py       (NEW, ~50 LOC)
  _format_size, _format_date, _open_path  (extracted from history_tab.py)
```

## Related Code Files
**Create**
- `gui/library_panel.py`
- `gui/_history_helpers.py`
- `test_library_panel.py` (uploader recompute, filter behaviour, signal emission)

**Modify**
- `gui/platform_tab.py` — replace placeholder with `LibraryPanel(platform, saved_store)`.
- `gui/main_window.py`:
  - `library_panel.redownload_requested` → existing `_on_history_redownload`.
  - `library_panel.remove_history_requested` → existing `_on_history_remove`.
  - `engine.history_changed` → both platform tabs' `library_panel.refresh()`.
- `app_state.py` — add `library_active_uploader_tiktok: str | None`, `library_active_uploader_facebook: str | None` to `AppState`.

**Read for context**
- `gui/history_tab.py` — full reference; logic ports across.
- `history_store.py` — `HistoryRecord` shape.

## Implementation Steps
1. Extract helpers from `gui/history_tab.py` into `gui/_history_helpers.py` (don't yet delete `history_tab.py` — Phase 06).
2. Build `LibraryPanel`:
   - `QSplitter(Qt.Horizontal)`: left `QListWidget` (uploader sidebar), right `QWidget` containing search input + table.
   - `refresh()`:
     - `records = [r for r in load_history_records() if r.platform == self.platform]`
     - Recompute uploader Counter; rebuild left list with "All (N)" + per-uploader rows.
     - Apply current filter; render right table.
   - Star marker: cross-reference `saved_store.list_all(self.platform)` URLs vs uploader (best-effort match by uploader handle in URL — `@user1` etc.).
   - Right-click context menu — port verbatim from `history_tab.py`.
   - Search debounced 200 ms (reuse pattern from `history_tab.py:113-117`).
3. Extend `AppState` with `library_active_uploader_tiktok` / `library_active_uploader_facebook` (None default).
4. `MainWindow`:
   - On startup: `library_panel.set_active_uploader(state.library_active_uploader_*)`.
   - On snapshot: read `library_panel.active_uploader()` per platform.
5. Tests:
   - With 5 records (3 uploader A / 2 uploader B), uploader sidebar shows correct counts.
   - Click uploader A → only A rows in table.
   - Click "All" → all 5 rows.
   - "Remove from history" right-click → emits `remove_history_requested(video_id)`.
   - Star indicator appears for uploader B when saved-channel B exists.
   - Snapshot/restore round-trips active uploader.

## Todo List
- [ ] `gui/library_panel.py` created
- [ ] `gui/_history_helpers.py` created
- [ ] `AppState` extended with library fields; load/save tolerant
- [ ] `LibraryPanel` integrated into `PlatformTab` (replaces placeholder)
- [ ] Right-click menu actions wired through MainWindow
- [ ] `test_library_panel.py` ≥6 tests passing
- [ ] All existing tests (incl. `test_app_state.py`) still green

## Success Criteria
- Time-to-find-uploader < 3 s in dogfooding.
- Library refreshes automatically when engine completes a download.
- Active uploader survives app close/reopen.

## Risk Assessment
- **Star matching by uploader handle** — best-effort; if a saved channel URL parses to an uploader different from `HistoryRecord.uploader`, no star. Acceptable; can refine in follow-up.
- **Performance with 10k records** — Counter+filter is sub-100 ms in pure Python; QTableWidget with 10k rows is ~300 ms — acceptable. If slow in practice, add lazy population (defer Phase).

## Security Considerations
- File-open via `_open_path` already validated for path existence.

## Next Steps
Phase 05 splits Settings into Global + per-platform sections.
