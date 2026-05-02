# Phase 2 — Status-bar health pill

**Status:** ✅ complete (2026-05-02) · **Priority:** P1 · **Effort:** S (~1h) · **Risk:** Low

## Context

- Files: `gui/status_bar_widget.py` (~40 LOC added), `gui/main_window.py` (timer + wiring).
- Depends on Phase 1 (`health_check.compute_health`).

## Goal

Add a colored circular dot to `StatusBarWidget`, leftmost. Color reflects `HealthReport.max_severity()` — gray (no data yet) → green (`None`) → amber (`info`/`warn`) → red (`error`). Click opens a `QMenu` (or simple popover) listing the current issues; selecting one routes to the same fix-action handler that Phase 3's Settings buttons invoke.

## Key Insights

- `StatusBarWidget` is dumb (just `set_counts`). Health is a different state-shape, so add `set_health_report(report)` rather than overloading `set_counts`.
- The pill is purely visual — all interaction lives in the popover. Keeps the status bar clean.
- A `QMenu` is enough for the popover; no need for a custom widget.

## Requirements

- Pill renders as a 10×10 px filled circle (QSS-styled `QLabel` with `border-radius: 5px`).
- Color updates synchronously when `set_health_report` is called.
- Click anywhere on the pill opens the popover.
- Popover lists issues sorted by severity (error → warn → info), with title + truncated detail.
- Selecting a popover row emits `health_action_requested(issue)` for `MainWindow` to handle.

## Architecture

```
StatusBarWidget
├── + self.health_pill: QLabel(10x10, styled)
├── + self.health_pill.mousePressEvent → opens self._health_menu
├── + self._issues: list[HealthIssue] = []
├── + Signal: health_action_requested(object)  # HealthIssue
└── + set_health_report(report: HealthReport) -> None

MainWindow
├── + self._health_timer = QTimer(self) ; interval = 30 * 60_000
├── + self._health_timer.timeout.connect(self._refresh_health)
├── + _refresh_health() — runs compute_health in QThreadPool, slot back to UI
├── + on_channel_fetched signal → _refresh_health (lightweight cache hit)
└── + status_bar.health_action_requested.connect(self._handle_health_action)
```

## Related Code Files

**Modify:**
- `gui/status_bar_widget.py` — add pill, popover, signal, setter.
- `gui/main_window.py` — timer, threaded refresh, action routing.

**Read for context:**
- Phase 1 `health_check.py` (HealthIssue/HealthReport shape).
- `gui/main_window.py` (existing `status_bar` reference + theme/QSS conventions).
- `gui/tokens.py` (palette colors so the pill respects light/dark themes).

## Implementation Steps

1. Add three palette tokens to `gui/tokens.py` (or use existing): `health_ok`, `health_warn`, `health_error`. Default: `#2ecc71` / `#f5a623` / `#e74c3c`.
2. In `StatusBarWidget.__init__`, prepend a `QLabel` with fixed size (12, 12), object name `healthPill`. QSS via app stylesheet:
   ```css
   QLabel#healthPill { border-radius: 6px; background: gray; }
   QLabel#healthPill[severity="ok"]    { background: <token>; }
   QLabel#healthPill[severity="info"]  { background: <token>; }
   QLabel#healthPill[severity="warn"]  { background: <token>; }
   QLabel#healthPill[severity="error"] { background: <token>; }
   ```
3. Override `mousePressEvent` on the pill to call `self._show_popover()`.
4. `_show_popover()` builds a `QMenu`: one `QAction` per issue (icon = severity dot, text = `f"{title} — {detail[:60]}"`). Action `triggered` emits `health_action_requested(issue)`.
5. `set_health_report(report)`: store issues, set pill `severity` property, `style().polish(pill)` to re-apply QSS.
6. In `MainWindow`, create `self._health_timer = QTimer(self)`, interval 1_800_000 (30 min), connect `timeout` to `self._refresh_health()`. Start it in `__init__`.
7. `_refresh_health()` runs `health_check.compute_health(...)` via `QThreadPool` (use `QRunnable` + a small `QObject` for the result signal). On result: `self.status_bar.set_health_report(report)`.
8. Wire `download_engine.history_changed` (or a new `channel_fetched` signal if more appropriate) to `_refresh_health`.
9. Wire `status_bar.health_action_requested` → stub `_handle_health_action(issue)` (Phase 3 fills the dispatcher).

## Todo List

- [x] Reuse existing `state.success/warning/error` palette tokens (no new tokens needed).
- [x] Add pill QLabel (`_ClickableLabel`) + inline theme-aware stylesheet.
- [x] Implement `set_health_report` + tooltip refresh.
- [x] Implement popover (QMenu) + `health_action_requested` signal (cap 20 + overflow row).
- [x] Implement `_refresh_health` in MainWindow with QThreadPool worker (`_HealthWorker`).
- [x] Wire 30-min QTimer + `engine.history_changed` post-fetch trigger.
- [x] Manual smoke: pill turns amber on synthetic stale channel; close+reopen safe.
- [x] Add `MainWindow.closeEvent` to drain workers + stop timer (added during code review).

## Success Criteria

- Pill is visible in status bar, defaults to gray on launch (pre-first-compute), goes green within ~1s.
- Forcing an issue (e.g. `touch -d "100 days ago" data/cookies.txt`) flips the pill to amber/red on next compute.
- Clicking pill opens popover with the right number of items.
- 30-min timer + post-fetch refresh both trigger recomputes (verifiable via debug log).

## Risks

| Risk | Mitigation |
|---|---|
| QSS property selectors don't repaint without `unpolish/polish` | Always call `style().unpolish(pill); style().polish(pill)` after `setProperty`. |
| Threaded compute races with UI close | `QThreadPool.globalInstance().waitForDone(2000)` in `MainWindow.closeEvent`. |
| Popover blocks if list is huge | Cap to 20 items in menu; "View all in Settings" action at bottom. |

## Security Considerations

None — pure UI bind to data layer.

## Next Steps

→ Phase 3 builds the Settings panel section + the real action dispatcher.
