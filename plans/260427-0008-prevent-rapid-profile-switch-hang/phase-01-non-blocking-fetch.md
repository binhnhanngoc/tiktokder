# Phase 1 — Non-blocking fetch + busy indicator + control disable

## Overview
- **Priority:** P0 (user-reported hang)
- **Status:** pending

Replace the blocking `fetcher.wait()` with a signal-based handoff, surface a busy indicator, and disable all rapid-click triggers while a fetch is in flight.

## Key insights

- The hang is `fetcher.wait()` on the GUI thread (`gui/base_browser_panel.py:113`).
- Old fetcher's `_cancelled` flag will eventually exit `run()`; we only need to ignore its remaining emissions.
- The single shared browser panel beneath the saved-channels list means **one fetch at a time** is the right semantics — overlapping fetches confuse the table state. Disabling the saved-channel table during fetch enforces that without queueing complexity.

## Architecture

```
SavedChannelsPanel  ──fetch_started──▶  disable table + buttons + context menu
                                        (re-enable on fetch_finished)
                ▲
                │ signals
                │
BaseBrowserPanel ──┬── add QProgressBar (indeterminate, hidden when idle)
                   ├── add Cancel button (hidden when idle)
                   ├── emit fetch_started / fetch_finished
                   └── replace wait() with signal disconnect on stale fetcher
```

## Related code files

**Modify:**
- `gui/base_browser_panel.py` — add progress bar + cancel button; signal lifecycle; non-blocking start.
- `gui/saved_channels_panel.py` — listen to fetch lifecycle; disable controls while busy.
- `gui/facebook_browser_panel.py` — let base handle Load-more disable through the new lifecycle (its existing `setEnabled(False)` calls stay correct).

**No changes:**
- `channel_fetcher.py`, `facebook_fetcher.py` — fetchers already cooperate via `_cancelled` flag.

## Implementation steps

1. **`gui/base_browser_panel.py`:**
   1. Add two signals: `fetch_started = Signal()`, `fetch_finished = Signal()`.
   2. Add `QProgressBar` configured for busy mode (`setRange(0, 0)`), hidden by default, placed above/next to the status label.
   3. Add `Cancel` button next to Browse, hidden by default.
   4. Add `_is_fetching: bool` state.
   5. Rewrite `_on_browse()`: short-circuit if already fetching (UI should already be disabled — guard for programmatic re-entry only). Remove `cancel() + wait()`.
   6. Rewrite `_start_fetcher()`:
      - Disconnect any prior fetcher signals defensively (no-op when None).
      - Set `_is_fetching=True`, show progress bar, show Cancel, disable URL input + Browse.
      - Connect new fetcher's signals.
      - `fetcher.start()`.
      - Emit `fetch_started`.
   7. Rewrite `_on_fetch_done()`:
      - Hide progress bar + Cancel; re-enable URL input + Browse.
      - Set `_is_fetching=False`.
      - Emit `fetch_finished`.
      - Existing logic (`status_label.setText`, `fetch_completed.emit`) stays.
   8. Add `_on_cancel_clicked()`:
      - If `self._fetcher and self._fetcher.isRunning()`: call `cancel()`, disable Cancel button, set status text "Cancelling…".
      - Do **not** call `wait()`. The fetcher's natural `finished_fetch` will trigger `_on_fetch_done`.

2. **`gui/saved_channels_panel.py`:**
   1. In `__init__`, after `self.browser_panel.fetch_completed.connect(...)`, also connect:
      - `browser_panel.fetch_started.connect(self._on_browser_fetch_started)`
      - `browser_panel.fetch_finished.connect(self._on_browser_fetch_finished)`
   2. Add `_on_browser_fetch_started()`: disable `self.table`, `self.add_btn`, `self.refresh_btn`.
   3. Add `_on_browser_fetch_finished()`: re-enable the same widgets.
   4. In `_on_context_menu()`, if `self.browser_panel._is_fetching`, return early before showing the menu (or hide fetch-related items).

3. **`gui/facebook_browser_panel.py`:**
   - `_on_load_more` already early-returns when `self._fetcher.isRunning()`. Keep.
   - Existing `load_more_btn.setEnabled` calls in `_on_fetch_done` stay correct.
   - Optional: also disable `scrolls_spin` while fetching (parallel to `url_input` in base).

## Todo list

- [ ] Add `fetch_started` / `fetch_finished` signals to `BaseBrowserPanel`
- [ ] Add `QProgressBar` (indeterminate) + Cancel button to `BaseBrowserPanel`
- [ ] Replace `cancel() + wait()` with non-blocking signal disconnect
- [ ] Disable URL input during fetch; show "Cancelling…" on cancel
- [ ] `SavedChannelsPanel`: disable table/add/refresh during fetch; suppress context menu
- [ ] Run `python -m pytest -q` — ensure no regression
- [ ] Manual smoke: launch GUI, double-click two saved channels rapidly → no hang

## Success criteria

- Rapid double-click on saved channels never freezes the GUI for >100ms.
- Progress bar visible during fetch; Cancel button works without blocking.
- Saved-channels table disabled during fetch; re-enabled on completion or cancel.
- Existing tests (`test_saved_channels_panel.py`, `test_settings_split.py`, …) still pass.

## Risk assessment

- **Risk:** Old fetcher emits a delayed `finished_fetch` after we already swapped — `_on_fetch_done` would re-enable controls prematurely.
  - **Mitigation:** Disconnect old fetcher's signals before assigning `self._fetcher = new_fetcher` — defensive, only relevant if we ever allow overlapping fetches. With the disable-during-fetch UX we should never overlap.
- **Risk:** Cancel button stuck if Playwright never finishes (network hang).
  - **Mitigation:** Existing `goto(timeout=30_000)` + `PlaywrightTimeout` handler ensures `finished_fetch` always fires within 30s. Acceptable.
- **Risk:** Test that calls `panel._show_channel(ch)` directly bypasses fetch lifecycle.
  - **Mitigation:** Tests exercise the cached path (no fetch). The non-cached path test wasn't previously exercised — we'll add a unit test for the disable behavior using a mock fetcher.

## Security considerations
None — UI-only change.

## Next steps
Phase 2 — tests covering the lifecycle.
