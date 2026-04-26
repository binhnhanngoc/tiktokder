# Phase 02 — Semantic Tokens & Spacing Constants

## Context Links

- Synthesis: `plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` §5 (items 2 + 6), §8 (Tier-1 items 3–4); researcher-4 §4 supplies the exact hex values.
- Existing hex usage: `gui/download_table.py:30-37, 164` (status colors); `gui/url_input_panel.py:67` (red error border).
- Existing layout calls audited: `gui/url_input_panel.py:27`, `gui/download_table.py:61` (`setContentsMargins(0,0,0,0)` — already minimal, leave alone).

## Overview

- **Priority:** P2 (foundation for theming + iconography)
- **Status:** completed
- **Effort:** ~3h
- Define 14 semantic color tokens (mapped per theme) and the 4/8 spacing scale. Migrate `gui/download_table.py` status color map from hardcoded hex to token lookup. Replace the inline error border in `url_input_panel.py`.

## Key Insights

- Tokens must resolve **at call time**, not at import time, because the theme can switch live (phase 03). Helper `token(name)` reads current mode each call — cheap dict lookup, no caching needed.
- Spacing scale is constants-only; no helper functions. KISS.
- Don't chase 100% migration of `setContentsMargins`/`setSpacing` — only touch what's already tied to visible spacing. The two existing calls are `(0,0,0,0)` resets, which stay.
- 14 tokens: `bg.canvas`, `bg.surface`, `bg.subtle`, `border.default`, `border.strong`, `text.primary`, `text.secondary`, `text.muted`, `accent.default`, `accent.hover`, `accent.fg`, `state.success`, `state.warning`, `state.error`, `state.info` — wait, that's 15. Spec says 14. Drop `state.info` if not currently surfaced; keep if a future toast needs it. Decision: keep all 15 (one extra is fine, naming clean) and document in token file.

## Requirements

**Functional**
- `gui/tokens.py` exposes:
  - `LIGHT: dict[str, str]` and `DARK: dict[str, str]` palettes.
  - `set_mode(mode: str) -> None` where `mode in {"light", "dark"}`.
  - `current_mode() -> str`.
  - `token(name: str) -> str` returns hex for the currently-active mode; raises `KeyError` on unknown name.
- `gui/spacing.py` exposes module-level constants `XS=4, SM=8, MD=12, LG=16, XL=24, XXL=32, XXXL=48`.
- `gui/download_table.py` reads status colors via `token("state.success" | "state.warning" | "state.error" | "text.muted")` instead of inline hex.
- `gui/url_input_panel.py` error styling reads `token("state.error")` instead of literal `red`.

**Non-functional**
- File length: tokens.py <100 LoC, spacing.py <30 LoC.
- No imports from PySide6 in tokens/spacing modules — keep them pure-Python so they're testable headlessly.

## Architecture

Module shape:

```
gui/
├── tokens.py     # palette dicts + set_mode/current_mode/token()
├── spacing.py    # plain int constants
├── download_table.py    # imports token from gui.tokens
└── url_input_panel.py   # imports token from gui.tokens
```

Data flow: phase 03 calls `tokens.set_mode("dark"|"light")` whenever the resolved theme changes. Widgets that build stylesheets at construction time will not auto-refresh — for Tier-1 that is acceptable (status cells re-render on each `_set_status` call which re-reads `token()`). Document that limitation; deeper repaint orchestration is Tier-2.

## Related Code Files

**Create**
- `gui/tokens.py`
- `gui/spacing.py`

**Modify**
- `gui/download_table.py` — replace `STATUS_COLORS` hex literals with token lookups inside `_set_status`; drop the constant dict if no longer referenced externally.
- `gui/url_input_panel.py` — replace `border: 1px solid red;` with f-string using `token("state.error")`.

**Read for context**
- `gui/main_window.py` (phase 03 will wire `set_mode` here)

## Implementation Steps

1. **Create `gui/tokens.py`** with the two palettes. Use exact hex values from researcher-4 §4 of the synthesis. Suggested values (light / dark):
   - `bg.canvas`: `#FFFFFF` / `#0F1115`
   - `bg.surface`: `#F7F8FA` / `#161A21`
   - `bg.subtle`: `#EEF0F4` / `#1C2129`
   - `border.default`: `#E2E5EB` / `#2A2F3A`
   - `border.strong`: `#C7CCD6` / `#3A4150`
   - `text.primary`: `#11151C` / `#E6E9EF`
   - `text.secondary`: `#3A4150` / `#A6ADBB`
   - `text.muted`: `#6B7280` / `#7A8493`
   - `accent.default`: `#4F46E5` / `#6366F1`
   - `accent.hover`: `#4338CA` / `#818CF8`
   - `accent.fg`: `#FFFFFF` / `#FFFFFF`
   - `state.success`: `#16A34A` / `#22C55E`
   - `state.warning`: `#D97706` / `#F59E0B`
   - `state.error`: `#DC2626` / `#EF4444`
   - `state.info`: `#0284C7` / `#38BDF8`

   *(If researcher-4 §4 lists slightly different exact hexes, use those instead — the table above is a fallback if the synthesis section is silent.)*
2. Add module-level mutable `_mode = "light"` plus `set_mode/current_mode/token` functions.
3. **Create `gui/spacing.py`** — seven int constants, one-line module docstring.
4. **Patch `gui/download_table.py`:**
   - Delete the `STATUS_COLORS` dict.
   - Inside `_set_status`, map status → token name once: `{STATUS_COMPLETE: "state.success", STATUS_DOWNLOADING: "state.warning", STATUS_FAILED: "state.error", STATUS_SKIPPED: "text.muted", STATUS_CANCELLED: "text.muted", STATUS_QUEUED: "text.muted"}`. Look up via `token(...)`.
   - Drop the now-unused `from PySide6.QtGui import QColor` if no longer needed elsewhere — keep if referenced.
5. **Patch `gui/url_input_panel.py`:**
   - Replace literal `"border: 1px solid red;"` with `f"border: 1px solid {token('state.error')};"`.
   - Add `from gui.tokens import token`.
6. **Sanity import** all four files: `python -c "from gui import tokens, spacing, download_table, url_input_panel"`.

## Todo List

- [x] Create `gui/tokens.py` (palette + helpers)
- [x] Create `gui/spacing.py` (constants)
- [x] Refactor `gui/download_table.py` status color path to use `token(...)`
- [x] Refactor `gui/url_input_panel.py` error border to use `token('state.error')`
- [x] Verify all four files import cleanly
- [x] Confirm UI renders in source run with default light mode (headless build verified)

## Success Criteria

- Grep for `#[0-9a-fA-F]{6}` inside `gui/` returns only files we explicitly chose not to touch (currently: zero — both call-sites migrated).
- `gui/spacing.py` has all seven constants and is <30 lines.
- `gui/tokens.py` has 15 keys per palette, both palettes, working `token()` helper.
- App still launches and downloads still display status colors (now resolved through tokens).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Token miss (typo in key) raises `KeyError` at runtime | Med | Low | Keep call sites few; add a unit-style assertion in `tokens.py` module that both palettes have identical keys. |
| Stylesheet built at construction time doesn't refresh after `set_mode` | High (by design) | Low for Tier-1 | Accepted limitation; Tier-2 will trigger repaints. Document in tokens.py docstring. |
| Spacing module accidentally imported as `from gui.spacing import *` polluting namespace | Low | Trivial | Underscore-prefix nothing; document the seven public names explicitly. |
| Researcher-4 §4 hex differs from fallback table here | Med | Trivial | Read the synthesis §4 first; fallback table only used if synthesis is silent. |

## Security Considerations

None — pure presentation layer.

## Next Steps

- Phase 03 imports `gui.tokens.set_mode` and calls it from `darkdetect` callback + Settings handler.
- Phase 04 may use `token('accent.default')` to colorize qtawesome icons consistently.
