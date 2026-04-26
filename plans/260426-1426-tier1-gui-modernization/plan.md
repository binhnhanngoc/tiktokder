---
title: "Tier-1 GUI modernization (PySide6 theming + tokens + icons)"
description: "Disable UPX, add pyqtdarktheme/qtawesome/darkdetect, semantic tokens, spacing constants, icon helper."
status: pending
priority: P2
effort: ~1.5d
branch: main
tags: [gui, theming, pyside6, packaging, ux]
created: 2026-04-26
---

## Overview

Apply Tier-1 of the modern-Python-GUI synthesis (`plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` §8) to tiktokder. Stay on PySide6. Add MIT-licensed theming (pyqtdarktheme + qtawesome + darkdetect), semantic color tokens, spacing constants, OS-follow dark/light theme with Settings override, and a single qtawesome-based icon set. Disable UPX in PyInstaller spec to reduce AV false-positives.

**In scope:** UPX-off, deps, tokens, spacing, theme bootstrap + listener + Settings control, icon helper, manual UI walkthrough, rebuild smoke test.
**Out of scope (Tier-2/3):** InfoBar/toast, empty state, skeleton rows, focus rings, tray icon, drag-and-drop, geometry persistence beyond what already exists, QFluentWidgets, Inno Setup, Azure signing.

## Phases

| # | File | Status | Owner | Depends on |
|---|---|---|---|---|
| 01 | [phase-01-spec-and-deps.md](phase-01-spec-and-deps.md) | pending | — | — |
| 02 | [phase-02-tokens-and-spacing.md](phase-02-tokens-and-spacing.md) | pending | — | 01 |
| 03 | [phase-03-theme-bootstrap.md](phase-03-theme-bootstrap.md) | pending | — | 01, 02 |
| 04 | [phase-04-iconography.md](phase-04-iconography.md) | pending | — | 01 |
| 05 | [phase-05-validation.md](phase-05-validation.md) | pending | — | 01–04 |

Phase 02 and 04 can run in parallel after 01 completes (different files). Phase 03 reads tokens from 02. Phase 05 is the final gate.

## Key dependencies

- pyqtdarktheme (MIT), qtawesome (MIT), darkdetect (BSD-3) — added in phase 01.
- Existing `config.AppConfig` extended with one new field (`theme_mode: "system"|"light"|"dark"`) in phase 03.
- `tiktokder.spec` edited once in phase 01 (UPX off + hidden imports), no further spec changes.

## Hard constraints

- KISS / YAGNI / DRY. No abstractions beyond what each phase needs.
- No backwards-compat shims for theme changes — overwrite hex usage directly.
- Files <200 lines after edits where practical.
- All new code under `gui/` package.

## Success criteria (rolled up)

- App launches in source + frozen build, follows OS theme on first run.
- Settings → Appearance segmented control (System/Light/Dark) persists across restart.
- No raw status hex literals remain in `gui/download_table.py`.
- All toolbar/status icons render via `gui.icons.icon(...)`; no emoji or `QIcon.fromTheme`.
- Bundle size delta documented; build still launches.
