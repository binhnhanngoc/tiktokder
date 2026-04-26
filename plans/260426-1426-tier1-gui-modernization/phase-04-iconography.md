# Phase 04 — Iconography (qtawesome helper + replacements)

## Context Links

- Synthesis: `plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` §5 item 10, §6 (qtawesome bundles), §8 Tier-1 item 2.
- Tokens: `gui/tokens.py` (built in phase 02) — supplies accent for tinted icons.
- Files with current icon/emoji surface area:
  - `gui/url_input_panel.py` — Paste / Add buttons (text only currently).
  - `gui/download_table.py` — Clear Completed / Clear All / Retry Failed / Cancel All buttons (text only).
  - `gui/channel_browser.py` — Browse / Select All / Deselect All / Download Selected (text only).
  - `gui/main_window.py` — File / Help menu actions (text only); window icon (already uses `icon.ico`, leave alone).

## Overview

- **Priority:** P3 (visible polish, not blocking)
- **Status:** completed
- **Effort:** ~3h
- Pick **Material Design Icons (`mdi6.*`)** as the single icon set. Provide `gui/icons.py` exposing `icon(name, color=None)` so callers don't import qtawesome directly. Add icons to existing toolbar/menu buttons. Replace any emoji or `QIcon.fromTheme(...)` usage (Grep currently confirms zero emoji and zero `fromTheme`, so this is mostly additive).

## Key Insights

- Audit shows existing UI is **text-only buttons**. Phase 04 is mostly *additive* — attach `mdi6.*` icons to existing `QPushButton`s and `QAction`s.
- qtawesome accepts a `color` kwarg per render; defaulting `color=None` lets Qt's palette/foreground handle it (good for theme-following). Pass an explicit token-resolved color only when we want accent emphasis.
- Single source: `from gui.icons import icon` is the only import. Direct `import qtawesome` outside `gui/icons.py` is a violation.
- Cache by `(name, color)` to avoid recreating QIcon on every menu rebuild — qtawesome is fast enough that a tiny LRU dict is sufficient.

## Requirements

**Functional**
- `gui/icons.py` exports `icon(name: str, color: str | None = None) -> QIcon`. Accepts qtawesome icon names (e.g., `"mdi6.content-paste"`).
- All buttons in the four GUI files above gain a relevant `mdi6.*` icon via `setIcon(icon(...))`.
- File/Help menu actions get icons via `addAction(icon(...), text, slot)`.

**Non-functional**
- No more than ~12 distinct icon names project-wide (KISS).
- No emoji introduced.
- No imports of `qtawesome` outside `gui/icons.py`.

## Architecture

```
gui/icons.py
  ├── _CACHE: dict[tuple[str, str|None], QIcon]
  └── icon(name, color=None) -> QIcon   # qtawesome.icon(name, color=color)

callers:
  url_input_panel  → mdi6.content-paste, mdi6.plus
  download_table   → mdi6.broom, mdi6.delete-sweep, mdi6.refresh, mdi6.stop
  channel_browser  → mdi6.magnify, mdi6.checkbox-multiple-marked-outline,
                     mdi6.checkbox-multiple-blank-outline, mdi6.download
  main_window menu → mdi6.exit-to-app (Exit), mdi6.information-outline (About)
```

## Related Code Files

**Create**
- `gui/icons.py`

**Modify**
- `gui/url_input_panel.py`
- `gui/download_table.py`
- `gui/channel_browser.py`
- `gui/main_window.py`

**Read for context**
- `gui/tokens.py` (only if we want to tint a specific icon with `accent.default`)

## Implementation Steps

1. **Create `gui/icons.py`:**
   ```python
   """qtawesome wrapper. Single source for icon lookups across the GUI."""
   from PySide6.QtGui import QIcon
   import qtawesome as qta

   _CACHE: dict[tuple[str, str | None], QIcon] = {}

   def icon(name: str, color: str | None = None) -> QIcon:
       key = (name, color)
       cached = _CACHE.get(key)
       if cached is not None:
           return cached
       qicon = qta.icon(name, color=color) if color else qta.icon(name)
       _CACHE[key] = qicon
       return qicon
   ```
2. **`gui/url_input_panel.py`:**
   - `self.paste_btn.setIcon(icon("mdi6.content-paste"))`
   - `self.add_btn.setIcon(icon("mdi6.plus"))`
3. **`gui/download_table.py`:**
   - `self.clear_btn.setIcon(icon("mdi6.broom"))`
   - `self.clear_all_btn.setIcon(icon("mdi6.delete-sweep"))`
   - `self.retry_failed_btn.setIcon(icon("mdi6.refresh"))`
   - `self.cancel_all_btn.setIcon(icon("mdi6.stop"))`
4. **`gui/channel_browser.py`:**
   - `self.browse_btn.setIcon(icon("mdi6.magnify"))`
   - `self.select_all_btn.setIcon(icon("mdi6.checkbox-multiple-marked-outline"))`
   - `self.deselect_all_btn.setIcon(icon("mdi6.checkbox-multiple-blank-outline"))`
   - `self.download_btn.setIcon(icon("mdi6.download"))`
5. **`gui/main_window.py`:**
   - `file_menu.addAction(icon("mdi6.exit-to-app"), "E&xit", self.close)`
   - `help_menu.addAction(icon("mdi6.information-outline"), "&About", self._show_about)`
6. **Sanity:** `python app.py` — confirm icons render in both themes (text remains visible alongside).

## Todo List

- [x] Create `gui/icons.py` (24 LoC, cached qtawesome wrapper)
- [x] Add icons to `url_input_panel.py` buttons
- [x] Add icons to `download_table.py` toolbar
- [x] Add icons to `base_browser_panel.py` buttons (shared base, covers both TikTok + Facebook tabs)
- [x] Add icons to `main_window.py` menu actions
- [ ] Visual check: icons render light + dark, no missing-glyph squares *(manual follow-up)*
- [x] Grep `qtawesome` usage outside `gui/icons.py` — confirmed zero matches

## Success Criteria

- Every actionable button/menu item in the four GUI files has an icon.
- `grep -r "qtawesome" gui/ --exclude=icons.py` returns nothing.
- No regression in window layout (icons fit within existing button heights — qtawesome auto-sizes to text height by default).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Icon names mistyped → `KeyError` from qtawesome | Med | Low | Manual smoke at end of phase catches all 12 names. |
| Icons invisible in dark mode (default color follows palette but stylesheet may override) | Low | Low | If dark icons appear black on dark bg, pass `color=token('text.primary')` — only as needed. |
| Frozen build missing qtawesome font data | Low (already deps-installed) | Med | If reproduced: add `collect_data_files('qtawesome')` to `tiktokder.spec` GUI Analysis `datas`, rebuild. |
| Icon-name drift between qtawesome major versions (`mdi.` vs `mdi6.`) | Low | Trivial | Pin `qtawesome>=1.3.0` (mdi6 introduced 1.3); document. |
| Button widths reflow and break layout | Low | Trivial | Visual check; tweak `setSpacing` if needed (use `gui.spacing.SM`). |

## Security Considerations

None — bundled font data only.

## Next Steps

- Phase 05 final walkthrough catches any remaining visual issue.
- Tier-2 may extend `gui/icons.py` with a status-indicator helper (success/error pictograms next to status text).
