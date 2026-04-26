# Phase 05 — Settings split (Global + per-platform sections)

**Status:** pending
**Effort:** 0.5d
**Depends on:** Phase 02

## Context Links
- Plan: `plan.md`
- Brainstorm: §3.3
- Modifies: `gui/settings_panel.py`.

## Overview
Split the single SettingsPanel into three logical sections shown via a vertical group layout (or `QTabWidget` if visual review prefers): **Global**, **TikTok**, **Facebook**. No new persistence — everything still lives in `AppConfig`. Live propagation already runs through `_apply_settings`; signal stays the same.

## Key Insights
- Cleanest visual: `QGroupBox`-per-section in a `QVBoxLayout` (preserves existing form-style UX, adds visual grouping). Avoids extra tabs nested inside the Settings tab.
- TikTok-specific: `cookie_browser` only.
- Facebook-specific: `cookies_file` + `max_scrolls` default + login-wall help text.
- Global: output_dir, workers, delay, default quality, write_subs, write_thumb, history_max_entries, theme.
- `max_scrolls` default is currently per-FB-panel (10). Adding a Settings entry means `FacebookBrowserPanel.scrolls_spin.setValue(config.facebook_max_scrolls_default)` on init.

## Requirements
**Functional**
- One `SettingsPanel` widget with three `QGroupBox` sections.
- All fields auto-save (existing pattern preserved).
- New `AppConfig.facebook_max_scrolls_default: int = 10`.
- `_apply_settings` propagates to FB panel default.

**Non-functional**
- No new dependencies. Layout fits within existing window default size (900×600).

## Architecture
```
gui/settings_panel.py    (modified)
  class SettingsPanel(QWidget):
    QVBoxLayout
    ├── QGroupBox "Global"        (existing fields except cookie/cookies_file)
    ├── QGroupBox "TikTok"        (cookie_browser)
    └── QGroupBox "Facebook"      (cookies_file, max_scrolls default, login-wall help link)
```

## Related Code Files
**Modify**
- `gui/settings_panel.py` — restructure layout into three QGroupBoxes; add `facebook_max_scrolls_default` field.
- `config.py` — add `facebook_max_scrolls_default: int = 10` to `AppConfig`.
- `gui/main_window.py` — propagate `config.facebook_max_scrolls_default` to `FacebookBrowserPanel.scrolls_spin` in `_apply_settings`.

**Read for context**
- `gui/settings_panel.py` — full file; refactor in place.
- `gui/facebook_browser_panel.py:30-37` — current scrolls_spin default.

## Implementation Steps
1. Add `facebook_max_scrolls_default: int = 10` to `AppConfig` in `config.py`.
2. Refactor `gui/settings_panel.py`:
   - Wrap form rows in three `QGroupBox` widgets.
   - Move `cookie_combo` + label under "TikTok".
   - Move `cookies_file_input` + label + new `fb_scrolls_default_spin` under "Facebook".
   - Keep all auto-save signal wiring intact.
3. In `MainWindow._apply_settings`, propagate FB scrolls default:
   ```python
   self.facebook_tab.browser_panel.scrolls_spin.setValue(self.config.facebook_max_scrolls_default)
   ```
   (Only when current value matches old default — avoid clobbering an in-session change. Or: set on init only.)
4. On `FacebookBrowserPanel.__init__`, accept optional `default_scrolls` param; pass `config.facebook_max_scrolls_default` from `MainWindow`.
5. Tests:
   - `SettingsPanel` builds without errors.
   - Editing `cookies_file_input` triggers `settings_changed`.
   - `AppConfig.facebook_max_scrolls_default` round-trips through load/save.
   - FB panel created with default=15 from config gets scrolls_spin set to 15.

## Todo List
- [ ] `AppConfig.facebook_max_scrolls_default` added (default 10)
- [ ] `SettingsPanel` restructured into 3 QGroupBoxes
- [ ] FB scrolls default field added under Facebook group
- [ ] `MainWindow._apply_settings` propagates FB default
- [ ] All existing settings tests still pass
- [ ] No regression in auto-save behaviour

## Success Criteria
- Visual: clear three-section grouping in Settings tab.
- TikTok cookie change live-applies to TikTok engine path; FB cookies path live-applies to FB panel.
- Adjusting FB default scrolls in Settings updates next `FacebookBrowserPanel` fetch.

## Risk Assessment
- **Auto-save signal multiplexing** — new spinbox needs `valueChanged.connect(self._save)` like other fields. Easy to forget; covered by smoke test.

## Security Considerations
- None new — existing file picker validates paths.

## Next Steps
Phase 06 deletes legacy widgets and finalises tests/docs.
