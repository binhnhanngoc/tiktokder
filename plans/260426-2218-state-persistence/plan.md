# Plan: UI State Persistence (Download queue + Channel/Page browse)

**Date:** 2026-04-26
**Slug:** state-persistence
**Status:** Completed

## Goal

Persist volatile GUI state across app sessions:
1. **Download tab queue** — restore rows (URL, status, title) on reopen.
2. **Channel/Page tab** — restore last URL + fetched videos per platform sub-panel; remember active sub-tab.
3. **Active main tab** — restore which top-level tab the user was on.

State is interruptive-safe: no auto-resume of downloads, user manually clicks Retry.

## User Decisions
- No auto-resume of pending/in-flight downloads on launch
- Clear All wipes saved state immediately
- Channel browser: single snapshot per platform (URL + videos), no multi-URL history

## Architecture

```
config.py
  └─ STATE_PATH = CONFIG_DIR / "state.json"

app_state.py (NEW)
  ├─ AppState (dataclass)
  ├─ QueueItemState
  ├─ VideoInfoState
  ├─ BrowserPanelState
  ├─ load_state(path) -> AppState
  └─ save_state(path, state) -> None

app.py
  └─ on exit: build AppState from MainWindow → save_state()
  └─ on launch: load_state() → MainWindow(state=...)

gui/main_window.py
  └─ accept optional state, restore on init, expose snapshot() method
gui/download_table.py
  └─ load_from_state(items), snapshot() → list[QueueItemState]
  └─ Clear All also clears saved state file
gui/channel_browser.py
  └─ snapshot() / restore_from(state)
gui/base_browser_panel.py
  └─ load_from_state(state), snapshot() → BrowserPanelState
gui/facebook_browser_panel.py
  └─ override snapshot/restore for max_scrolls
```

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | Create `app_state.py` module | Done |
| 2 | Wire load/save in `app.py` and `MainWindow` | Done |
| 3 | Snapshot/restore in download table | Done |
| 4 | Snapshot/restore in channel browser panels | Done |
| 5 | Tests + final integration | Done (14 new tests, 282 total pass) |

## Files

**Create:**
- `app_state.py`
- `test_app_state.py`

**Modify:**
- `config.py` — add `STATE_PATH`
- `app.py` — load/save state lifecycle
- `gui/main_window.py` — accept state, restore, snapshot, hook Clear All
- `gui/download_table.py` — `load_from_state`, `snapshot`, signal on Clear All
- `gui/base_browser_panel.py` — `load_from_state`, `snapshot`
- `gui/facebook_browser_panel.py` — extend for `max_scrolls`
- `gui/channel_browser.py` — aggregate snapshot/restore + active sub-tab
- `docs/codebase-summary.md` — document new module

## Key Design Choices

**Why separate `state.json` (not `config.json`)?**
- State changes frequently (every close), config rarely
- State can be large (hundreds of VideoInfo rows); keep config small/readable
- Crash on state save shouldn't corrupt config

**Why `Downloading` → `Cancelled` on restore?**
- App was killed mid-download; the row is no longer downloading
- Cancelled is a recognized terminal state with Retry available

**Why no auto-fetch on Channel restore?**
- Browse fetches are slow (FB scraping = many seconds)
- User may want to view results without re-hitting the network

## Success Criteria

- Close app with 5 queued downloads + Facebook URL/videos → reopen → all restored verbatim
- Status of completed/failed/skipped rows preserved
- Clear All deletes both table and `state.json` queue section
- Active tab + active channel sub-tab restored
- All existing tests still pass
- New `test_app_state.py` covers load/save/migrate/empty/malformed
