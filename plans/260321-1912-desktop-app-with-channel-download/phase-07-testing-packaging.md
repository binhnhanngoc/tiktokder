# Phase 7: Testing & Packaging

## Context
- [plan.md](plan.md) | [phase-06](phase-06-settings-config.md)
- Depends on: All previous phases

## Overview
- **Priority:** P2
- **Status:** complete
- **Description:** Unit tests for new modules, integration smoke tests, PyInstaller packaging

## Requirements
### Functional
- Unit tests for: config.py, channel_fetcher.py, download_engine.py, url_parser additions
- GUI smoke tests (QApplication + widget instantiation, no full E2E)
- PyInstaller spec file for single-exe build
- Update README.md with GUI usage instructions

### Non-functional
- Maintain 67 existing tests passing
- New tests: target ~30 additional tests
- Exe size target: <80MB

## Related Code Files
### Create
- `test_config.py` - config load/save/defaults tests
- `test_channel_fetcher.py` - channel fetcher tests (mocked yt-dlp)
- `test_download_engine.py` - engine queue/signal tests
- `tiktokder.spec` - PyInstaller spec file

### Modify
- `test_tiktokder.py` - add tests for `is_channel_url()`
- `README.md` - add GUI section

## Implementation Steps
1. Write `test_config.py`:
   - Test default config creation
   - Test load/save roundtrip
   - Test history add/check/persist
2. Write `test_channel_fetcher.py`:
   - Mock yt-dlp to return fake playlist entries
   - Test VideoInfo dataclass
   - Test error handling
3. Write `test_download_engine.py`:
   - Test queue management (add, cancel)
   - Test signal emission with QSignalSpy or mock slots
   - Test history skip logic
4. Add to `test_tiktokder.py`:
   - Tests for `is_channel_url()`
5. Create `tiktokder.spec`:
   - PyInstaller config for single-file exe
   - Include PySide6 plugins
   - Set icon and metadata
6. Update README.md:
   - Add "Desktop App" section
   - Add screenshot placeholder
   - Document `python app.py` launch

## Todo
- [x] Write test_config.py
- [x] Write test_channel_fetcher.py
- [x] Write test_download_engine.py
- [x] Add is_channel_url tests
- [x] Create PyInstaller spec
- [x] Update README.md
- [x] Verify all tests pass
- [x] Test exe build

## Success Criteria
- All 67 existing tests pass
- ~30 new tests pass
- `pyinstaller tiktokder.spec` produces working exe
- README documents both CLI and GUI usage

## Risk Assessment
- PySide6 + PyInstaller: may need `--collect-all PySide6` flag
- Some GUI tests may need `QApplication` fixture (create once per session)
