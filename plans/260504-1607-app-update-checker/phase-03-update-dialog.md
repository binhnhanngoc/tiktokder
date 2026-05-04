# Phase 03 — `gui/update_dialog.py` UpdateAvailableDialog

**Priority:** P2 · **Status:** todo · **Effort:** ~1h

## Context Links
- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md) — section "UpdateAvailableDialog"
- Sibling pattern: `gui/help_dialog.py` — same `QDialog` + `QTextBrowser` + manual link routing approach. Reuse its anchor-click pattern.

## Overview
Modal `QDialog` shown when a newer release exists. Renders release notes via `QTextBrowser.setMarkdown` (PySide6 ≥ 6.4 native — already required). Three buttons + opt-out checkbox. Pure UI: emits signals, never touches config or network directly.

## Key Insights
- The dialog never decides what's newer or whether to skip — it only renders state and emits user choices. Caller (`MainWindow`) writes config based on result.
- Release notes from the API may include external links; route them via `QDesktopServices.openUrl` like `help_dialog.py` does (`setOpenLinks(False)` + `anchorClicked` slot).
- Tag-fallback mode (`is_tag_fallback=True`) means release notes are empty — show a placeholder line: *"No release notes available — see GitHub for details."*
- Modal blocking is fine: dialog is only shown post-startup (delayed 2000ms) and post-manual-click; no race with engine signals.

## Requirements

**Functional:**
- Constructor: `UpdateAvailableDialog(release: ReleaseInfo, current_version_str: str, opt_out_currently: bool, parent=None)`.
- Header line: `"Version {release.version_str} is available (you have {current_version_str})"`.
- Body: `QTextBrowser` with `setMarkdown(release.body)` (or placeholder when `is_tag_fallback`).
- Checkbox: *"Don't check for updates automatically"* — initial state mirrors `not opt_out_currently` semantics. **Read brainstorm carefully:** "Checkbox toggles `update_check_enabled` on close." So if checkbox is *checked*, `update_check_enabled` becomes `False`. Checkbox unchecked = checks remain enabled. Initial state = `not opt_out_currently` (i.e., checked when checks are disabled).
- Three buttons (in a `QDialogButtonBox` or `QHBoxLayout`):
  - **Open Release Page** — `QDesktopServices.openUrl(QUrl(release.html_url))`, then `accept()`.
  - **Skip This Version** — emit `skip_requested = Signal(str)` carrying `release.version_str`, then `accept()`.
  - **Remind Me Later** — `accept()` with no side-effect.
- On any close path (including the `X` button via `closeEvent`), expose `opt_out_chosen() -> bool` returning the checkbox's *final* state, so caller can decide whether to flip `update_check_enabled`.
- External `http(s)` links inside release notes open in system browser (not in-dialog).

**Non-functional:**
- File < 200 LOC (target ~90).
- No imports from `update_checker` other than `ReleaseInfo` (type-only).
- No imports from `config` — keep dialog UI-pure.
- Tests: instantiate offscreen (`QT_QPA_PLATFORM=offscreen`), assert title, checkbox initial state, button labels, signal emission on Skip, opt-out state read-back.

## Architecture

```
gui/update_dialog.py
├── from update_checker import ReleaseInfo
├── class UpdateAvailableDialog(QDialog):
│   ├── skip_requested = Signal(str)               # version_str
│   ├── __init__(release, current_version_str, opt_out_currently, parent)
│   ├── _build_ui(release, current_version_str)    # header + body + checkbox + buttons
│   ├── _on_open_release(release_url)              # slot
│   ├── _on_skip(version_str)                      # slot — emits skip_requested
│   ├── _on_anchor_clicked(QUrl)                   # external-link routing
│   └── opt_out_chosen() -> bool                   # checkbox.isChecked() at close
```

Header layout: vertical `QVBoxLayout`. Header label (rich text), `QTextBrowser` (stretch=1), `QCheckBox`, button row.

## Related Code Files

**Create:**
- `gui/update_dialog.py`
- `test_update_dialog.py`

**Read (no edits):**
- `gui/help_dialog.py` — anchor-click pattern, `QDialog`/`QTextBrowser` plumbing
- `update_checker.py` — `ReleaseInfo` type

## Implementation Steps

1. Create `gui/update_dialog.py` with module docstring + imports (`QDialog`, `QDialogButtonBox`, `QTextBrowser`, `QCheckBox`, `QLabel`, `QVBoxLayout`, `QHBoxLayout`, `QPushButton`, `QUrl`, `QDesktopServices`, `Signal`, `Slot`, `from update_checker import ReleaseInfo`).
2. Define `UpdateAvailableDialog(QDialog)` with `skip_requested = Signal(str)`.
3. In `__init__`: store `release.html_url` and `release.version_str` on self; call `_build_ui`.
4. `_build_ui`:
   - `QLabel` header: rich text with bold version numbers.
   - `QTextBrowser`: `setOpenLinks(False)`; if `release.is_tag_fallback` → `setPlainText("No release notes available — see GitHub for details.")` else `setMarkdown(release.body or "")`. Connect `anchorClicked` → `_on_anchor_clicked`.
   - `QCheckBox`: store as `self._optout_checkbox`; initial `setChecked(opt_out_currently is False is False)` — wait, brainstorm says default is opt-in (checks enabled, checkbox unchecked). So `setChecked(False)` initially when `update_check_enabled=True`. Pass `opt_out_currently=not config.update_check_enabled` from caller, then dialog does `setChecked(opt_out_currently)`. **Document this contract clearly in the constructor docstring.**
   - Three `QPushButton` instances in a horizontal layout: `Open Release Page` (default), `Skip This Version`, `Remind Me Later`.
5. Wire button slots:
   - Open → `QDesktopServices.openUrl(QUrl(self._release_url))` → `self.accept()`
   - Skip → `self.skip_requested.emit(self._version_str)` → `self.accept()`
   - Remind → `self.accept()`
6. `opt_out_chosen(self) -> bool`: `return self._optout_checkbox.isChecked()`.
7. `_on_anchor_clicked(url)`: copy `help_dialog._on_anchor_clicked` verbatim — `if url.scheme() in ("http", "https"): QDesktopServices.openUrl(url)`.
8. Compile-check: `python -c "from gui.update_dialog import UpdateAvailableDialog"`.
9. Write `test_update_dialog.py`:
   - Use `pytestqt` if already in deps (check `requirements.txt`); else use the same pattern as `test_help_dialog.py` (`QApplication.instance() or QApplication([])`).
   - Test 1: Instantiate with sample `ReleaseInfo(version=(1,10,1), version_str="1.10.1", html_url="https://...", body="# Notes\n- thing", is_tag_fallback=False)`. Assert `windowTitle`, header label contains version.
   - Test 2: Tag-fallback path — assert placeholder text in body.
   - Test 3: `skip_requested` signal fires with correct version on Skip button click. Use `pytestqt`'s `qtbot.waitSignal` or a manual `QSignalSpy`.
   - Test 4: `opt_out_chosen()` reflects checkbox toggles.
10. Run `python -m pytest test_update_dialog.py -v`.

## Todo List

- [ ] Create `gui/update_dialog.py` skeleton with imports
- [ ] Implement `UpdateAvailableDialog.__init__` + `_build_ui`
- [ ] Wire three button slots
- [ ] Wire external-link routing
- [ ] Implement `opt_out_chosen()`
- [ ] Compile-check
- [ ] Write 4 tests in `test_update_dialog.py`
- [ ] All tests green; file < 200 LOC

## Success Criteria

- Dialog renders correctly when run manually: `python -c "from PySide6.QtWidgets import QApplication; from update_checker import ReleaseInfo; from gui.update_dialog import UpdateAvailableDialog; app = QApplication([]); d = UpdateAvailableDialog(ReleaseInfo((1,10,1),'1.10.1','https://example.com','# Test\n- a\n- b',False), '1.9.0', False); d.exec()"`
- All tests in `test_update_dialog.py` green
- File < 200 LOC

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| `setMarkdown` differs across PySide versions | Project pins ≥ 6.6.0 per README; behaviour stable since 6.4 |
| Test runs without QApplication on CI | Same `QT_QPA_PLATFORM=offscreen` env that `test_help_dialog.py` uses |
| Markdown body containing inline HTML escapes oddly | Acceptable — release notes authored by us; not a security boundary because `setMarkdown` strips scripts |

## Security Considerations

- `setMarkdown` (not `setHtml`) — no script execution from release-notes content.
- External links routed through `QDesktopServices` — opens system browser, no in-dialog WebView.
- `release.html_url` is constructed by caller from API response or `tag_name`; trust the API origin (`api.github.com` over HTTPS). Worst case: malicious release page — same risk as user manually visiting.

## Next Steps
Phase 04 (`MainWindow` wiring) constructs and shows this dialog.
