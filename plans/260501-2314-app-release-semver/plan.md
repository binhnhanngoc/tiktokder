---
title: "App release semver infrastructure"
description: "Single-source version constant wired through GUI title, About dialog, CLI --version, build artifacts, Windows EXE metadata, and docs."
status: completed
priority: P2
effort: 3h
branch: main
tags: [versioning, semver, release, build, infra]
created: 2026-05-01
---

# App Release Semver — Plan Overview

Add semantic versioning infrastructure to TikTokDer at v1.4.0 (no version bump — only plumbing). Establish `version.py` as the single source of truth (SSOT) and wire it through GUI, CLI, build, EXE metadata, and docs. KISS: no packaging system, no helper scripts, no CI automation.

## Goal
Future version bumps require editing exactly **one** literal: `version.py`. README has one acknowledged manual line, documented in the release process.

## Scope (agreed)
- Starting version stays **1.4.0**
- Show version in **GUI title bar AND About dialog**
- **No** pyproject.toml/setup.py
- **No** bump helper scripts, **no** CI release automation, **no** pre-release suffixes

## Phases

| # | Phase | Files Owned | Status |
|---|-------|-------------|--------|
| 01 | [Version SSOT + wireup](phase-01-version-ssot-and-wireup.md) | `version.py` (new), `app.py`, `main.py`, `gui/main_window.py` (title only) | [x] done |
| 02 | [About dialog with version](phase-02-about-dialog.md) | `gui/main_window.py` (`_show_about` only) | [x] done |
| 03 | [Build + spec EXE metadata](phase-03-build-and-spec-version.md) | `build.py`, `tiktokder.spec` | [x] done |
| 04 | [Docs + release process](phase-04-docs-and-release-process.md) | `docs/project-changelog.md`, `docs/release-process.md` (new), `README.md` | [x] done |
| 05 | [Tests](phase-05-tests.md) | `test_version.py` (new) | [x] done |

## Dependency Graph
```
phase-01 (SSOT exists)
   ├─► phase-02 (imports __version__)
   ├─► phase-03 (imports __version__ / __version_info__)
   ├─► phase-04 (references SSOT in docs)
   └─► phase-05 (tests SSOT, CLI --version, drift)
```
phase-02..05 can run in parallel **after** phase-01 lands. No two phases touch the same file in the same region (phase-01 edits window title; phase-02 edits the existing `_show_about` slot — distinct lines).

## Key Constraints
- **KISS**: `version.py` is two lines. `__version_info__` is parsed from `__version__` (DRY).
- **No new packaging**: stays a flat repo. No `setup.py`, no `pyproject.toml`.
- **VSVersionInfo inline**: in `tiktokder.spec`, no separate `version_info.txt` file.
- **README literal**: one manual line at `README.md:5` (`**v1.4.0**`) — acknowledged debt, documented in release-process.md, drift-tested in phase-05.

## Success Criteria (whole plan)
- `python main.py --version` prints `TikTokDer 1.4.0` and exits 0
- GUI window title reads `TikTokDer v1.4.0`
- Help → About shows version 1.4.0
- `python build.py` produces `dist/TikTokDer-portable-1.4.0.zip`
- Right-click on built `TikTokDer.exe` → Properties → Details shows v1.4.0
- All tests in `test_version.py` pass
- `docs/release-process.md` exists; bump checklist references only `version.py` + `README.md` line + changelog

## Rollback
Each phase is a small, isolated commit. Revert any phase independently with `git revert`. No data migrations, no schema changes, no user-facing breakage if reverted.

## Out of Scope (YAGNI)
pyproject.toml; bump-version helper; CI/CD release automation; pre-release suffixes (-rc, -beta); checksums/signing; auto-generated release notes.
