# Phase 03 — Global URL bar + status bar with platform badges

**Status:** pending
**Effort:** 0.5d
**Depends on:** Phase 02

## Context Links
- Plan: `plan.md`
- Brainstorm: §3.1, §3.4
- Replaces: per-tab URL input (currently in `gui/url_input_panel.py` + `gui/download_tab.py`).

## Overview
Add a single URL bar above all tabs. Pasting/dropping a URL auto-detects platform via `url_parser.detect_platform` and routes to that platform's queue. Drag-drop `.txt` splits by platform. Status bar shows `TT: N · FB: N · Done: K · Ready/...`.

## Key Insights
- The bar lives on `MainWindow.menuBar()` adjacent area or as a top widget above `QTabWidget` (use a `QHBoxLayout` wrapper as `centralWidget` content).
- `QStatusBar` is already created by `QMainWindow`; replace single `status_label` with three labels + state text.
- Auto-routing also switches the active tab, mimicking today's "switch to Channel tab" UX (`MainWindow._on_channel_url`).

## Requirements
**Functional**
- `GlobalUrlBar`:
  - QLineEdit with placeholder "Paste URL or drop .txt here".
  - "Add" button (also triggers on Enter).
  - Drag-drop for both URL strings and `.txt` files.
  - Emits `urls_submitted: list[str]` (already validated, may span both platforms).
- `StatusBarWidget`:
  - 4 labels: TikTok queued, Facebook queued, total done, free-text status.
  - Updated on every `engine.download_started/finished` and on queue mutations.
- Mixed `.txt`: each line passed through `validate_url` + `detect_platform`; lines that match neither are dropped silently (log to status text).

**Non-functional**
- Bar height ≤ 28 px (slim — preserves vertical space).

## Architecture
```
gui/global_url_bar.py        (NEW, ~80 LOC)
  class GlobalUrlBar(QWidget):
    signals: urls_submitted(list[str])  # already-validated mixed-platform list

gui/status_bar_widget.py     (NEW, ~70 LOC)
  class StatusBarWidget(QWidget):  # added via QMainWindow.statusBar().addPermanentWidget
    method: set_counts(tt_queued, fb_queued, done, status_text)
```

## Related Code Files
**Create**
- `gui/global_url_bar.py`
- `gui/status_bar_widget.py`
- `test_global_url_bar.py` (drop parsing + platform splitting)
- `test_status_bar_widget.py` (counter math)

**Modify**
- `gui/main_window.py`:
  - Wrap central widget in `QVBoxLayout` containing `GlobalUrlBar` then `QTabWidget`.
  - Replace `self.status_label` with `StatusBarWidget`.
  - Wire `global_url_bar.urls_submitted` → `_on_urls_submitted` (splits by platform, calls each `PlatformTab.queue_panel.add_download` + `engine.add_urls`, switches active tab to the platform of the first URL).
  - Update `_update_status_count` to call `StatusBarWidget.set_counts` (count rows per platform from each `PlatformTab.queue_panel`).
  - Drop `gui/url_input_panel.py` import (deletion in Phase 06).

**Read for context**
- `gui/download_tab.py:56-99` — drag-drop logic (port to `GlobalUrlBar`).
- `url_parser.py:75-82, 91-106` — `detect_platform`, `read_batch_file`.

## Implementation Steps
1. **`gui/global_url_bar.py`**:
   - Composite QWidget: QLineEdit + Add button.
   - `setAcceptDrops(True)`; copy `dragEnterEvent` / `dropEvent` from `gui/download_tab.py`.
   - On submit/Enter: split text by whitespace; validate; emit list.
2. **`gui/status_bar_widget.py`**:
   - Three QLabels + spacer + status QLabel.
   - `set_counts(tt, fb, done, text)` updates all four.
3. Modify `gui/main_window.py`:
   - Build new central widget structure.
   - Add `_count_queue(platform)` helper that walks `tab.queue_panel._row_data` and sums non-terminal rows.
   - In `_update_status_count`: compute `(tt_q, fb_q, done)` and pass to `StatusBarWidget`.
   - In `_on_urls_submitted(urls)`: group by `detect_platform`, dispatch each group to its PlatformTab.queue + engine.
4. Tests:
   - Drop a `.txt` with 2 TikTok + 3 FB URLs → `urls_submitted` emits all 5 in order.
   - `StatusBarWidget.set_counts(2, 3, 7, "Ready")` updates labels correctly.
   - `_on_urls_submitted` splits and routes mixed batch.

## Todo List
- [ ] `gui/global_url_bar.py` created with drag-drop
- [ ] `gui/status_bar_widget.py` created
- [ ] `MainWindow` wires both widgets; central layout updated
- [ ] Status bar reflects per-platform queue + done in real time
- [ ] Mixed `.txt` import routes correctly per platform
- [ ] All existing tests pass

## Success Criteria
- Drop a mixed `.txt` → URLs land in correct platform queues.
- Status bar shows `TT: 2 · FB: 3 · Done: 0 · Ready` after the drop.
- Active tab switches to platform of first URL on drop.

## Risk Assessment
- **Per-platform count source of truth** — using each `PlatformTab.queue_panel._row_data` keeps counts coherent with what the user sees. Don't double-count from engine state.

## Security Considerations
- Drop handler validates URLs strictly — invalid drops silently dropped (consistent with current behaviour in `gui/download_tab.py`).

## Next Steps
Phase 04 replaces the Library placeholder with the two-pane history view.
