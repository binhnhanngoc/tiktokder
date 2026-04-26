# Phase 06 — Cutover: delete legacy widgets, finalise tests + docs

**Status:** pending
**Effort:** 1d
**Depends on:** Phases 02, 03, 04, 05

## Context Links
- Plan: `plan.md`
- Brainstorm: §4.1 ("Deprecated"), §8 step 6.

## Overview
Final cleanup pass. Delete legacy widget modules now that platform tabs + global URL bar fully cover their surface. Update tests, README, and `docs/codebase-summary.md`. Drop back-compat aliases.

## Key Insights
- **Hard cutover** (locked decision §3 in plan.md). No `layout_v2` flag.
- Tests touching `MainWindow.url_input` / `MainWindow.download_table` — point to new locations or rewrite.
- README sub-section about tabs needs full rewrite.

## Requirements
**Functional**
- All legacy widget modules deleted.
- Test suite green (unit + integration).
- Docs reflect new IA.

**Non-functional**
- No dead imports, no leftover `# TODO platform-first` markers.
- LOC delta acceptable (target net +150).

## Related Code Files
**Delete**
- `gui/channel_browser.py`
- `gui/download_tab.py`
- `gui/history_tab.py`
- `gui/url_input_panel.py`

**Modify (test surface)**
- `test_tiktokder.py` — most is URL/CLI logic; verify nothing still imports deleted modules.
- Any test referencing `MainWindow.download_tab`, `MainWindow.history_tab`, `MainWindow.channel_browser` → update to `MainWindow.tiktok_tab` / `MainWindow.facebook_tab` / their inner `queue_panel` / `library_panel`.
- `test_app_state.py` — verify new fields (`library_active_uploader_*`) round-trip.

**Modify (docs)**
- `README.md` — rewrite "GUI tabs" section under "Quick Start" + "Settings (GUI)" table to reflect 3-tab layout, saved channels, library, global URL bar.
- `docs/codebase-summary.md` — add `saved_channels_store.py`, `gui/platform_tab.py`, `gui/saved_channels_panel.py`, `gui/library_panel.py`, `gui/global_url_bar.py`, `gui/status_bar_widget.py`. Remove deleted modules.
- `docs/development-roadmap.md` (if exists) — mark UI-restructure phase done.
- `docs/project-changelog.md` (if exists) — add entry.

**Modify (back-compat removal)**
- `gui/main_window.py`:
  - Remove `self.url_input` / `self.download_table` aliases unless something else still imports them. (Search project; if only test files reference, update tests instead.)

## Implementation Steps
1. **Audit imports** of deleted modules:
   - `grep -rn "from gui.channel_browser" .`
   - `grep -rn "from gui.download_tab" .`
   - `grep -rn "from gui.history_tab" .`
   - `grep -rn "from gui.url_input_panel" .`
   - Each remaining hit → repoint or delete.
2. Run `grep -rn "MainWindow.download_tab\|MainWindow.history_tab\|MainWindow.channel_browser" .` and update tests.
3. Delete the four legacy `gui/*.py` modules.
4. Remove back-compat aliases in `MainWindow.__init__` if nothing imports them externally.
5. Re-run full test suite (`pytest -v`). Target: zero failures.
6. Smoke-test the GUI manually:
   - Start app → 3 tabs visible (TikTok / Facebook / Settings) + global URL bar + status bar.
   - Drop a TT URL → lands in TikTok queue, status updates.
   - Drop a mixed `.txt` → URLs split correctly.
   - Add saved channel → row appears → browse → "Download all new" with confirm dialog.
   - Library: click uploader → table filters; right-click → all actions work.
   - Settings: edit FB cookies path → live-propagates to FB panel.
   - Close + reopen → active tab + library uploader + saved channels restored.
7. Rewrite README "GUI tabs" subsection. Sample text:
   ```
   GUI tabs:
   - **TikTok** — saved channels list, per-platform queue, library (uploader sidebar + history table).
   - **Facebook** — same composite for Facebook pages/profiles.
   - **Settings** — global preferences plus TikTok and Facebook-specific options.

   A persistent URL bar at the top accepts pasted URLs or .txt drops; URLs auto-route to the matching platform's queue. The status bar shows per-platform queue counts and total completed.
   ```
8. Update `docs/codebase-summary.md` module list.
9. Add changelog entry: `[1.3.0] Platform-first UI restructure — saved channels persistence, library two-pane view, global URL bar, status bar badges.`
10. Bump app version constant if one exists (search `1.2.0` → only `README.md:5` appears; manual update there).

## Todo List
- [ ] Legacy modules deleted
- [ ] All `from gui.{deleted_module}` imports updated
- [ ] Tests updated; full suite green
- [ ] Manual smoke test passes (8 scenarios in step 6)
- [ ] README "GUI tabs" rewritten
- [ ] `docs/codebase-summary.md` updated
- [ ] `docs/project-changelog.md` entry added (if file exists)
- [ ] Version constant updated (1.2.0 → 1.3.0)
- [ ] Back-compat `url_input` / `download_table` aliases removed
- [ ] No `# TODO platform-first` or stale references in code

## Success Criteria
- `pytest -v` 100% pass.
- Manual smoke test: all 8 scenarios green.
- `git ls-files | grep -E "channel_browser|download_tab|history_tab|url_input_panel" | wc -l` returns 0.
- README sub-section accurately describes new IA.

## Risk Assessment
- **Hidden import** — a test file or `app.py` may reference a deleted module. Step 1 catches this; CI catches anything missed.
- **Forgotten back-compat alias** — removing `self.url_input` may break a test. Update tests in same PR.
- **Version-tag drift** — `tiktokder.spec` may pin a version string. Search and update.

## Security Considerations
- No new attack surface.

## Next Steps
- Notify Tauri-migration plan (`260426-1518-tauri-migration`) that block is lifted; SvelteKit IA in `phase-07-svelte-tabs.md` should be revised to match new platform-first IA.
- Optional follow-on plan: CLI parity for saved channels (`main.py --saved-channel <nickname>`).
