# Phase 1: Project Setup & Dependencies

## Context
- [plan.md](plan.md)
- Existing: `requirements.txt` with yt-dlp, rich, pytest

## Overview
- **Priority:** P1
- **Status:** complete
- **Description:** Add PySide6 dependency, create project structure, GUI entry point

## Key Insights
- PySide6 ~50-70MB exe when packaged; acceptable for desktop app
- Must keep CLI working alongside GUI (no breaking changes)
- Python 3.10+ required (already in place)

## Requirements
### Functional
- Add PySide6 to requirements
- Create `gui/` package with `__init__.py`
- Create `app.py` as GUI entry point with minimal QApplication bootstrap
- Create `config.py` for JSON-based settings (output dir, workers, delay)

### Non-functional
- All new files kebab-case where possible (Python modules use snake_case by convention)
- Each file under 200 LOC

## Related Code Files
### Modify
- `requirements.txt` - add PySide6

### Create
- `app.py` - GUI entry point
- `config.py` - settings manager (load/save JSON)
- `gui/__init__.py` - package init

## Implementation Steps
1. Add `PySide6>=6.6.0` to `requirements.txt`
2. Add `pyinstaller>=6.0.0` to requirements (for phase 7)
3. Create `gui/__init__.py` (empty or minimal)
4. Create `config.py`:
   - `AppConfig` dataclass: `output_dir`, `workers`, `delay`, `window_geometry`
   - `load_config(path)` / `save_config(config, path)` using JSON
   - Default config path: `~/.tiktokder/config.json`
5. Create `app.py`:
   - Initialize `QApplication`
   - Load config
   - Show `MainWindow` (placeholder until phase 2)
   - `sys.exit(app.exec())`

## Todo
- [x] Update requirements.txt
- [x] Create gui/ package
- [x] Implement config.py
- [x] Create app.py entry point
- [x] Verify PySide6 imports work

## Success Criteria
- `python app.py` launches empty window
- `python main.py --help` still works
- Config file created/loaded from `~/.tiktokder/config.json`

## Risk Assessment
- PySide6 install may be large (~200MB wheel) - acceptable
- No OS-specific risks on Windows 11
