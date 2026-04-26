# Phase 01 — Config Field + Rename + Migration Shim

## Context Links
- Brainstorm: `plans/reports/brainstorm-260427-0013-tiktok-cookies-parity.md`
- Existing FB cookie field: `config.py` (search: `cookies_file`)

## Overview
- **Priority:** P2
- **Status:** completed
- **Effort:** S (~30 min)
- **Description:** Add `tiktok_cookies_file: Path | None` to `AppConfig`, rename existing `cookies_file` → `facebook_cookies_file`, add migration shim that reads the old key.

## Key Insights
- `cookies_file` is FB-only today (used in `facebook_fetcher.py` Playwright injection). Renaming for symmetry pays off long-term.
- Migration: read both old + new key on load; write only the new key on save. Remove shim in 2 releases.

## Requirements
**Functional**
- `AppConfig.tiktok_cookies_file: Path | None` exists, defaults `None`
- `AppConfig.facebook_cookies_file: Path | None` (renamed from `cookies_file`)
- Loading a config file with the legacy `cookies_file` key → value lands in `facebook_cookies_file`
- Saving always writes the new key only (legacy key not re-emitted)

**Non-functional**
- No breaking change for users with existing `config.json` / settings store
- Migration silent (no warning needed for cookie field)

## Architecture
```
AppConfig (config.py)
├── tiktok_cookie_browser: str | None     # existing
├── tiktok_cookies_file: Path | None      # NEW
├── facebook_cookies_file: Path | None    # RENAMED from cookies_file
└── ...

config.load(path) → reads "cookies_file" OR "facebook_cookies_file" → assigns to facebook_cookies_file
config.save(path) → writes only "facebook_cookies_file"
```

## Related Code Files
**Modify:**
- `config.py` — add field, rename, update load/save logic

**Read for context:**
- `gui/settings_panel.py:152-180` — current FB cookies wiring (informs rename impact)
- `facebook_fetcher.py:160-185` — current consumer of `cookies_file`
- `downloader.py:64-66` — TikTok cookie wiring (foundation for Phase 02)

**Create:** none

## Implementation Steps
1. Open `config.py`, locate `cookies_file` field declaration
2. Rename field to `facebook_cookies_file` (keep `Path | None` type, default `None`)
3. Add `tiktok_cookies_file: Path | None = None` adjacent to `tiktok_cookie_browser`
4. In config-load function (search for the JSON-decode site):
   - If raw dict has `cookies_file` and not `facebook_cookies_file`, copy value to new field
   - Coerce string → `Path` if non-None
5. In config-save: serialize `facebook_cookies_file` and `tiktok_cookies_file` under their canonical keys; do NOT emit `cookies_file`
6. Update any direct `config.cookies_file` references in the same file (likely only declaration + load/save)
7. Run `python -m py_compile config.py` to confirm syntax

## Todo List
- [x] Rename `cookies_file` → `facebook_cookies_file` in `AppConfig`
- [x] Add `tiktok_cookies_file: str | None = None` (kept `str` for JSON-serialization symmetry with existing field)
- [x] Add legacy-key fallback in load logic
- [x] Update save logic to emit new keys only (filter drops legacy key after migration)
- [x] `python -m py_compile config.py` passes
- [x] Updated downstream consumers in `gui/main_window.py` + `gui/settings_panel.py` to use renamed field

## Success Criteria
- `python -c "from config import AppConfig; c = AppConfig(); print(hasattr(c, 'tiktok_cookies_file'), hasattr(c, 'facebook_cookies_file'))"` prints `True True`
- A test config JSON with old `cookies_file` key loads → resulting `AppConfig.facebook_cookies_file` is set correctly
- Saved config JSON contains `facebook_cookies_file` key, no `cookies_file` key

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| Other modules reference `config.cookies_file` directly | Phase 02 + 03 update all call sites — grep before declaring done |
| Settings panel widget bound to old name breaks UI | Phase 03 updates the binding |
| Test fixtures use old key | Phase 04 updates fixtures |

## Security Considerations
- File path stored as-is in config; not validated until used by yt-dlp/Playwright (existing pattern)
- No logging of cookie values; only paths

## Next Steps
- Phase 02 consumes `tiktok_cookies_file` via `apply_cookies()` helper
- Phase 03 binds Settings UI to the new field
