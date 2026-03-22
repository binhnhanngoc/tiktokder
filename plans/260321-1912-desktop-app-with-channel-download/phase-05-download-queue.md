# Phase 5: Download Queue & Progress UI

## Context
- [plan.md](plan.md) | [phase-04](phase-04-channel-browser.md)
- Depends on: Phase 2, Phase 3

## Overview
- **Priority:** P1
- **Status:** complete
- **Description:** Download table with per-video progress bars, status indicators, queue management

## Requirements
### Functional
- QTableWidget columns: [URL/Title, Status, Progress, Size, Actions]
- Status values: Queued, Downloading, Complete, Failed, Skipped
- Per-row QProgressBar widget embedded in table
- Color-coded status (green=complete, red=failed, yellow=downloading, gray=queued)
- Right-click context menu: Cancel, Retry, Open file, Copy URL
- Clear completed/failed items button
- Overall progress in status bar (X/Y downloaded)

### Non-functional
- Table updates driven by DownloadEngine signals (no polling)
- Smooth progress bar updates
- Handle 100+ items without lag

## Architecture
```
gui/download_table.py (NEW)
  ├── DownloadTableWidget(QWidget)
  │   ├── QTableWidget with embedded QProgressBars
  │   ├── Context menu (cancel, retry, open, copy)
  │   └── Toolbar: Clear Completed, Cancel All
  └── Connected to DownloadEngine signals
```

## Related Code Files
### Create
- `gui/download_table.py` - download queue table widget

### Modify
- `gui/main_window.py` - embed DownloadTable in Download tab
- `gui/url_input_panel.py` - connect URL submission to DownloadEngine

## Implementation Steps
1. Create `gui/download_table.py`:
   - Subclass QWidget with QVBoxLayout
   - QTableWidget with columns: Title, Status, Progress, Size
   - Method `add_download(url: str)` - add row with Queued status
   - Slot `on_download_started(url)` - update status to Downloading
   - Slot `on_download_progress(url, percent)` - update progress bar
   - Slot `on_download_finished(url, result)` - update status, show title
   - Embed QProgressBar widget in progress column via `setCellWidget()`
   - Color status text based on state
2. Add context menu:
   - Right-click on row shows: Cancel, Retry Failed, Open File, Copy URL
   - Cancel: tell DownloadEngine to cancel specific URL
   - Retry: re-add failed URL to engine
   - Open File: open downloaded file in explorer
3. Add toolbar buttons above table:
   - "Clear Completed" - remove done rows
   - "Cancel All" - cancel all active downloads
4. Wire in MainWindow:
   - Place UrlInputPanel at top of Download tab
   - Place DownloadTable below
   - Connect signals: URL submitted -> engine.add_urls -> table.add_download
   - Connect engine signals to table slots
   - Update status bar with overall progress

## Todo
- [x] Implement DownloadTableWidget
- [x] Add context menu
- [x] Add toolbar buttons
- [x] Wire into MainWindow Download tab
- [x] Connect engine signals to table

## Success Criteria
- Adding URL shows row in table with Queued status
- Download progress updates smoothly in progress bar
- Completed downloads show green status
- Failed downloads show red with retry option
- Right-click menu works
- Status bar shows overall count
