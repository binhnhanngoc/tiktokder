# Phase 04 — Docs + release process

## Context Links
- Plan overview: `plan.md`
- Blocker: `phase-01-version-ssot-and-wireup.md`
- Existing files: `docs/project-changelog.md` (last entry `[1.3.1] — 2026-04-27`), `README.md:5` (literal `**v1.4.0**`)

## Overview
- **Priority:** P2
- **Status:** pending
- **Description:** Document the SemVer policy, add a `[1.4.0]` changelog entry covering both retroactive 1.4.0 work and the new versioning infrastructure, create a concise release-process doc, and annotate the README literal as manually maintained.

## Key Insights
- Changelog drift exists: `README.md` says v1.4.0 but `docs/project-changelog.md` last entry is 1.3.1. We close that gap with a retroactive `[1.4.0]` entry.
- Recent post-1.3.1 git log shows: sortable library columns (already in 1.3.1 entry actually — check), library thumbnails always-on, library preview pane + descriptions, TikTok cookies parity, polished progress bar, hang-on-rapid-profile-switch fix, page-name folders for Facebook. These are the 1.4.0 contents.
- README's `**v1.4.0**` literal is acknowledged tech debt — listed in the release checklist as one of two manual-bump locations alongside `version.py`.
- `docs/release-process.md` is NEW — keep under 50 lines.

## Requirements
**Functional**
- `docs/project-changelog.md` gains a "Versioning Policy" preamble (above the `## [1.3.1]` heading) explaining MAJOR/MINOR/PATCH semantics and bump triggers.
- Same file gains a `## [1.4.0] — 2026-05-01` entry covering: versioning infrastructure (this plan) + retroactive features shipped at 1.4.0 (library thumbnails always-on, library preview pane + descriptions, sortable library columns + filter row, TikTok cookies parity, polished progress bar, profile-switch hang fix, Facebook page-name folders).
- `docs/release-process.md` exists with: SemVer rules, bump location list, build commands, git tag commands, release checklist.
- `README.md:5` literal `**v1.4.0**` keeps current value but the release-process doc explicitly calls it out as a manual-bump location.

**Non-functional**
- `docs/release-process.md` ≤ 50 lines.
- Changelog preamble ≤ 25 lines.
- No formatting break in existing changelog entries.

## Architecture
```
docs/project-changelog.md
   ├─ [NEW] Versioning Policy (preamble)
   ├─ [NEW] [1.4.0] — 2026-05-01
   ├─ [1.3.1] — 2026-04-27 (existing)
   └─ [1.3.0] — 2026-04-26 (existing)

docs/release-process.md (NEW)
   ├─ SemVer rules
   ├─ Bump locations (version.py + README.md:5 + changelog)
   ├─ Build commands
   ├─ Git tag command
   └─ Pre-tag checklist

README.md:5 — unchanged literal **v1.4.0**, documented as manual
```

## Related Code Files
**Create**
- `docs/release-process.md`

**Modify**
- `docs/project-changelog.md` (prepend preamble + new entry; existing entries untouched)

**Untouched**
- `README.md` — literal stays at v1.4.0 for now; manual-bump status documented in release-process.md

## Implementation Steps
1. Edit `docs/project-changelog.md`:
   - Insert below the `# Project Changelog` H1, above the `## [1.3.1]` heading:
     ```markdown
     ## Versioning Policy

     TikTokDer follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):
     - **MAJOR** — breaking changes to CLI flags, config schema, history/state file format, or data folder layout.
     - **MINOR** — new features, additive config keys, new GUI panels (backwards compatible).
     - **PATCH** — bug fixes, dependency bumps, doc-only changes, performance tweaks (no UX or data changes).

     The single source of truth is `version.py` (`__version__`). The README badge line and the latest changelog entry below must match it on every release. See `docs/release-process.md` for the bump checklist.
     ```
   - Insert immediately above the `## [1.3.1]` heading (and below the new policy block):
     ```markdown
     ## [1.4.0] — 2026-05-01 — Library polish, cookies parity, versioning infra

     ### Added
     - **Library**: thumbnails always-on (sidecars next to videos) + right-side preview pane with metadata and full description.
     - **Library**: filter row (Quality / Date range / Size / Status) + sortable columns by header click.
     - **Cookies**: TikTok `cookies.txt` parity with Facebook (per-platform cookie file paths).
     - **Channels**: Facebook downloads use page-name folders (per-channel browse cache).
     - **GUI**: progress bar styled with token-aware QSS.
     - **Versioning infrastructure**: `version.py` SSOT wired through GUI title bar, About dialog, CLI `--version`, build artifact filename, and Windows EXE metadata. New `docs/release-process.md`.

     ### Fixed
     - **GUI**: rapid profile switch no longer hangs the window.

     ### Notes
     - No data-format changes; no breaking config changes. Forward-compatible with 1.3.x state files.
     ```
2. Create `docs/release-process.md`:
   ```markdown
   # Release Process

   TikTokDer follows [SemVer](https://semver.org/): MAJOR.MINOR.PATCH (see `docs/project-changelog.md` "Versioning Policy" for triggers).

   ## Single Source of Truth
   `version.py` — `__version__` is the only digit-bearing literal that matters. `__version_info__` is parsed from it.

   ## Manual-Bump Locations (3)
   On every release, update these together:
   1. `version.py` — `__version__ = "X.Y.Z"`
   2. `README.md` line 5 — `**vX.Y.Z**` (intentionally manual; one literal, well-commented in release process)
   3. `docs/project-changelog.md` — prepend new `## [X.Y.Z] — YYYY-MM-DD — short headline` entry

   ## Build
   ```
   python build.py
   ```
   Produces `dist/TikTokDer-portable-X.Y.Z.zip`. The Windows EXE inside has `VSVersionInfo` baked in (right-click → Properties → Details).

   ## Tag
   ```
   git add version.py README.md docs/project-changelog.md
   git commit -m "release: vX.Y.Z"
   git tag vX.Y.Z
   git push && git push --tags
   ```

   ## Pre-Tag Checklist
   - [ ] `version.py`, `README.md`, changelog all show same `X.Y.Z`
   - [ ] `python -m pytest` passes
   - [ ] `python main.py --version` prints `TikTokDer X.Y.Z`
   - [ ] `python build.py` succeeds; zip filename includes `X.Y.Z`
   - [ ] Smoke-test built GUI: window title, Help → About both show `vX.Y.Z`
   - [ ] Windows EXE Properties → Details shows `X.Y.Z`

   ## Out of Scope (not automated yet)
   - Code-signing the EXEs
   - GitHub Releases auto-upload
   - Pre-release suffixes (`-rc`, `-beta`)
   - Auto-generated release notes from commits
   ```

3. Confirm no edits to `README.md` are required this phase (the literal already matches `1.4.0`).

## Todo List
- [ ] Prepend "Versioning Policy" preamble to `docs/project-changelog.md`
- [ ] Insert `[1.4.0] — 2026-05-01` changelog entry above `[1.3.1]`
- [ ] Create `docs/release-process.md` (≤ 50 lines)
- [ ] Verify `README.md:5` still reads `**v1.4.0**` (no edit needed this release)
- [ ] Lint: changelog renders in any Markdown viewer without warnings

## Success Criteria
- Changelog shows three entries (1.4.0, 1.3.1, 1.3.0) plus policy preamble.
- `docs/release-process.md` exists and lists exactly 3 manual-bump locations.
- Drift test in phase-05 passes (README literal == changelog latest == `version.__version__`).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Retroactive 1.4.0 changelog misses a feature | Medium | Low | Cross-reference recent git log + README features list during drafting |
| Future contributor forgets one of the 3 manual-bump locations | Medium | Medium | Drift test (phase-05) + explicit checklist in release-process.md |
| README hardcoded version drifts again next release | Medium | Low | Drift test catches it pre-merge; checklist reminds on bump |

## Security Considerations
None — documentation only.

## Next Steps
Phase 05 (tests) enforces the drift invariant codified here.
