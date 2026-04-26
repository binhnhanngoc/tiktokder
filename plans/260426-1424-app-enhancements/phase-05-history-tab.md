---
title: "Phase 05 — History tab"
priority: P0
effort: 1h 15m
status: planned
depends: [01]
---

# Phase 05 — History Tab (4th Top-Level Tab)

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ History UI, § Polish features)
- Depends on Phase 01 (`load_history_records`, `HistoryRecord`).
- New file: `gui/history_tab.py`.

## Overview
Add a top-level `History` tab listing all v2 records with rich columns, live search, platform filter, stats summary, and right-click row menu. Refreshes when engine emits a new record. Filenames open via OS-native handler.

## Key Insights
- `Re-download` and `Remove from history` need engine access. Tab emits Qt signals; `MainWindow` wires them.
- `Open file` / `Open containing folder`: cross-platform via `os.startfile` on Windows, `subprocess.Popen(["open", path])` macOS, `subprocess.Popen(["xdg-open", path])` Linux.
- Stats summary (total count, total size, per-platform count, top-5 uploaders) computed in-memory on each refresh — lists ≤10K rows are tiny.
- Live search: filter by case-insensitive substring across `title`, `uploader`, `url`. Use `QSortFilterProxyModel` for performance.

## Requirements

### Functional
- Tab columns: `Title | Platform | Uploader | Quality | Size | Date | Path` (7 columns, Title stretches).
- Search line above table — filters all rows live.
- Platform combo `All / TikTok / Facebook` — additional filter.
- Stats labels: `Total: N | Size: X MB | TikTok: a | Facebook: b | Top: u1, u2, ...`
- Right-click row menu:
  - `Open file` → opens the video in OS-default player. If file missing, show toast "File no longer exists".
  - `Open containing folder` → opens explorer/finder at the folder.
  - `Re-download` → emits `redownload_requested(url)`; MainWindow forwards to engine with `force=True`.
  - `Copy URL` → clipboard.
  - `Remove from history` → emits `remove_history_requested(video_id)`; MainWindow updates store + refreshes.
- Tab refreshes on `engine.history_changed` signal (added in Phase 07).

### Non-Functional
- `gui/history_tab.py` ≤ 250 LOC. If exceeds, split row-menu logic into `history_tab_actions.py`.
- Search debounced (200ms `QTimer`) to avoid filter-storm on long lists.

## Architecture

### Widget Layout
```
HistoryTab (QWidget)
├── HBox: search QLineEdit + platform QComboBox
├── HBox: stats QLabel(s)
└── QTableView (or QTableWidget) wired to QSortFilterProxyModel
```

### Signals (out)
```python
redownload_requested = Signal(str)        # video URL (or rebuilt from record)
remove_history_requested = Signal(str)    # video_id
```

### Slots (in)
```python
@Slot()
def refresh(self) -> None: ...            # re-loads records, recomputes stats, repopulates table
```

### Stats Computation
```python
def _compute_stats(records: list[HistoryRecord]) -> dict:
    total = len(records)
    size = sum(r.size_bytes or 0 for r in records)
    by_platform = Counter(r.platform or "unknown" for r in records)
    top_uploaders = Counter(r.uploader for r in records if r.uploader).most_common(5)
    return {"total": total, "size": size, "by_platform": by_platform, "top_uploaders": top_uploaders}
```

### File-Open Helpers
```python
import os, sys, subprocess

def open_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return True

def open_folder(path: str) -> bool:
    return open_file(os.path.dirname(path))
```

## Related Code Files

### To Create
- `gui/history_tab.py` — widget, model, signals, slots.

### To Modify
- `gui/main_window.py` — add 4th tab, wire signals to engine; subscribe to `engine.history_changed` to call `history_tab.refresh()`.
- `download_engine.py` (Phase 07) — emits `history_changed` signal on each persisted record.

### Not Touched This Phase
- `config.py` — already provides `load_history_records` from Phase 01.

## Implementation Steps
1. Define `HistoryTab(QWidget)` with the layout above.
2. Implement `refresh()` — read via `load_history_records()`, populate table, recompute stats labels.
3. Implement search + platform-combo filtering. Use a debounced QTimer on `textChanged`.
4. Implement context menu via `customContextMenuRequested` → `QMenu`. Wire each action.
5. Implement file-open helpers (cross-platform).
6. Add `redownload_requested(str)` and `remove_history_requested(str)` signals.
7. In `main_window.py`: instantiate `HistoryTab`, add as 4th tab, wire signals (history-tab → engine for redownload, history-tab → config for remove + refresh).
8. Defer the engine `history_changed` emission to Phase 07; for now, refresh on tab `showEvent` so reopening tab shows latest.
9. Smoke: download a video, click History tab, verify row appears.

## Todo
- [ ] Create `gui/history_tab.py` skeleton.
- [ ] Layout: search input, platform combo, stats labels, table.
- [ ] `refresh()` populates table from `load_history_records()`.
- [ ] Stats computation + label rendering.
- [ ] Search + platform filter (debounced).
- [ ] Context menu actions: open file, open folder, re-download, copy URL, remove.
- [ ] File-open helpers cross-platform.
- [ ] Wire into `main_window.py` as 4th tab.
- [ ] Signal hookup (re-download → engine; remove → store + refresh).
- [ ] Manual smoke.

## Success Criteria
- History tab visible after Download / Channel-Page / *History* / Settings.
- Records appear with correct columns; missing fields render `—`.
- Search filters rows in < 100ms for 10K rows.
- Right-click on a row shows all 5 menu items.
- `Open file` works on at least Windows host (dev environment).
- Remove from history removes the row and persists to disk.
- Re-download enqueues the URL with `force=True`.

## Risk & Mitigation
- **File path may be stale** (user moved file) → `Open file` checks existence, shows transient status-bar warning.
- **Long uploader list inflates stats label** → cap at top-5.
- **Refresh storm on rapid downloads** → engine emits `history_changed` once per completion, debounced not needed because frequency is bounded by network.

## Security
- File-open helpers receive paths from history records (user-controlled by file location). Always pass via `open`/`xdg-open`/`startfile` — these do not execute as shell commands. No shell=True.
- Path normalization prevents `..` traversal; `os.path.realpath` once when reading.

## Next Steps
- Phase 07 wires `engine.history_changed` to `history_tab.refresh()` for live updates.
