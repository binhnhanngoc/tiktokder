# Phase 04 — `gui/main_window.py` worker + startup hook + manual menu

**Priority:** P2 · **Status:** todo · **Effort:** ~1.5h

## Context Links
- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md) — section "Flow Diagram", "Menu Wiring"
- Existing precedent: `_HealthWorker` / `_HealthWorkerSignals` at `gui/main_window.py:66-86` — worker pattern using `QRunnable` + `QThreadPool`. **Reuse this pattern** instead of `QThread`. (Brainstorm said `QThread`; the precedent in this codebase is `QRunnable`. Switch to `QRunnable` for consistency.)
- Existing `_setup_menu` at `gui/main_window.py:526-571`
- Existing `closeEvent` at `gui/main_window.py:653-680` — already calls `QThreadPool.globalInstance().waitForDone(2000)` so update worker drains for free.

## Overview
Wire the update-check feature into `MainWindow`:
1. Add `_UpdateWorker` (`QRunnable`) + signals
2. Cache last `ReleaseInfo` on `self._latest_release_cache` for the About-tab pill (phase-05)
3. Schedule background check via `QTimer.singleShot(2000, ...)` after window shows
4. Add `Help → Check for Updates…` menu action
5. Manual flow: ignores cache and skip gates; surfaces all outcomes via `QMessageBox`
6. Background flow: silent on every failure; only opens `UpdateAvailableDialog` when newer + not skipped

## Key Insights
- `closeEvent` already drains `QThreadPool.globalInstance()` for the health worker — reusing `QRunnable` means we get teardown safety **for free**.
- `last_update_check_at` is written **always** (success or fail). This prevents thrashing the API on a flaky network: one failure = 24h cooldown.
- Caller writes config; dialog only emits `skip_requested`. Keeps the dialog UI-pure (phase-03 contract).
- Manual path bypasses all three gates (`update_check_enabled`, `should_check_now`, `skipped_update_version`) — user explicitly asked.
- `Signal(object)` pattern from `_HealthWorker` works for `ReleaseInfo | None` payload — same Qt mechanic.
- Distinguish background vs manual via a worker constructor flag, so the same worker class handles both. `done` signal carries `(ReleaseInfo | None, is_manual: bool)`.

## Requirements

**Functional:**

*Worker:*
- `_UpdateWorker(QRunnable)` with `_UpdateWorkerSignals` exposing `done = Signal(object, bool)`.
- `run()`: calls `update_checker.latest_release()`, emits `done.emit(result, self._is_manual)`. Never raises (matches `_HealthWorker` defensiveness).

*Background path (startup):*
- `QTimer.singleShot(2000, self._maybe_check_updates_background)` from `__init__` *after* `show()` happens. Safer to schedule from a method called by `app.py` after `window.show()`, OR right at end of `__init__` (window is shown almost immediately after — 2000ms gives Qt's event loop time to settle).
- `_maybe_check_updates_background()`: returns immediately if `not config.update_check_enabled` OR `not should_check_now(config.last_update_check_at)`. Otherwise spawns `_UpdateWorker(is_manual=False)`.

*Manual path (menu):*
- `_on_check_updates_manual()`: spawns `_UpdateWorker(is_manual=True)` regardless of any gate.
- Show a brief status-bar message (`update_status("Checking for updates…")`) so user sees activity.

*Result handler:*
- `_on_update_check_done(result, is_manual)`:
  - **Always** write `config.last_update_check_at = time.time()`; `save_config(config)`.
  - Cache `self._latest_release_cache = result` so phase-05 pill can read it.
  - If `result is None` (network failure):
    - Background → silent.
    - Manual → `QMessageBox.warning(self, "Update Check Failed", "Could not reach GitHub. Check your internet connection and try again.")`
  - If `result` is not None and `is_newer(result.version, __version_info__)`:
    - Background path: skip if `result.version_str == config.skipped_update_version`.
    - Otherwise: instantiate `UpdateAvailableDialog`, wire `skip_requested → _on_skip_version`, exec it. After exec returns: read `dialog.opt_out_chosen()` → if True, set `config.update_check_enabled = False` and `save_config(config)`.
  - If `result` is not None but **not** newer (or equal):
    - Background → silent.
    - Manual → `QMessageBox.information(self, "Up to Date", f"You're running the latest version (v{__version__}).")`
  - **Emit `update_check_finished` signal** so phase-05 pill can refresh.

*Menu wiring:*
- Insert `Help → Check for &Updates…` action. Place it just before the existing `addSeparator()` at line 566 (so it sits with the manual/troubleshooting cluster, separated from About).

**Non-functional:**
- All edits inside `gui/main_window.py`. No new files.
- Stay under file's existing concerns; group new methods together with section comment `# ── update checker ──`.
- Cache field `_latest_release_cache: ReleaseInfo | None = None` initialized in `__init__`.
- New signal `update_check_finished = Signal()` declared at class level (Qt signals must be class attributes).

## Architecture

```
gui/main_window.py additions
├── module-level
│   ├── from update_checker import (
│   │       ReleaseInfo, latest_release, is_newer, should_check_now,
│   │   )
│   ├── from gui.update_dialog import UpdateAvailableDialog
│   ├── import time
│   └── from PySide6.QtWidgets import QMessageBox  (if not already)
├── class _UpdateWorkerSignals(QObject)
│   └── done = Signal(object, bool)
├── class _UpdateWorker(QRunnable)
│   ├── __init__(is_manual: bool)
│   └── run() → emits done(result, is_manual)
└── class MainWindow
    ├── update_check_finished = Signal()                 # for pill refresh
    ├── __init__: self._latest_release_cache = None
    ├── __init__ end: QTimer.singleShot(2000, self._maybe_check_updates_background)
    ├── _setup_menu: insert "Check for Updates…" before "About"
    ├── _maybe_check_updates_background()    # gate-checked
    ├── _on_check_updates_manual()           # bypass gates
    ├── _spawn_update_worker(is_manual)      # DRY helper
    ├── _on_update_check_done(result, is_manual)
    └── _on_skip_version(version_str)        # writes config
```

## Related Code Files

**Modify:**
- `gui/main_window.py` — additions only; existing methods untouched

**Read (no edits):**
- `update_checker.py` (phase-01) — public API
- `gui/update_dialog.py` (phase-03) — dialog signature + signals
- `config.py` (phase-02) — three new fields

## Implementation Steps

1. Add module imports near the top of `gui/main_window.py`:
   - `import time`
   - `from PySide6.QtWidgets import QMessageBox` (verify it isn't already imported)
   - `from update_checker import latest_release, is_newer, should_check_now, ReleaseInfo`
   - `from gui.update_dialog import UpdateAvailableDialog`
   - Update `from config import (...)` to include `save_config` if not already there (it is — line 30).
2. Define `_UpdateWorkerSignals(QObject)` with `done = Signal(object, bool)`. Put it directly below `_HealthWorkerSignals` (~line 86) to mirror precedent.
3. Define `_UpdateWorker(QRunnable)`:
   ```python
   class _UpdateWorker(QRunnable):
       def __init__(self, is_manual: bool) -> None:
           super().__init__()
           self._is_manual = is_manual
           self.signals = _UpdateWorkerSignals()
       def run(self) -> None:
           try:
               result = latest_release()
           except Exception:
               result = None
           self.signals.done.emit(result, self._is_manual)
   ```
4. Add `update_check_finished = Signal()` to `MainWindow` class body (near top of class definition).
5. In `MainWindow.__init__`, after `self._help_dialog = None` (line 115), add:
   ```python
   self._latest_release_cache: ReleaseInfo | None = None
   ```
6. At the end of `MainWindow.__init__` (after `QTimer.singleShot(0, self._refresh_health)`), add:
   ```python
   QTimer.singleShot(2000, self._maybe_check_updates_background)
   ```
7. Modify `_setup_menu`: insert the new action right before `help_menu.addSeparator()` at line 566:
   ```python
   help_menu.addAction(
       icon("mdi6.update"),
       "Check for &Updates…",
       self._on_check_updates_manual,
   )
   ```
8. Add new methods (group under a `# ── update checker ──` section comment, near the `_open_help` method around line 618):
   - `_maybe_check_updates_background()` — gate check + spawn (`is_manual=False`)
   - `_on_check_updates_manual()` — status update + spawn (`is_manual=True`)
   - `_spawn_update_worker(is_manual)` — `worker = _UpdateWorker(is_manual); worker.signals.done.connect(self._on_update_check_done); QThreadPool.globalInstance().start(worker)`
   - `@Slot(object, bool) _on_update_check_done(result, is_manual)` — implement the result-handler logic from Requirements above
   - `@Slot(str) _on_skip_version(version_str)` — `self.config.skipped_update_version = version_str; save_config(self.config)`
9. Compile-check: `python -c "from gui.main_window import MainWindow"`.
10. Manual smoke-test:
    - Set `__version__` to `"0.0.1"` temporarily in `version.py` (or pass a debug flag) to force "newer" path. Run `python app.py`. Within ~3s the dialog should pop up.
    - Test menu: `Help → Check for Updates…` while `__version__` is current → "Up to Date" info dialog.
    - Test offline: disable network, manual check → warning dialog.
    - **Restore `__version__`** before commit.
11. Add tests covering:
    - Background path with `update_check_enabled=False` does **not** spawn a worker (use `QThreadPool` mock or just unit-test `_maybe_check_updates_background` with a patched `should_check_now`).
    - `_on_update_check_done(None, is_manual=False)` is silent (no `QMessageBox` called); writes `last_update_check_at` (mock `time.time`).
    - `_on_update_check_done(release, is_manual=False)` with `release.version_str == config.skipped_update_version` does **not** show dialog.
    - `_on_skip_version("1.10.1")` updates config field.
12. `python -m pytest test_main_window.py -v` (create file if absent — `test_main_window_update_checker.py` is fine; mirror existing `test_*` naming around `gui/main_window.py`).

## Todo List

- [ ] Imports + `_UpdateWorkerSignals` + `_UpdateWorker`
- [ ] `update_check_finished` signal + `_latest_release_cache` field
- [ ] Startup hook (`QTimer.singleShot(2000, ...)`)
- [ ] Menu action
- [ ] `_maybe_check_updates_background`
- [ ] `_on_check_updates_manual`
- [ ] `_spawn_update_worker`
- [ ] `_on_update_check_done` (full branching: net error + newer + up-to-date × manual/background)
- [ ] `_on_skip_version`
- [ ] Compile-check
- [ ] Manual smoke (3 paths: newer / up-to-date / offline)
- [ ] Unit tests (≥4)
- [ ] All tests green

## Success Criteria

- Startup never blocks UI thread (network always off main thread).
- Background check fires exactly once per launch when gates allow.
- Manual menu always shows an outcome (newer dialog / "up to date" info / "failed" warning).
- Skip-version persists; opt-out persists; manual still works after opt-out.
- `_latest_release_cache` populated post-check (phase-05 prerequisite).
- `update_check_finished` signal emits exactly once per check completion.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Worker emits after `MainWindow` teardown | `closeEvent` already calls `QThreadPool.globalInstance().waitForDone(2000)` — covered |
| `save_config` on Skip blocks UI for slow disks | Single ~1KB JSON write; safe on main thread |
| `QMessageBox.warning` interrupts user mid-task in manual mode | Acceptable — user clicked "Check for Updates"; expects a verdict |
| Race: user clicks menu twice fast → two workers in flight | Latest result wins by signal arrival order; both write the same `last_update_check_at` (~equal `time.time()`); idempotent. Optional: disable menu action while pending — not needed for MVP |
| `__version_info__` is a 3-tuple of `int` from `version.py` — `is_newer` expects same shape | Phase-01 spec aligns; tested via integration in phase-04 tests |

## Security Considerations

- API call is HTTPS to `api.github.com`. No certs pinned (stdlib uses system trust store, fine).
- `release.html_url` opened via `QDesktopServices` — same risk surface as a manual visit; acceptable.
- `save_config` writes to user's data dir only. No privilege escalation.

## Next Steps
Phase 05 reads `_latest_release_cache` and connects to `update_check_finished` signal for live pill refresh.
