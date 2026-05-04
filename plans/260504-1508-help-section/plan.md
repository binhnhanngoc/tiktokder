# Help Section for TikTokDer

**Date:** 2026-05-04 · **Branch:** main · **Status:** Draft

## Goal
Add an in-app Help section so users can read the manual, learn how to export
cookies (TikTok + Facebook), configure cookies, troubleshoot, and discover
features without leaving the app.

## Approach (KISS)
Single tabbed `HelpDialog` (QDialog + QTabWidget + QTextBrowser per tab) with
HTML content baked into Python constants. Open from the existing `Help` menu
in `MainWindow`. Each menu item jumps to the relevant tab. F1 opens the dialog
on the first tab.

Why a dialog (not a 4th main tab):
- Keeps top-level IA stable (TikTok / Facebook / Settings).
- Avoids paying main-window real estate for read-only docs.
- Modal/non-modal optional; we use **non-modal** so users can keep the help
  window open while exporting cookies in their browser.
- HTML in `QTextBrowser` gives clickable links + formatting for free.

## Tabs
1. **Getting Started** — first launch, drag-drop, queue/library basics.
2. **Cookies — Export Guide** — step-by-step "Get cookies.txt LOCALLY" usage
   on Chrome/Firefox/Edge, what file to save, where to save it.
3. **Cookies — Configure** — Settings → TikTok / Facebook Cookies File,
   browser auto-extract (TikTok), what each option fixes.
4. **Channels &amp; Library** — saving channels, Download all new, library
   filters, Downloaded filter.
5. **Troubleshooting** — rate-limits, login walls, missing ffmpeg, dedup,
   "Force Download".
6. **Shortcuts** — F1, Ctrl+Q, Ctrl+F, Tab navigation.
7. **About** — version, GitHub link, license.

## Files
**Create:**
- `gui/help_dialog.py` — `HelpDialog(QDialog)` + tab content constants.
- `test_help_dialog.py` — Qt offscreen tests for instantiation, tab count,
  `open_at_tab` navigation, content non-empty.
- `plans/260504-1508-help-section/plan.md` — this file.

**Modify:**
- `gui/main_window.py` — extend `_setup_menu`; add new actions and slots.
- `docs/gui-usage.md` — note Help menu and F1; update Keyboard Shortcuts.
- `README.md` — short bullet under Features; mention `Help` menu.

**Untouched:** engine, downloader, history, config — pure UI feature.

## Acceptance Criteria
- `Help` menu lists: User Manual (F1), Export Cookies, Configure Cookies,
  Channels &amp; Library, Troubleshooting, Shortcuts, About.
- F1 opens the dialog on tab 0.
- Each menu item opens the dialog on its corresponding tab.
- All tab bodies have non-empty HTML; external `https://` links open in the
  user's browser via `QDesktopServices`.
- Existing tests still pass; new tests pass.
- `gui/help_dialog.py` &lt; 200 LOC (split content if needed).

## Out of Scope
- Localization (English only).
- In-app cookie export tooling (still relies on browser extension).
- Video tutorials / GIF assets.

## Risks
- HTML content rot when features change. **Mitigation:** keep wording
  high-level; concrete UI strings re-checked during release process.

## Phases
Single-phase implementation (small surface area). No separate phase files.
