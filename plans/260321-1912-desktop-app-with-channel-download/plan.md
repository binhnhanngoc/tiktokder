---
title: "Convert TikTokDer CLI to Desktop App with Channel Download"
description: "Add PySide6 desktop GUI and channel/profile video listing to existing TikTok downloader"
status: complete
priority: P1
effort: 12h
branch: feat/desktop-app
tags: [gui, pyside6, desktop, channel-download]
created: 2026-03-21
completed: 2026-03-21
---

# TikTokDer Desktop App

Convert CLI tool to PySide6 desktop application while preserving CLI backward compatibility.

## Current State
- 3 Python files: `main.py` (CLI), `downloader.py` (yt-dlp wrapper), `url_parser.py` (validation)
- ThreadPoolExecutor for concurrent downloads, Rich for CLI progress
- 67 unit tests covering URL parsing, downloader options, CLI args

## Target State
- PySide6 desktop app with download queue, channel browser, settings
- New `app.py` entry point for GUI; `main.py` stays as CLI
- QThread-based download engine with signal-driven progress updates
- Channel video listing via yt-dlp `--flat-playlist`

## Architecture

```
main.py          (CLI entry - unchanged)
app.py           (GUI entry - NEW)
url_parser.py    (shared - minor additions for channel URL detection)
downloader.py    (shared - refactored: extract core logic from Rich UI)
download_engine.py  (NEW - QThread wrapper, Qt signals for progress)
gui/
  main_window.py    (main window layout, menu, toolbar)
  url_input_panel.py (URL input + channel paste area)
  download_table.py (QTableWidget with progress bars)
  channel_browser.py (list channel videos, select/deselect)
  settings_dialog.py (output dir, workers, delay config)
config.py        (JSON-based settings persistence)
```

## Phases

| # | Phase | Status | Effort | File |
|---|-------|--------|--------|------|
| 1 | Project setup & dependencies | complete | 1h | [phase-01](phase-01-project-setup.md) |
| 2 | Core GUI window & layout | complete | 2h | [phase-02](phase-02-core-gui-window.md) |
| 3 | Download engine refactor (QThread) | complete | 2h | [phase-03](phase-03-download-engine.md) |
| 4 | Channel/profile video listing | complete | 2h | [phase-04](phase-04-channel-browser.md) |
| 5 | Download queue & progress UI | complete | 2h | [phase-05](phase-05-download-queue.md) |
| 6 | Settings & configuration | complete | 1.5h | [phase-06](phase-06-settings-config.md) |
| 7 | Testing & packaging | complete | 1.5h | [phase-07](phase-07-testing-packaging.md) |

## Key Decisions
- **PySide6** over Tkinter/PyQt: best table widgets, LGPL license, native look
- **Keep CLI**: `main.py` unchanged, GUI is additive
- **No Selenium**: yt-dlp native profile support handles most cases
- **JSON config** over SQLite: simpler, sufficient for settings + download history
- **Modular GUI**: each widget in its own file (<200 LOC each)
