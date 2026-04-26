# Phase 03 — Settings UI Path Picker

## Context Links
- Phase 01 (config foundation): `./phase-01-config-and-migration.md`
- Existing FB cookies UI: `gui/settings_panel.py:152-180`

## Overview
- **Priority:** P2
- **Status:** completed
- **Depends on:** Phase 01
- **Effort:** S (~30 min)
- **Description:** Add a path picker for `tiktok_cookies_file` under the TikTok Settings group, mirroring the existing FB cookies picker. Auto-save + propagate to live engine state.

## Key Insights
- FB block at `gui/settings_panel.py:152-180` is a working template — copy structure, swap labels and config field.
- Existing settings auto-save pattern: edit signal → handler writes to `config` → calls live-update on `engine`. Reuse the same pattern.

## Requirements
**Functional**
- New row under TikTok group: label "Cookies File", read-only path field, "Browse..." button, optional "Clear" button
- Browse opens native file dialog filtered to `*.txt` (Netscape format)
- Selected path persists to `config.tiktok_cookies_file` and propagates to in-flight engine
- Tooltip: `"Optional. Overrides Cookie Browser. Export via 'Get cookies.txt LOCALLY' extension while logged in."`
- Field renamed `facebook_cookies_file` continues to work in existing FB row (binding update)

**Non-functional**
- Visually consistent with FB cookies row (same widget classes, spacing, button labels)
- File dialog defaults to user's Downloads folder if no prior selection

## Architecture
```
Settings panel layout (TikTok group):
┌───────────────────────────────────────────────┐
│ Cookie Browser   [None ▾]                     │ existing
│ Cookies File     [______________] [Browse]    │ NEW
└───────────────────────────────────────────────┘

Settings panel layout (Facebook group):
┌───────────────────────────────────────────────┐
│ Cookies File     [______________] [Browse]    │ existing (rename binding)
│ Default Max Scrolls  [10 ▴▾]                  │ existing
└───────────────────────────────────────────────┘
```

## Related Code Files
**Modify:**
- `gui/settings_panel.py` — add TikTok cookies row; update FB row to bind `facebook_cookies_file`

**Read for context:**
- `config.py` (post-Phase 01) — confirm field names
- `download_engine.py` — find live-propagation entry point (search for setter calls on settings changes)

**Create:** none

## Implementation Steps
1. Locate FB cookies block (`settings_panel.py` ~152-180) — note widget creation, signal wiring, save handler
2. Update FB block: rebind `cookies_file` → `facebook_cookies_file` (label, save handler, init read)
3. In TikTok group section, add a parallel block:
   - Label widget: "Cookies File"
   - Line edit (read-only display) + Browse button
   - File dialog with `.txt` filter
   - Clear button (optional — match FB behavior)
4. Wire signals: on browse-confirmed → `config.tiktok_cookies_file = Path(selected)` → call live-propagate method (same one FB uses)
5. On settings panel init: read `config.tiktok_cookies_file`, populate display field
6. Set tooltip per Requirements
7. Compile check + visual smoke: `python app.py` → Settings → confirm row appears, Browse opens dialog, selection persists across restart

## Todo List
- [x] Update FB cookies row to bind `facebook_cookies_file`
- [x] Add TikTok "Cookies File" row (label + line edit + Browse)
- [x] Wire Browse to file dialog, save selected path to config
- [x] Wire init read from config to populate display
- [x] Add tooltip
- [x] Smoke test offscreen-Qt confirms field round-trips through config.json (visual GUI check left to user)

## Success Criteria
- TikTok group shows "Cookies File" row directly below "Cookie Browser"
- Browse opens native file dialog filtered to `.txt`
- Selected path appears in line edit
- Restart app → field still populated
- Setting flows through to live download engine without restart (verifiable: change path, queue download, confirm yt-dlp picks up new path)
- FB cookies row continues to work after binding rename

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| Layout shifts disrupt other rows in TikTok group | Use existing layout primitives (likely `QFormLayout`); insert at end of TikTok group |
| File dialog filter blocks valid cookies in non-`.txt` files | Use `.txt` as default filter but allow "All Files" option |
| Live-propagate handler not found / not used by FB row | Fallback: require app restart; document in tooltip |
| Path with spaces breaks downstream | Phase 02's helper already passes `str(path)` to yt-dlp; yt-dlp handles spaces |

## Security Considerations
- Browse dialog is local file access only; no upload
- Selected path stored in plain config (consistent with FB)
- Cookie file content never displayed in UI (path only)

## Next Steps
- Phase 04 adds tests + updates README Settings table
