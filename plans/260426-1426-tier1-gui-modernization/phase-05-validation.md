# Phase 05 — Validation (manual walkthrough + rebuild + smoke)

## Context Links

- All prior phase files in this plan dir.
- Synthesis: `plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` §5 (look-and-feel checklist anchors what we visually verify).

## Overview

- **Priority:** P2 (gate before declaring Tier-1 done)
- **Status:** pending
- **Effort:** ~2h
- Manual UI walkthrough across all panels in light, dark, and system modes. Rebuild standalone, smoke both executables, capture before/after screenshot pair.

## Key Insights

- This phase is the only quality gate; we are not adding automated UI tests in Tier-1 (out of scope per YAGNI).
- The walkthrough must hit each of the four widgets so token + icon + theme work together.
- Frozen build catches PyInstaller-only failures (missing data files, hidden imports) that source runs hide.

## Requirements

**Functional**
- Light mode: every panel renders with correct backgrounds, borders, status colors, accent on focus / progress / selected control.
- Dark mode: same coverage, no white flashes on hover, no invisible text.
- System mode: OS theme flip propagates within ~2 s; selecting Light or Dark stops following OS until user reselects System.
- Restart with each saved mode → app boots into that mode, no flicker.
- Frozen GUI exe runs the same checks in System mode (sample subset).
- Frozen CLI exe still prints `--help` (regression check).

**Non-functional**
- Capture two screenshots (light, dark) of the Download tab to attach in the team status note.

## Architecture

No code in this phase. Sequence of human-driven checks. Rollback procedure (if a check fails) is documented per risk row.

## Related Code Files

**Read-only**
- All `gui/*.py`, `app.py`, `tiktokder.spec`, `requirements.txt`.

**No modifications expected.** If a fix is needed, file a follow-up under the offending phase, do not patch in phase 05.

## Implementation Steps

1. **Source-run walkthrough — Light:**
   - Settings → Appearance → Light.
   - Tab through all four widgets: focus ring uses accent indigo `#4F46E5`-derived shade.
   - Add a single TikTok URL → confirm Queued status uses muted token, Downloading uses warning, Complete uses success.
   - Force a fail (e.g., bad URL) → status uses error token (red).
   - Open About dialog — text legible.
2. **Source-run walkthrough — Dark:**
   - Repeat step 1 in Dark mode. Verify error border on bad URL is the dark-palette red, not a hardcoded `red` literal.
3. **System-follow test:**
   - Settings → Appearance → System.
   - Toggle Windows 11: Settings → Personalization → Colors → "Choose your mode" between Light and Dark.
   - Confirm app re-themes within ~2 s, no crash, listener logs no exceptions.
4. **Lock-mode test:**
   - Settings → Appearance → Light. Flip Windows mode to Dark. App must stay light.
   - Settings → Appearance → System. App must re-sync to Dark.
5. **Persistence test:**
   - Set Dark, close app. Reopen `data/config.json` and confirm `"theme_mode": "dark"`. Relaunch — opens directly in Dark with no Light flash.
6. **Icon visual check:**
   - Every button/menu icon visible and recognizable in both themes; no missing-glyph rectangles.
7. **Rebuild standalone:**
   - `python build.py`.
   - Capture: build duration, dist folder size (compare to phase 01 record).
8. **Frozen smoke:**
   - Launch `dist/TikTokDer/TikTokDer.exe` — verify default System mode, OS-flip listener works, Settings persist (`dist/TikTokDer/data/config.json` written next to exe per portable mode).
   - `dist/TikTokDer/TikTokDer-CLI.exe --help` exits 0.
9. **Screenshots:** capture Download tab in both themes (e.g., Win+Shift+S). Save outside the repo or in a temp dir — do NOT commit binary screenshots into the plan folder.
10. **Final size delta note:** append a 2-line summary to this phase's Todo (phase 01 size vs phase 05 size; should match closely — only deps changed).

## Todo List

- [ ] Source run, Light walkthrough — pass/fail per widget
- [ ] Source run, Dark walkthrough
- [ ] OS-flip test (System mode)
- [ ] Lock-mode test (Light + OS flip)
- [ ] Persistence test (config.json verified)
- [ ] Icon visual check both themes
- [ ] `python build.py` rebuild succeeds
- [ ] Frozen GUI launch + Settings persist
- [ ] Frozen CLI `--help` regression check
- [ ] Capture light/dark screenshots (off-tree)
- [ ] Record final bundle size + zip size in this file's Todo

## Success Criteria

- All 11 Todo checks pass.
- Zero crashes during OS theme flip.
- Frozen build size within ±5% of phase 01 measurement (deps changed but no UPX restoration).
- No raw hex remaining in `gui/` (re-grep `#[0-9a-fA-F]{6}`).
- No `qtawesome` import outside `gui/icons.py`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation / Rollback |
|---|---|---|---|
| Listener crash on OS flip in frozen build | Low | High | Logs in stderr; rollback = ship with `theme_mode = "system"` disabled (force `"light"`/`"dark"`). Investigate as bug in phase 03 follow-up. |
| Icons missing in frozen build only | Med | Med | Add `collect_data_files('qtawesome')` to spec, rebuild. |
| Bundle bloat exceeds expectation | Low | Low | Tier-2/3 packaging work (Inno Setup) compresses better than UPX anyway. Document. |
| Status colors illegible in dark mode | Low | Med | Adjust dark palette state.* hex values in `gui/tokens.py` (one-line fix), no architecture change. |
| Settings button group emits double signals on toggle | Low | Trivial | Filter on `checked=True` inside slot. |
| Source run passes but frozen build misses `pyqtdarktheme` data files | Low | Med | Add `collect_data_files('qdarktheme')` to spec; rebuild. |

## Security Considerations

- No new persisted data beyond `theme_mode` (non-sensitive string).
- No network calls introduced.

## Next Steps

- On all-pass: mark plan status `completed`, hand off to user.
- If any phase fails validation, log the failure into that phase's file under a "Defects" subsection, fix, retest only the affected steps.
- Follow-on: Tier-2 plan (toast/InfoBar, empty state, skeleton rows, focus rings, tray, drag-and-drop, geometry persistence) — separate plan dir.
