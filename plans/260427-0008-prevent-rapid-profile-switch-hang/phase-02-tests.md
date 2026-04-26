# Phase 2 — Tests

## Overview
- **Priority:** P1
- **Status:** pending

Verify the lifecycle by driving fetch_started/fetch_finished from a stub QThread and asserting widget enable/disable state.

## Implementation steps

1. Add tests to `test_saved_channels_panel.py` (existing offscreen Qt fixture):
   1. **`test_fetch_lifecycle_disables_saved_channels_controls`** — emit `fetch_started` from the browser panel; assert table + Add + Refresh-all are disabled; emit `fetch_finished`; assert re-enabled.
   2. **`test_browser_panel_progress_bar_visible_during_fetch`** — call `_start_fetcher` with a stub QThread that doesn't auto-start; assert progress bar visible, Cancel button visible, Browse disabled. Manually call `_on_fetch_done(0)`; assert hidden again.
   3. **`test_cancel_does_not_block_main_thread`** — start a stub fetcher whose `cancel()` records the call but `run()` simulates a long sleep on a side thread. Press Cancel; status label shows "Cancelling…" immediately (no GUI wait). Then emit `finished_fetch` and assert state cleans up.

2. Run all tests: `python -m pytest -q`

## Todo list

- [ ] Add stub `_StubFetcher(QThread)` helper in test file
- [ ] Add 3 lifecycle tests
- [ ] Verify all existing tests still pass

## Success criteria

- All new tests pass headless (`QT_QPA_PLATFORM=offscreen`).
- No flake from QThread timing (use direct signal emission, not real `start()` where possible).
- Total test runtime increase < 0.5s.
