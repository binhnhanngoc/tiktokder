---
title: "Phase 06 — Settings panel extensions"
priority: P0
effort: 25m
status: planned
depends: [01]
---

# Phase 06 — Settings Panel Extensions

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ Quality selector → Settings default, § Polish — subs+thumb toggles)
- Affected file: `gui/settings_panel.py` (currently 96 LOC)

## Overview
Add three new controls to Settings: `Default Quality` combo, `Write subtitles (en)` checkbox, `Write thumbnail` checkbox. Auto-save on change (existing pattern). `settings_changed` signal already plumbed; engine consumes new fields in Phase 07.

## Key Insights
- Existing Settings has `Output Directory`, `Concurrent Downloads`, `Delay`, `Cookie Browser`, `Reset to Defaults`, all auto-saving. Just append three more rows.
- Quality combo items: `Best`, `1080p`, `720p`, `480p`, `Audio only`. Map UI label → config string (`best|1080p|720p|480p|audio`).
- Tooltip on Quality combo: "Audio-only and 480p+ require ffmpeg" (matches `_warn_ffmpeg_missing` policy).

## Requirements

### Functional
- New row: `Default Quality:` → `QComboBox` with 5 options. Persists to `AppConfig.quality_default`.
- New row: `Write subtitles (en):` → `QCheckBox`. Persists to `AppConfig.write_subtitles`.
- New row: `Write thumbnail:` → `QCheckBox`. Persists to `AppConfig.write_thumbnail`.
- All three trigger `settings_changed` on change (re-uses existing `_save` slot).
- `Reset to Defaults` resets the new controls to `Best`, unchecked, unchecked.

### Non-Functional
- `gui/settings_panel.py` ≤ 150 LOC after additions.
- No layout regression — existing rows remain in current order; new rows appended below cookie browser.

## Architecture

### Combo Mapping
```python
QUALITY_LABELS = [
    ("Best", "best"),
    ("1080p", "1080p"),
    ("720p", "720p"),
    ("480p", "480p"),
    ("Audio only", "audio"),
]
```

### Layout Order
```
Output Directory:    [QLineEdit] [Browse...]
Concurrent Downloads:[QSpinBox]
Delay Between (s):   [QDoubleSpinBox]
Cookie Browser:      [QComboBox]
Default Quality:     [QComboBox]            ← new
Write subtitles (en):[QCheckBox]            ← new
Write thumbnail:     [QCheckBox]            ← new
                     [Reset to Defaults]
```

## Related Code Files

### To Modify
- `gui/settings_panel.py` — add three controls and their save bindings.
- `test_config.py` (already touched in Phase 01) — no further changes here unless we add Settings persistence test (skip — settings tests are GUI-level, covered by manual smoke).

### Not Touched This Phase
- `download_engine.py` — Phase 07 wires the new fields into engine.
- `downloader.py` — already accepts these args (Phase 03).

## Implementation Steps
1. Import `QCheckBox` (already imported indirectly? check) in `gui/settings_panel.py`.
2. Add `quality_combo` with `QUALITY_LABELS`; set current text from `config.quality_default`.
3. Add `subs_check` and `thumb_check`; set checked from config.
4. Connect `currentIndexChanged` (combo) and `stateChanged` (check) to `_save`.
5. Extend `_save` to write `quality_default`, `write_subtitles`, `write_thumbnail` from controls into config.
6. Extend `_reset_defaults` to reset the three controls.
7. Manual smoke: change quality to 720p, restart, verify persisted.

## Todo
- [ ] Add `QUALITY_LABELS` constant.
- [ ] `quality_combo` row + binding.
- [ ] `subs_check` row + binding.
- [ ] `thumb_check` row + binding.
- [ ] Extend `_save` to write three new fields.
- [ ] Extend `_reset_defaults`.
- [ ] Manual restart-persistence smoke.

## Success Criteria
- Settings tab shows three new controls below Cookie Browser, above Reset button.
- Changing any of them auto-saves and emits `settings_changed`.
- Restarting the app loads the previously-set values.
- `Reset to Defaults` resets to `Best`, unchecked, unchecked.
- File ≤ 150 LOC.

## Risk & Mitigation
- **Combo label/value mismatch** — use `(label, value)` tuple iteration; index `userData` per item via `addItem(label, value)`; read via `currentData()`.
- **Checkbox `stateChanged` fires during initial setup** — block signals during construction or check via `blockSignals`.

## Security
- N/A — UI-only.

## Next Steps
- Phase 07 reads `config.quality_default / write_subtitles / write_thumbnail` and forwards to `DownloadEngine`.
