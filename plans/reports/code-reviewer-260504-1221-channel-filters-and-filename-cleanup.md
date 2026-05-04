# Code Review — channel-filters-and-filename-cleanup

**Scope:** 14 files (gui/base_browser_panel.py, downloader.py, path_builder.py, channel_fetcher.py, facebook_fetcher.py, gui/library_panel.py, gui/_table_items.py + 5 test files + 5 docs).
**Verdict:** **FIX-FIRST** — one real correctness bug in live-fetch + sort + filter interaction; everything else verified or low-impact.

---

## Critical

### C1. `BaseBrowserPanel._on_video_found`: `setRowHidden` is called against the wrong row when sort reorders the freshly-inserted row

**File:** `gui/base_browser_panel.py:264-301`

**Reproduction (verified):**

```python
panel = _Panel(placeholder="…")
panel.from_date_check.setChecked(True)
panel.from_date_edit.setDate(QDate(2024, 1, 1))
v_old = VideoInfo(..., upload_date="20200101")  # should be hidden
v_new = VideoInfo(..., upload_date="20250101")  # should be visible
panel._on_video_found(v_old)
panel._on_video_found(v_new)

# Result:
#   row 0: NEW 2025  hidden=False  (correct)
#   row 1: OLD 2020  hidden=False  (WRONG — should be hidden!)
```

**Root cause:**

```python
self.table.setSortingEnabled(False)
row = self.table.rowCount()         # captured BEFORE insert: e.g. 1
self.table.insertRow(row)           # row 1 now holds v_new
# … fill cells …
self.table.setSortingEnabled(True)  # ← Qt sorts; v_new (newer date) jumps to row 0
                                    #              v_old slides DOWN to row 1
self.table.setRowHidden(row, not self._matches(video))
                                    # ← `row=1` now points at v_old, but
                                    #   _matches(video=v_new) returns True →
                                    #   setRowHidden(1, False) un-hides v_old
```

The captured `row` index is stale post-sort. Worse: this can **un-hide** a previously-hidden row, since `setRowHidden(staleIndex, False)` clobbers whatever row landed there.

Qt docs/forums explicitly warn about this: "As soon as you set/insert an item, table will automatically sort again and the just inserted item will be moved to some new row, but you will still try use the old row number, and things get messed up." ([Qt Forum reference](https://forum.qt.io/topic/112844/qtablewidget-strange-behaviour))

**Test gap:** the suite (`test_base_browser_panel.py`) always calls `_apply_filters()` after pushing rows, which iterates by index and re-reads the VideoInfo from `UserRole` — that path is sound. The bug only hits during **live fetch with an active filter** (which is the new feature this PR ships).

**Fix options (any of these works):**

1. **Cleanest:** locate the row of the just-inserted video by scanning for the matching UserRole pointer:
   ```python
   self.table.setSortingEnabled(True)
   target = next(
       (r for r in range(self.table.rowCount())
        if self.table.item(r, _COL_TITLE).data(Qt.ItemDataRole.UserRole) is video),
       row,
   )
   self.table.setRowHidden(target, not self._matches(video))
   ```
2. **Simpler:** call `_apply_filters()` instead of `setRowHidden(row, ...)` — already iterates correctly. Slightly wasteful (re-evaluates every row per insert) but safe. Mirrors LibraryPanel's full-rebuild pattern.
3. **Cheapest, less defensive:** stop calling `setRowHidden` per-insert; let `_apply_filters` (called from `_on_fetch_done`) handle it. Trades live-incremental hiding for a single pass at fetch end. UX: filter momentarily looks loose during fetch — probably acceptable since search debounce already accepts a 200 ms lag.

Recommend **option 1** — preserves the live-incremental-filter UX without thrashing the whole table on each insert.

---

## Important

### I1. `_update_status_during_fetch` reflects the same stale-index bug

**File:** `gui/base_browser_panel.py:303-312`

Status reads `isRowHidden(r)` for all rows — fine on its own — but because of C1, hidden state is wrong for live-inserted rows under filter, so the displayed "Found N videos — showing M" count is also wrong. Fixing C1 fixes this transitively.

### I2. `quality_combo.findData(current)` after `clear()` may briefly emit `currentIndexChanged(-1)` despite `blockSignals`

**File:** `gui/base_browser_panel.py:196-206`

`blockSignals(True)` is correctly applied across `clear()` and `addItem()` calls so this is mostly moot, but worth a sanity check: `_rebuild_quality_combo()` is called from `_on_fetch_done` — running on the GUI thread, no race. Verified safe; mentioning only because the same idiom in LibraryPanel uses the identical pattern.

### I3. `os.path.exists(rec.file_path)` race: history record exists at predicate evaluation, gone before download

**File:** `downloader.py:317`

The check is TOCTOU-correct for dedup purposes (worst case: video re-downloaded if the file is deleted between scan and download — that's the desired behavior). Not a bug, just noting that this is intentional.

### I4. Test missing for the C1 bug

After fixing C1, add a regression test:
```python
def test_live_insert_with_filter_and_sort_does_not_unhide(qapp):
    panel = _Panel(placeholder="…")
    panel.from_date_check.setChecked(True)
    panel.from_date_edit.setDate(QDate(2024, 1, 1))
    panel._on_video_found(VideoInfo(..., upload_date="20200101"))  # OLD
    panel._on_video_found(VideoInfo(..., upload_date="20250101"))  # NEW

    rows = {panel.table.item(r, 1).text(): r for r in range(panel.table.rowCount())}
    assert panel.table.isRowHidden(rows["OLD 2020"]) is True
    assert panel.table.isRowHidden(rows["NEW 2025"]) is False
```

---

## Nice-to-have

### N1. Filename worst-case Windows path

`<base>\facebook\<uploader 80>\<title 80> [<id 6>].mp4` = 102 chars over the base-dir prefix. With a 158-char base path the total exceeds Windows MAX_PATH (260). yt-dlp + Python both honor long-path support if enabled in the OS, but standard installs of older Windows 10 still fail at 260. Same risk existed pre-change (`<id 19>_<title 50>.mp4` was actually shorter). Document or auto-truncate; not a blocker.

### N2. `CRLF` warnings on every file from git

The working tree has Unix line endings; on commit Git will normalize. Cosmetic — confirm `.gitattributes` rules match team intent before merge.

---

## Verified

- **`_path_under` Windows semantics** — confirmed with `python -c` runs:
  - Cross-drive (`C:\Windows\win.ini` vs `D:\...\downloads`) → `ValueError: Paths don't have the same drive` → caught → returns `False`. ✓
  - `..` traversal (`D:/...\downloads/../../../Windows/win.ini`) → `realpath` resolves to `D:\Windows\win.ini` → `commonpath` returns `D:\` ≠ `D:\...\downloads` → `False`. ✓
  - Case-insensitive Windows: `realpath` canonicalizes casing on Python 3.13 even for non-existent paths; comparison is sound. ✓
  - UNC vs drive (`//server/share` vs `D:\...`) → ValueError → False. ✓
  - Empty parent or empty child → fast-fail returns False. ✓
- **`get_downloaded_ids` behavior change when `output_dir` doesn't exist** — old: empty set. New: still consults history, but `_path_under` requires `realpath(child)` under `realpath(parent)` AND `os.path.exists(file_path)`. If the file exists, dedup correctly skips; otherwise nothing leaks. Safe.
- **Empty/null titles** — `yt-dlp.prepare_filename({'title': '', ...})` and `{'title': None, ...}` both render to `NA [777777].mp4` — clean, no leading-space artifact.
- **`_videos` no-mutation invariant** — filter only calls `setRowHidden`; `_videos` mutated only in `clear()` / `append()` / `_on_video_found()`. `SavedChannelsPanel._on_dl_new_clicked` (`gui/saved_channels_panel.py:433`) reads `getattr(self.browser_panel, "_videos", [])` — unaffected.
- **`get_ydl_opts` callers** — only `_do_download` calls it (downloader.py:355); engine routes through `download_video` → `_do_download` which always rewrites `outtmpl`. No bypass paths.
- **Filter race on GUI thread** — `_on_video_found` and `_apply_filters` both fire on the GUI thread (signals/timers). No concurrency issue. Verified.
- **`upload_date_from_entry`** — handles `int`/`float` epoch, rejects non-numeric, catches `OverflowError`/`OSError` for out-of-range timestamps. Returns UTC date — timezone-stable.
- **`_matches` predicate edge cases** — rows with `upload_date is None` or `""` correctly hide when From/To filter is enabled (verified live).
- **`setRowHidden` persistence across header sort clicks** — Qt preserves visibility across sort; only the visible-row order changes. Verified by reading `setSortingEnabled` flow.
- **Test suite** — 473/473 pass (`pytest -q`); 7 new browser-panel tests + 4 new dedup-union tests cover the documented surface.

---

## Recommended Actions

1. **Block merge** until C1 is fixed (option 1 above) and a regression test (I4) is added.
2. After C1 fix: re-run `pytest test_base_browser_panel.py -v` to confirm.
3. Optional: track N1 for a later phase if anyone hits MAX_PATH issues.

## Unresolved Questions

- Should "Download Selected" warn when 0 visible rows match a filter that hides everything — or silently no-op (current behavior)?
- Does the Quality combo lag during live fetch ever cause user confusion when they hit "Download Selected" before `_on_fetch_done` runs `_rebuild_quality_combo`? (Acceptable per spec; flagging for product UX.)

---

**Status:** DONE_WITH_CONCERNS
**Summary:** One blocking correctness bug (C1) — `setRowHidden` uses pre-sort row index in `_on_video_found`, hiding the wrong row and silently un-hiding a previously-filtered row. Reproduced empirically. All other security and correctness checks pass.
**Concerns/Blockers:** C1 must be fixed before ship — affects the headline feature (live filtering during fetch).
