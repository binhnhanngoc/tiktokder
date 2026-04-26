# Plan: Prevent Rapid Profile-Switch Hang

**Goal:** Eliminate the GUI freeze that occurs when users rapidly switch saved channels (or hammer Browse / Refresh / Load-more). Add a visible busy indicator so users understand the app is working.

**Reports:** [scout-260427-0008-blocking-ui-actions.md](../reports/scout-260427-0008-blocking-ui-actions.md)

## Root cause

`gui/base_browser_panel.py:111-113` calls `self._fetcher.wait()` on the GUI thread when a new fetch is requested while one is already in flight. For Facebook (Playwright), `wait()` can block the UI for 3–30 s while the worker exits its current `page.wait_for_timeout()`. Saved-channels table double-click bypasses the existing `browse_btn.setEnabled(False)` guard.

## Solution (KISS / YAGNI)

1. Make fetch start non-blocking — never call `wait()` on the GUI thread.
2. While a fetch is in flight, disable every control that could trigger another fetch (saved-channels table double-click, context menu actions, Add/Refresh-all, Browse, Load-more, URL input).
3. Show an indeterminate `QProgressBar` and a Cancel button so the user has feedback + an escape hatch.
4. Old fetcher cleanly drains in background after Cancel — its signals are disconnected so its emissions are discarded.

## Phases

| # | Phase | Status |
|---|---|---|
| 1 | [Non-blocking fetch + busy indicator + control disable](phase-01-non-blocking-fetch.md) | completed |
| 2 | [Tests](phase-02-tests.md) | completed |

## Key dependencies

- PySide6 `QProgressBar` (built-in)
- No new packages
- All changes inside `gui/` (one base panel + one saved-channels panel)

## Out of scope

- Sequential auto-refresh for "Refresh all" (existing limitation, separate feature)
- Persistence debouncing for `_persist()` (impact too small — YAGNI)
- Async history loading (already reactive via `history_changed` signal)
