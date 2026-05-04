---
title: "In-App Update Checker"
description: "Notify-only GitHub-Releases-API update checker (background + manual + About-tab pill). Stdlib only, ~280 LOC, no self-update."
status: completed
priority: P2
effort: 4-6h
branch: main
tags: [gui, networking, releases, ux]
created: 2026-05-04
blockedBy: []
blocks: []
---

# In-App Update Checker — Plan Overview

Add a lightweight "check for updates" feature to TikTokDer GUI. Background-checks once per 24h on startup, plus manual `Help → Check for Updates…` and an About-tab status pill. **Notify only** — no self-update, no in-app download. Polls GitHub Releases API with a `/tags` fallback for unsigned-release safety net.

## Source

- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md)
- All design decisions confirmed; no open questions at planning time.

## Goal

Users learn about new versions inside the app within 24h of publish, without TikTokDer ever modifying its own files. Manual menu always works regardless of opt-out / cache / skip state.

## Scope

- ✅ GUI only (CLI users `git pull`)
- ✅ GitHub Releases API + `/tags` fallback
- ✅ 24h cache, opt-out checkbox (default ON), Skip-this-version
- ✅ About-tab pill + "Check now" button
- ✅ `gh release create` post-tag step in `docs/release-process.md`
- ❌ Self-replace EXE / in-app ZIP download / progress bar
- ❌ CLI integration / pre-release channel / update history log
- ❌ Code signing (separate concern)

## Phases

| # | Phase | Files Owned | Status |
|---|-------|-------------|--------|
| 01 | [update_checker core module](phase-01-update-checker-core.md) | `update_checker.py` (new), `test_update_checker.py` (new) | [x] done |
| 02 | [config persistence fields](phase-02-config-fields.md) | `config.py`, `test_config.py` | [x] done |
| 03 | [UpdateAvailableDialog](phase-03-update-dialog.md) | `gui/update_dialog.py` (new), `test_update_dialog.py` (new) | [x] done |
| 04 | [MainWindow wiring + worker](phase-04-main-window-wiring.md) | `gui/main_window.py` | [x] done |
| 05 | [About-tab pill + Check now](phase-05-about-tab-pill.md) | `gui/help_dialog.py`, `gui/help_content.py`, `gui/about_panel.py` (new), `test_about_panel.py` (new) | [x] done |
| 06 | [Release process + version bump](phase-06-release-and-version.md) | `docs/release-process.md`, `version.py`, `README.md`, `docs/project-changelog.md`, `docs/system-architecture.md` | [x] done |

## Dependency Graph

```
phase-01 (logic)  ─┐
                   ├─► phase-03 (dialog uses ReleaseInfo)
phase-02 (config) ─┤                    │
                   └─► phase-04 (worker + startup) ─► phase-05 (pill reads cached ReleaseInfo)
                                                           │
                                                           └─► phase-06 (docs + bump)
```

phase-01 and phase-02 are independent — can run in parallel. phase-03 depends on phase-01 (imports `ReleaseInfo`). phase-04 depends on phase-01, 02, 03. phase-05 depends on phase-04 (reads `MainWindow._latest_release_cache`). phase-06 must come last (version bump triggers smoke-tests).

## Key Constraints

- **Stdlib only** — `urllib.request`, `json`, `re`, `time`, `dataclasses`. No new pip deps.
- **Threading** — HTTP off main thread; `QThread` worker emits `ReleaseInfo | None` signal.
- **File-size cap** — every new file < 200 LOC (CLAUDE.md rule). `update_checker.py` ~120, `gui/update_dialog.py` ~90.
- **Silent in background** — net failure never surfaces unless user invoked manual check.
- **Tag fallback** — `/releases/latest` → 404 → `/tags?per_page=10` → regex `^v\d+\.\d+\.\d+$` → highest tuple wins.
- **Dedup gates** — `should_check_now`, `skipped_update_version`, `update_check_enabled` only apply to background path; manual path bypasses all three.

## Success Criteria (whole plan)

- [ ] App startup never blocks > 100ms on the update path (network is off main thread).
- [ ] `Help → Check for Updates…` always shows an outcome (newer / up-to-date / net error).
- [ ] Background check fires at most once per 24h per launch; respects opt-out and skip-version.
- [ ] Network failure silent in background; clear `QMessageBox.warning` in manual mode.
- [ ] Skip-version persists; opt-out persists; manual check works after opt-out.
- [ ] About-tab pill reflects state on open; updates live after manual check.
- [ ] Works without published GitHub Release (tag fallback exercised by current repo state).
- [ ] No new entries in `requirements.txt`.
- [ ] `python -m pytest` passes; new tests cover version compare, cache gate, tag-list filtering, network-failure paths (mocked).
- [ ] `docs/release-process.md` includes `gh release create` step.
- [ ] Version bumped to **1.10.0**; drift test passes.

## Risks & Mitigations (carry-over from brainstorm)

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| GitHub Release not published yet → 404 | High at first | `/tags` fallback in checker |
| Offline / firewall blocks api.github.com | Medium | Silent fail in background; clear msg in manual |
| Pre-release tag picked up by `/tags` | Low | Regex `^v\d+\.\d+\.\d+$` excludes `-rc`, `-beta` |
| Source build with newer `__version__` than published | Low | Tuple compare returns `False` → silent |
| Modal dialog jars first-launch flow | Low | 2000ms `QTimer.singleShot` after `show()` |
| Worker emits result after `MainWindow` teardown | Low | Already handled pattern: `QThreadPool.waitForDone(2000)` in `closeEvent` (precedent: `_HealthWorker`) |

## Rollback

Each phase a small isolated commit. Revert any phase with `git revert`. No data migrations. Reverting phase-02 leaves three unused config fields — harmless because `load_config()` filters unknown keys. Reverting phase-04 fully disables the feature; the module + dialog become dead code until pruned.

## Out of Scope (YAGNI)

Self-replacing EXE; in-app ZIP download with progress bar; CLI `--check-update` flag / banner; pre-release / beta channel toggle; update history log; delta/patch updates; code signing; auto-generated release notes from commits.
