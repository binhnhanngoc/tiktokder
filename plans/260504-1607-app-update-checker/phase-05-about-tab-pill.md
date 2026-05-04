# Phase 05 — About-tab pill + "Check now" button

**Priority:** P3 · **Status:** todo · **Effort:** ~1h

## Context Links
- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md) — section "About Tab Badge"
- Files: `gui/help_content.py:225-239` (current `_about_html`), `gui/help_dialog.py` (renders tabs)
- Phase-04 prerequisites: `MainWindow._latest_release_cache`, `update_check_finished` signal, `_on_check_updates_manual`

## Overview
Replace the static About tab with a dynamic widget showing:
- Current version (existing)
- A status pill: **● Up to date** (green) / **▲ vX.Y.Z available** (amber, clickable) / **○ Last checked: …** (grey)
- A **Check now** button — calls the same manual path as the menu

Pill state is derived from `(MainWindow._latest_release_cache, version_info, last_update_check_at)`.

## Key Insights
- Current About tab is **static HTML** rendered by `QTextBrowser` (see `help_dialog.py` build loop). To get an interactive pill + button we need to **swap the About tab from a `QTextBrowser` to a custom `QWidget`** when the dialog is built.
- Cleanest approach: extend `help_tabs()` to return either `(tab_id, label, html_str)` *or* `(tab_id, label, widget_factory_callable)`. The dialog discriminates by `callable(content)` → call factory(parent) → use the widget; else `QTextBrowser` path. Keeps existing tabs untouched.
- The widget factory needs access to `MainWindow` for: cached `ReleaseInfo`, `update_check_finished` signal, `_on_check_updates_manual` slot, `last_update_check_at`. Easiest: pass `main_window` reference into `HelpDialog` constructor and propagate to factory.
- Pill is just a styled `QLabel` (Qt rich text + stylesheet). Three pre-defined stylesheets keyed by state. No new icons needed beyond text glyphs (●▲○).

## Requirements

**Functional:**

*State derivation:*
- `unknown` (grey): `_latest_release_cache is None` AND `last_update_check_at == 0.0` (never checked).
- `stale` (grey): `_latest_release_cache is None` AND `last_update_check_at > 0` (checked but failed last time). Show "Last checked: 2 days ago" (or human-readable delta).
- `up_to_date` (green): `_latest_release_cache` exists AND not `is_newer(...)`. Show "Up to date".
- `available` (amber): `_latest_release_cache` exists AND `is_newer(...)`. Show "vX.Y.Z available". **Clickable** — opens `UpdateAvailableDialog` for the cached release.

*Widget composition:*
- About tab body becomes a `QWidget` with vertical layout:
  1. Title `QLabel`: `"TikTokDer v{__version__}"` — large/bold (matches existing visual weight)
  2. Pill `QLabel` with stylesheet, plus a "Check now" `QPushButton` next to it (horizontal sub-layout)
  3. Original "Powered by" + license HTML retained — render in a child `QTextBrowser` below

*Interactivity:*
- "Check now" button → calls `main_window._on_check_updates_manual()` (reuse path).
- Pill click (only in `available` state) → instantiate `UpdateAvailableDialog` from cached release. Caller (the About widget) writes config on Skip / opt-out — same logic as `MainWindow._on_update_check_done`. **DRY:** factor that "show dialog + handle skip + handle opt-out" block out of phase-04 into a `MainWindow._show_update_dialog(release)` helper, then phase-05 calls the same helper. Update phase-04 plan retroactively in implementation.
- `update_check_finished` signal → re-render the pill in-place. Connection lifetime: only while About tab widget is alive; disconnect on widget destruction (`destroyed` signal) to avoid dangling slot if dialog gets recreated.

*Live refresh:*
- After manual check from About, `update_check_finished` fires → pill re-derives → text + colour update without re-instantiating widget.

**Non-functional:**
- New file `gui/about_panel.py` for the widget — keeps `help_dialog.py` and `help_content.py` lean. Target ~80 LOC.
- `help_content.py` change: `_about_html()` becomes the "Powered by + license" HTML only; new helper `about_panel_factory(main_window)` returns the full widget. Or simpler: keep `_about_html()` and have `AboutPanel` widget include a `QTextBrowser` rendering `_about_html()` underneath the pill. Pick the simpler structure.
- `help_dialog.py` change: tab-content type is now `str | Callable[[QWidget], QWidget]`; branching one-liner.

## Architecture

```
gui/about_panel.py (NEW)
└── class AboutPanel(QWidget):
    ├── __init__(main_window, parent)
    ├── _build_ui()
    ├── _refresh_pill()                  # state derivation + label/style
    ├── _on_check_now_clicked()          # → main_window._on_check_updates_manual()
    ├── _on_pill_clicked()               # only when available; → main_window._show_update_dialog()
    └── _human_delta(epoch) -> str       # "2 days ago", "just now", "—"

gui/help_content.py (EDIT)
├── _about_html()  → keep, but trim to "Powered by + license" body only
└── help_tabs()    → About entry returns a factory: lambda mw: AboutPanel(mw)
                     others stay as HTML strings

gui/help_dialog.py (EDIT)
├── HelpDialog.__init__(parent, main_window=None)
└── tab loop discriminates: if callable(content) → content(self) widget; else QTextBrowser as today

gui/main_window.py (EDIT)
├── _open_help: HelpDialog(self, main_window=self)
└── _show_update_dialog(release) — extracted from phase-04 result handler
```

## Related Code Files

**Create:**
- `gui/about_panel.py`

**Modify:**
- `gui/help_content.py` — split About into pill + powered-by HTML
- `gui/help_dialog.py` — accept `main_window` arg + branch on callable content
- `gui/main_window.py` — pass `main_window=self` to `HelpDialog`; extract `_show_update_dialog` helper
- `test_help_dialog.py` — update if it instantiates `HelpDialog()` with no kwargs (use sentinel `main_window=None`-tolerant path: `AboutPanel` should accept `None` and disable click/refresh paths gracefully)

**Read:**
- Phase-04 deliverable: `MainWindow._latest_release_cache`, `update_check_finished` signal

## Implementation Steps

1. **Refactor phase-04:** in `gui/main_window.py`, extract a `_show_update_dialog(release: ReleaseInfo)` method from `_on_update_check_done`. The result-handler calls it instead of inlining. This becomes the shared entry point used by both phase-04 (auto/manual flow) and phase-05 (pill click).
2. **Create `gui/about_panel.py`:**
   - Imports: `time`, `QWidget`, `QLabel`, `QPushButton`, `QTextBrowser`, `QHBoxLayout`, `QVBoxLayout`, `Slot`, `from version import __version__, __version_info__`, `from update_checker import is_newer`.
   - Class `AboutPanel(QWidget)`:
     - Constructor stores `main_window` ref (typed `Optional["MainWindow"]` via `TYPE_CHECKING` to avoid import cycle).
     - `_build_ui()`: title `QLabel` (bold, ~14pt), horizontal row with pill `QLabel` + "Check now" `QPushButton`, then `QTextBrowser` rendering `_powered_by_html()` (small height, no scroll if possible).
     - Connect "Check now" `clicked` → `_on_check_now_clicked`.
     - If `main_window`: connect `main_window.update_check_finished` → `_refresh_pill`. Disconnect on `self.destroyed`.
     - Make pill clickable by setting `QLabel.linkActivated` (use `<a>` markup) **only** when state is `available`.
   - `_refresh_pill()`:
     - Read `main_window._latest_release_cache` and `main_window.config.last_update_check_at` (None-guard if `main_window is None` → state = `unknown`).
     - Derive state per Requirements.
     - Set label text + stylesheet:
       - green: `background: #1f7a1f; color: white; padding: 2px 8px; border-radius: 8px;`
       - amber: `background: #c47b00; color: white; padding: 2px 8px; border-radius: 8px;` + `<a href="open">` wrapper
       - grey: `background: #666; color: white; padding: 2px 8px; border-radius: 8px;`
     - Set glyph: `●` (up-to-date), `▲` (available), `○` (unknown/stale).
   - `_human_delta(epoch)`: `now - epoch` → "just now" (<60s), "X minutes ago" (<3600s), "X hours ago" (<86400s), "X days ago" (else). Returns `"—"` for `epoch == 0`.
   - `_on_check_now_clicked`: call `main_window._on_check_updates_manual()` if `main_window`.
   - `_on_pill_clicked`: only fired when wired with `<a href="open">` link; call `main_window._show_update_dialog(main_window._latest_release_cache)`.
3. **Edit `gui/help_content.py`:**
   - Rename `_about_html` to `_powered_by_html` (or keep name — content is unchanged minus the H2 title which moves into the widget).
   - Change `help_tabs()`: replace About entry's HTML string with the factory `lambda mw: AboutPanel(mw)`. Need `from gui.about_panel import AboutPanel`. Risk of import cycle: `help_content` is imported by `main_window.py` (line 36). `about_panel` imports from `version` + `update_checker` only — clean. **Verify no cycle.**
   - The `help_tabs()` return type changes; document it: `tuple[tuple[str, str, str | Callable[[QWidget], QWidget]], ...]`.
4. **Edit `gui/help_dialog.py`:**
   - Constructor signature: `__init__(self, parent=None, main_window=None)`.
   - Tab build loop: if `callable(html)` → `widget = html(main_window)`; else current `QTextBrowser` path. Add the widget the same way (`self.tabs.addTab(widget, label)`).
5. **Edit `gui/main_window.py`:**
   - Update `_open_help`:
     ```python
     if self._help_dialog is None:
         self._help_dialog = HelpDialog(self, main_window=self)
     ```
   - Extract `_show_update_dialog` helper (per step 1).
6. **Update `test_help_dialog.py`** — instantiate with `main_window=None`; assert About tab now contains an `AboutPanel` (not a `QTextBrowser`). Existing tab-count + content tests pass with adjustment for the About entry.
7. **Add `test_about_panel.py`** covering:
   - Pill state = `unknown` when `main_window=None`.
   - Pill state = `available` when `_latest_release_cache.version > __version_info__`.
   - Pill state = `up_to_date` when equal.
   - "Check now" click invokes `main_window._on_check_updates_manual` (use a `MagicMock()` standing in for `main_window` with the required attributes).
8. Compile-check + smoke run: open Help → About, see pill. Click Check now, verify pill text updates after the worker finishes.

## Todo List

- [ ] Extract `MainWindow._show_update_dialog` from phase-04 result handler
- [ ] Create `gui/about_panel.py` with `AboutPanel` widget
- [ ] Implement state derivation + 4 visual states
- [ ] Wire "Check now" → `_on_check_updates_manual`
- [ ] Wire pill click → `_show_update_dialog` (when `available`)
- [ ] Connect `update_check_finished` → `_refresh_pill` (disconnect on destroy)
- [ ] Update `help_content.py` — About entry as factory
- [ ] Update `help_dialog.py` — accept `main_window`, branch on callable
- [ ] Update `main_window._open_help` to pass `self`
- [ ] Update `test_help_dialog.py`
- [ ] Add `test_about_panel.py` (≥4 tests)
- [ ] Smoke-test live: open / check / re-open
- [ ] All tests green; new file < 200 LOC

## Success Criteria

- About tab shows correct pill state on first open after fresh launch (`unknown` if no cache).
- After background check fires (or manual click), pill updates without re-opening Help dialog.
- Click amber pill → `UpdateAvailableDialog` opens with cached release.
- `Check now` button works regardless of opt-out state.
- All tests green; `gui/about_panel.py` < 200 LOC.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Import cycle: `help_content` → `about_panel` → ? | `about_panel` imports only `version`, `update_checker`, Qt. No cycle |
| `help_dialog` test breaks because About tab is no longer `QTextBrowser` | Update test to assert tab widget type per id |
| Help dialog opened before `MainWindow` finished init | Lazy creation in `_open_help` happens post-init; safe |
| Stylesheet looks bad in light vs dark theme | Use neutral palette colours that read on both; or honour `theme.py` palette — out of scope, accept first-cut |
| Disconnect on `destroyed` racy across Qt versions | If problematic, use `weakref` for `main_window` ref and guard slot with `try/except RuntimeError` |
| Extracting `_show_update_dialog` mid-implementation drifts phase-04 plan | Acknowledged: do this refactor under phase-05 commit; phase-04 result handler stays unchanged in shape, just delegates |

## Security Considerations
None new — pill is presentational; click path reuses phase-04's already-vetted dialog flow.

## Next Steps
Phase 06 — docs + version bump. Final phase before merge.
