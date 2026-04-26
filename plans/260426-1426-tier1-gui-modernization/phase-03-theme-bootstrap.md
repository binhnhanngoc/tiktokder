# Phase 03 — Theme Bootstrap (qdarktheme + darkdetect listener + Settings)

## Context Links

- Synthesis: `plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` §1, §5 item 3, §6 (Qt theming libs), §8 Tier-1 items 2 + 5.
- Entry point: `app.py`
- Main window: `gui/main_window.py`
- Settings UI: `gui/settings_panel.py`
- Config persistence: `config.py` (`AppConfig` dataclass)
- Tokens module: `gui/tokens.py` (built in phase 02)

## Overview

- **Priority:** P2 (the visible deliverable)
- **Status:** completed
- **Effort:** ~4h
- Apply `qdarktheme.setup_theme("auto", custom_colors={"primary": "#4F46E5"})` at startup. Run `darkdetect.listener` on a daemon thread that re-applies theme + calls `tokens.set_mode(...)` on OS theme changes. Add a `System / Light / Dark` segmented control in Settings, persisted as `AppConfig.theme_mode`. **Manual override beats listener** — when user picks Light or Dark, the listener stops driving theme until they switch back to System.

## Key Insights

- `qdarktheme.setup_theme("auto" | "light" | "dark", custom_colors={...})` is the one-liner; safe to call multiple times to re-apply on switch.
- `darkdetect.listener(callback)` blocks; it must run in a daemon thread (`threading.Thread(daemon=True)`). Callback is invoked on Windows via WM_SETTINGCHANGE — runs in the listener thread, not the Qt main thread, so the callback must marshal back via a `QObject.signal` → main thread slot before calling `qdarktheme.setup_theme(...)`.
- `darkdetect` Linux support is partial (depends on DE); on macOS/Windows it works. Acceptable for Tier-1.
- `AppConfig` already auto-saves on Settings change via `_save()` → reuse the same path. Add one new field: `theme_mode: str = "system"` with allowed values `{"system", "light", "dark"}`.
- Segmented control in PySide6 = three `QPushButton(checkable=True)` in a `QButtonGroup(exclusive=True)`. Keep it as such — no third-party widget needed.

## Requirements

**Functional**
- On app start: read `config.theme_mode`. If `"system"` → call `qdarktheme.setup_theme("auto", custom_colors={"primary": "#4F46E5"})` and start listener. If `"light"`/`"dark"` → call `setup_theme("light"|"dark", custom_colors=...)`, do NOT start listener.
- After `setup_theme(...)`: detect resolved mode via `darkdetect.isDark()` (or `qdarktheme.load_palette()` inspection) and call `tokens.set_mode("dark" if dark else "light")`.
- Settings → Appearance: three segmented buttons (`System` / `Light` / `Dark`). Selecting one updates `config.theme_mode`, calls `save_config(...)`, re-applies theme, and starts/stops the listener appropriately.
- Listener callback (off-thread) emits a Qt signal carrying the new resolved mode; a slot on the main thread re-applies `qdarktheme.setup_theme("auto", ...)` and `tokens.set_mode(...)`.
- The custom accent `#4F46E5` (indigo) is the single brand color. *(If product owner answers TikTok-pink later, swap one constant.)*

**Non-functional**
- No flicker on first paint (apply theme before `window.show()`).
- Listener thread has no shared mutable state with the GUI other than the signal emission.

## Architecture

```
app.py
  └── theme.bootstrap(app, config) ────────► qdarktheme.setup_theme(...)
                                              tokens.set_mode(...)
                                              start ThemeListener (daemon)
                                                       │
                                                       ▼ darkdetect.listener(cb)
                                                       │ (off-thread)
                                                       ▼ Qt Signal → main thread slot
                                              re-apply qdarktheme + tokens
gui/settings_panel.py
  └── AppearanceGroup (3 buttons) ──► theme.set_mode(mode)
                                        ├── persist to config
                                        └── re-apply / restart listener as needed
```

New module: `gui/theme.py` owning `bootstrap()`, `apply(mode)`, `ThemeListener` (`QObject` subclass with signal). Single source of truth for theme transitions.

## Related Code Files

**Create**
- `gui/theme.py` — bootstrap, apply, listener, accent constant.

**Modify**
- `app.py` — call `theme.bootstrap(app, config)` before `MainWindow(config)`.
- `config.py` — add `theme_mode: str = "system"` to `AppConfig`.
- `gui/settings_panel.py` — add Appearance row with three checkable buttons in a `QButtonGroup`; wire to `theme.apply` + persist.
- `gui/main_window.py` — no logic change, but ensure `_show_about` and any QMessageBox callsites still render OK in dark mode (visual only).

**Read for context**
- `gui/tokens.py` (built in phase 02 — `set_mode` is the integration point).

## Implementation Steps

1. **Extend `AppConfig`** in `config.py`:
   - Add `theme_mode: str = "system"`.
   - Existing JSON load/save already filters unknown keys, so older configs upgrade silently.
2. **Create `gui/theme.py`:**
   - Constants: `ACCENT = "#4F46E5"`, `ALLOWED_MODES = ("system", "light", "dark")`.
   - `class _ThemeBridge(QObject)` with `system_theme_changed = Signal(str)` (emits `"Dark"` or `"Light"`).
   - `_listener_thread: threading.Thread | None = None` module-level.
   - `def apply(mode: str) -> None` — calls `qdarktheme.setup_theme(mode if mode in ("light","dark") else "auto", custom_colors={"primary": ACCENT})`, then sets tokens via `tokens.set_mode("dark" if darkdetect.isDark() else "light")`.
   - `def _start_listener_if_needed(mode: str)` — starts daemon listener only when `mode == "system"`; idempotent (don't double-start).
   - `def _stop_listener()` — `darkdetect.listener` has no stop API, so we set a flag and let the daemon thread die at process exit. For runtime stop semantics: just ignore further signals when current mode is not "system" (gate inside the slot). Document this.
   - `def bootstrap(app, config)` — calls `apply(config.theme_mode)` and `_start_listener_if_needed(config.theme_mode)`.
   - `def set_mode(mode: str) -> None` — public API used by Settings; validates, calls `apply`, manages listener flag.
3. **Wire `app.py`:**
   - Import and call `theme.bootstrap(app, config)` after `app.setApplicationName(...)` and before `MainWindow(config)`.
4. **Add Appearance row to `gui/settings_panel.py`:**
   - Top of layout (before Output Directory) or as a new row labelled `"Appearance:"`.
   - `QHBoxLayout` containing three `QPushButton(checkable=True)` ("System", "Light", "Dark") in a `QButtonGroup(exclusive=True)`.
   - Pre-check button matching `config.theme_mode`.
   - On toggle (`buttonToggled` signal, filter to `checked=True`): call `theme.set_mode(value)` and `self._save()`.
5. **Smoke checks:**
   - Source run: change OS dark/light (Win11 Settings → Personalization → Colors) → app should follow within ~1 s when in System mode.
   - Pick Light in Settings → app stays light when OS flips.
   - Pick System again → app re-syncs to current OS state.
   - Restart app → mode persists (`data/config.json` shows `"theme_mode": "..."`).

## Todo List

- [x] Add `theme_mode` to `AppConfig` (default `"system"`)
- [x] Create `gui/theme.py` with bootstrap/apply/set_mode/listener
- [x] Wire `theme.bootstrap` into `app.py` before window creation
- [x] Add Appearance segmented control to `gui/settings_panel.py`
- [x] Persist mode via dedicated `_on_theme_toggled` (calls `save_config` directly)
- [ ] Manual: OS-flip test in System mode (Windows) *(manual follow-up)*
- [ ] Manual: lock-mode test (Light selected, OS flipped → app stays light) *(manual follow-up)*
- [ ] Manual: restart-persistence test *(manual follow-up)*
- [ ] Verify accent `#4F46E5` visibly applied to focus / progress / selected button *(manual follow-up)*

## Success Criteria

- App theme resolves correctly on cold start for all three modes.
- OS theme change in System mode triggers re-apply within 2 s, no crash.
- Settings selection survives restart (config.json shows correct value).
- Tokens module reports the resolved mode after every `theme.apply(...)` call (verified via a temporary `print` during dev, removed before phase 05).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `darkdetect.listener` callback executes on non-Qt thread, calling Qt → crash | High if not handled | High | Always marshal via `Signal` → main-thread slot. Never call `qdarktheme.setup_theme` from listener thread. |
| `qdarktheme` overrides custom QSS in `gui/url_input_panel.py` (red border) | Med | Low | Inline stylesheet on a single QLineEdit takes precedence over app stylesheet — observed behaviour, but verify. |
| `darkdetect` returns wrong value on Linux | Med | Low (Tier-1 is Win-first) | Document; if user reports, fall back to `theme_mode = "light"`. |
| Listener never stops cleanly on user switch to Light/Dark | Certain (no stop API) | Trivial | Gate inside the slot: ignore signal if `current_mode != "system"`. Daemon thread dies at process exit. |
| Settings UI mis-checks button on first show | Low | Trivial | Block signals while pre-checking, then unblock. |
| qdarktheme `custom_colors={"primary": ACCENT}` API drift | Low | Med | Pin `pyqtdarktheme>=2.1.0`; if API changes, fall back to no custom_colors and document. |
| Older config without `theme_mode` field | Already handled | None | `config.load_config` filters by known fields; missing field uses dataclass default `"system"`. |

## Security Considerations

- Listener thread only reads OS theme state via `darkdetect` (no network, no file I/O).
- No new persisted secrets; `theme_mode` is non-sensitive.

## Next Steps

- Phase 04 can run independently; tokens already reflect the resolved theme.
- Phase 05 will visually walk through both themes and the System-flip behaviour.
