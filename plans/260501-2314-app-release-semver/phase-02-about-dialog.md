# Phase 02 — About Dialog with Version

## Context Links
- Plan overview: `plan.md`
- Blocker: `phase-01-version-ssot-and-wireup.md`
- Existing stub: `gui/main_window.py:417-424` (`_show_about` already wired to Help → About)

## Overview
- **Priority:** P2
- **Status:** pending
- **Description:** Enrich the existing `_show_about()` slot in `MainWindow` to display the SSOT version. Help menu and action already exist (verified at line 368-369). KISS: keep using `QMessageBox.about` — no new file, no custom dialog class.

## Key Insights
- `gui/main_window.py:_setup_menu` already adds `help_menu.addAction(..., "&About", self._show_about)` (line 369).
- `_show_about` (line 417) currently shows a hardcoded blurb without version. We just inject `__version__`.
- A dedicated `gui/about_dialog.py` was considered but rejected — `QMessageBox.about` covers all current needs in <15 lines. YAGNI.

## Requirements
**Functional**
- Help → About TikTokDer opens a dialog showing:
  - App name: TikTokDer
  - Version: from `version.__version__`
  - One-line description (existing copy retained)
  - License acknowledgement (MIT or "Open source — see LICENSE")
- Dialog is modal, has app icon, OK button to close.

**Non-functional**
- No new file required.
- `_show_about` body remains under 20 lines.

## Architecture
```
Help menu ──► _show_about() ──► QMessageBox.about(self, title, text)
                  │
                  └─► reads version.__version__
```
No new widget classes, no signals/slots beyond what already exists.

## Related Code Files
**Modify**
- `gui/main_window.py` — replace body of `_show_about` (lines 417-424) only. `from version import __version__` already added in phase-01.

**Create / Delete**
- None.

## Implementation Steps
1. Confirm `from version import __version__` is present in `gui/main_window.py` (added in phase-01).
2. Replace `_show_about` body (lines 417-424) with:
   ```python
   def _show_about(self) -> None:
       QMessageBox.about(
           self,
           "About TikTokDer",
           f"<h3>TikTokDer v{__version__}</h3>"
           f"<p>TikTok &amp; Facebook batch video downloader.</p>"
           f"<p>Download videos without watermarks. Powered by yt-dlp.</p>"
           f"<p><small>Open source — see LICENSE.</small></p>",
       )
   ```
   (HTML rendering is on by default for `QMessageBox.about` — gives clean line breaks without extra widgets.)
3. Smoke-test: launch GUI, click Help → About, verify "TikTokDer v1.4.0" header.

## Todo List
- [ ] Update `_show_about` body to include `__version__`
- [ ] Manual smoke-test: Help menu → About shows v1.4.0
- [ ] No new files created (verify YAGNI compliance)

## Success Criteria
- About dialog visible from Help menu, displays current `__version__`.
- No new GUI files added.
- `_show_about` remains under 20 lines.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| HTML formatting breaks on some Qt themes | Low | Very Low | `QMessageBox.about` is theme-agnostic standard widget |
| User wants richer About in future (links, contributors) | Medium | Low | Refactor to `gui/about_dialog.py` only when actually needed (YAGNI for now) |

## Security Considerations
- Version string is a static literal from `version.py` — no injection vector, no user input rendered as HTML.

## Next Steps
None — terminal phase from a code-flow perspective. Tested by manual smoke-test (no automated UI test — see plan-level note).
