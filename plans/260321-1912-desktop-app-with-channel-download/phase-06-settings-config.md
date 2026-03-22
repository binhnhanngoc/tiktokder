# Phase 6: Settings & Configuration

## Context
- [plan.md](plan.md) | [phase-05](phase-05-download-queue.md)
- Depends on: Phase 1 (config.py), Phase 2

## Overview
- **Priority:** P2
- **Status:** complete
- **Description:** Settings panel for output directory, concurrency, delays, and download history

## Requirements
### Functional
- Output directory picker (QFileDialog)
- Worker count spinbox (1-10)
- Delay between downloads spinbox (0.0-10.0s)
- Cookie browser selection dropdown (None, Chrome, Firefox, Edge)
- "Reset to Defaults" button
- Settings auto-save on change
- Download history: track downloaded video IDs in JSON to skip re-downloads across sessions

### Non-functional
- Settings persist in `~/.tiktokder/config.json`
- Download history in `~/.tiktokder/history.json`

## Related Code Files
### Create
- `gui/settings_panel.py` - settings UI widget

### Modify
- `config.py` - add history management (load/save downloaded IDs)
- `download_engine.py` - check history before downloading

## Implementation Steps
1. Create `gui/settings_panel.py`:
   - QFormLayout with labeled controls
   - Output directory: QLineEdit + Browse button (QFileDialog)
   - Workers: QSpinBox (min=1, max=10)
   - Delay: QDoubleSpinBox (min=0.0, max=10.0, step=0.5)
   - Cookie browser: QComboBox (None, Chrome, Firefox, Edge)
   - Reset Defaults button
   - Connect value changes to config.save_config()
2. Extend `config.py`:
   - Add `cookie_browser: str | None` field to AppConfig
   - Add `load_history() -> set[str]` / `save_history(ids: set[str])`
   - History file: `~/.tiktokder/history.json` (list of video IDs)
3. Integrate history with DownloadEngine:
   - On engine init, load history
   - Before downloading, check if video_id in history -> skip
   - After successful download, add video_id to history and save

## Todo
- [x] Implement gui/settings_panel.py
- [x] Extend config.py with history management
- [x] Integrate history into DownloadEngine
- [x] Wire settings panel into MainWindow Settings tab

## Success Criteria
- All settings editable and persisted
- Download history prevents re-downloads across app restarts
- Reset to Defaults works
- Output directory picker opens native file dialog
