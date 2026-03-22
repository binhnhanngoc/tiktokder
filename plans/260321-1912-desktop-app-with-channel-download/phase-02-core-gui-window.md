# Phase 2: Core GUI Window & Layout

## Context
- [plan.md](plan.md) | [phase-01](phase-01-project-setup.md)
- Depends on: Phase 1

## Overview
- **Priority:** P1
- **Status:** complete
- **Description:** Build main window with tab layout, URL input panel, and placeholder areas

## Key Insights
- QTabWidget for separating Download/Channel/Settings views
- QMainWindow with status bar for global state display
- URL input should accept both single video URLs and channel/profile URLs

## Requirements
### Functional
- Main window with title "TikTokDer" and reasonable default size (900x600)
- Tab widget with 3 tabs: "Download", "Channel", "Settings"
- URL input panel: QLineEdit + "Add" button + "Paste from clipboard" button
- Auto-detect if pasted URL is channel vs single video
- Status bar showing download count / queue status

### Non-functional
- Window position/size restored from config
- Native Windows look and feel

## Architecture
```
MainWindow (QMainWindow)
  ├── MenuBar (File > Exit, Help > About)
  ├── QTabWidget
  │   ├── Tab "Download" -> UrlInputPanel + DownloadTable (phase 5)
  │   ├── Tab "Channel"  -> ChannelBrowser (phase 4)
  │   └── Tab "Settings" -> SettingsDialog (phase 6)
  └── StatusBar
```

## Related Code Files
### Create
- `gui/main_window.py` - QMainWindow subclass with tabs
- `gui/url_input_panel.py` - URL input widget (QLineEdit + buttons)

### Modify
- `app.py` - wire MainWindow instead of placeholder
- `url_parser.py` - add `is_channel_url()` helper

## Implementation Steps
1. Add `is_channel_url(url) -> bool` to `url_parser.py`:
   - Matches `tiktok.com/@username` (without `/video/` suffix)
2. Create `gui/main_window.py`:
   - Subclass QMainWindow
   - Setup menu bar (File > Exit)
   - Setup QTabWidget with 3 tabs
   - Status bar with download counter label
   - Save/restore geometry from config on close/open
3. Create `gui/url_input_panel.py`:
   - QHBoxLayout: QLineEdit + QPushButton("Add") + QPushButton("Paste")
   - On Add: validate URL, emit `url_submitted(str)` signal
   - On Paste: read clipboard, populate QLineEdit
   - Auto-detect channel vs video URL, emit appropriate signal
4. Update `app.py` to instantiate MainWindow

## Todo
- [x] Add is_channel_url to url_parser.py
- [x] Implement gui/main_window.py
- [x] Implement gui/url_input_panel.py
- [x] Wire MainWindow in app.py

## Success Criteria
- Window opens with 3 tabs, correct title and size
- URL input accepts text, validates, emits signal
- Paste button reads clipboard
- Window geometry restored on relaunch
