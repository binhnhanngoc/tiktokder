# Phase 06 — Release process update + version bump

**Priority:** P2 · **Status:** todo · **Effort:** ~30min

## Context Links
- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md) — sections "Release Process Update", "Next Steps"
- SSOT pattern: `docs/release-process.md` — current Manual-Bump Locations (3): `version.py`, `README.md:5`, `docs/project-changelog.md`
- Drift test: `test_version.py` — must keep all three in lockstep

## Overview
Land the documentation and version-bump that ships this feature:
1. Bump 1.9.0 → **1.10.0** (MINOR — new feature, no breaking change)
2. Add `gh release create` step to `docs/release-process.md` (post-tag block)
3. Add changelog entry
4. Mention `update_checker.py` in `docs/system-architecture.md`

## Key Insights
- `gh release create` is **post-tag**: insert a new H2 block between the existing "Tag" and "Pre-Tag Checklist" sections. Order it `Tag` → `GitHub Release` → `Pre-Tag Checklist` (the latter is named "Pre-Tag" but actually lives before the tag step in practice; revisit naming).
- `gh release create vX.Y.Z dist/TikTokDer-portable-X.Y.Z.zip --title "vX.Y.Z" --notes-from-tag` requires the tag to have an annotated message. Existing `git tag vX.Y.Z` is lightweight. **Either** switch the tag command to `git tag -a vX.Y.Z -m "..."` **or** use `--generate-notes` instead of `--notes-from-tag`. Recommend `--generate-notes` (auto-generated notes from PR/commit history) — zero authoring overhead.
- One-time setup `gh auth login` is documented separately so the per-release checklist stays compact.
- The drift test in `test_version.py` already covers `version.py` ↔ `README.md` ↔ changelog — bumping all three together passes it.

## Requirements

**Functional:**
- `version.py:5`: `__version__ = "1.10.0"`
- `README.md:5`: `**v1.10.0** | Python 3.10+ | …` (existing pattern)
- `docs/project-changelog.md`: prepend `## [1.10.0] — 2026-05-04 — In-app update checker` with bullets covering:
  - GitHub Releases API check on startup (24h cached) + Help → Check for Updates…
  - About-tab status pill + Check now button
  - Opt-out checkbox in dialog; Skip-this-version persistence
  - Tag fallback when no GitHub Release published
- `docs/release-process.md`:
  - Add a one-time setup section: `gh auth login --hostname github.com -s repo,read:org`
  - Insert new "Publish GitHub Release" section after "Tag", showing `gh release create vX.Y.Z dist/TikTokDer-portable-X.Y.Z.zip --title "vX.Y.Z" --generate-notes`
  - Update Pre-Tag Checklist to add: `- [ ] Tag is annotated (or use --generate-notes); release published via gh release create`
- `docs/system-architecture.md`: add a one-line entry under modules describing `update_checker.py` (network/release-fetch + version compare; no Qt deps).

**Non-functional:**
- No code changes beyond `version.py`. Pure docs + version bump.
- Drift test must pass.
- `python build.py` must produce `dist/TikTokDer-portable-1.10.0.zip` cleanly.

## Architecture
N/A — docs phase.

## Related Code Files

**Modify:**
- `version.py` — single literal change
- `README.md` — single literal change line 5
- `docs/project-changelog.md` — prepend new entry
- `docs/release-process.md` — add `gh release create` step + one-time setup note
- `docs/system-architecture.md` — add `update_checker.py` mention

**No edits:**
- `test_version.py` — drift test already runs against all three; no test code changes needed

## Implementation Steps

1. Bump `version.py:5` to `__version__ = "1.10.0"`.
2. Bump `README.md:5` to `**v1.10.0**`.
3. Prepend changelog entry to `docs/project-changelog.md` with the bullets in Requirements.
4. Edit `docs/release-process.md`:
   - Add new top-level section "## One-time Setup" near the top (after "## Single Source of Truth" or before "## Build"):
     ```
     ## One-time Setup
     `gh auth login --hostname github.com -s repo,read:org` — needed once per machine for `gh release create`.
     ```
   - Below the existing "## Tag" section, insert "## Publish GitHub Release":
     ```
     gh release create vX.Y.Z dist/TikTokDer-portable-X.Y.Z.zip \
       --title "vX.Y.Z" \
       --generate-notes
     ```
   - Add to "Pre-Tag Checklist": one new bullet about publishing the GitHub Release post-tag.
   - Remove "GitHub Releases auto-upload" from the "Out of Scope (not automated yet)" list — we now publish manually.
5. Edit `docs/system-architecture.md`: add a row/bullet under module list for `update_checker.py` (one-liner: "Stdlib-only HTTP fetch of latest GitHub release; pure logic, no Qt").
6. Run `python -m pytest` — drift test must pass.
7. Run `python main.py --version` → `TikTokDer 1.10.0`.
8. Run `python build.py` — verify it produces `dist/TikTokDer-portable-1.10.0.zip`.
9. Smoke-test built GUI: window title and Help → About both show `v1.10.0`.

## Todo List

- [ ] Bump `version.py`
- [ ] Bump `README.md` line 5
- [ ] Prepend changelog entry
- [ ] Add `gh auth login` one-time setup note in release-process.md
- [ ] Add "Publish GitHub Release" section
- [ ] Update Pre-Tag Checklist
- [ ] Update Out of Scope list (remove the now-shipped item)
- [ ] Add `update_checker.py` to system-architecture
- [ ] `pytest` green (drift test particularly)
- [ ] `python main.py --version` prints `TikTokDer 1.10.0`
- [ ] `python build.py` succeeds; zip filename includes `1.10.0`

## Success Criteria

- All three SSOT locations show `1.10.0`
- `test_version.py` drift test green
- `docs/release-process.md` includes a copy-pasteable `gh release create` command
- Built portable zip has `1.10.0` in filename and EXE properties

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Drift test fails after partial bump | Bump all three in one commit |
| `gh` not installed on dev machine | Phase only documents; actual `gh release create` is run at release time. If `gh` missing, the `/tags` fallback in checker still works for end users |
| `--generate-notes` produces empty notes for first-tag release | First v1.10.0 release will have notes from commits since v1.9.0; non-issue |
| Forgotten `gh release create` after tag push | Tag fallback in `update_checker.py` covers this — users still get notified, with a release-tag URL that exists |

## Security Considerations
- `gh` token stored in user keychain by `gh auth login`. Standard tooling.
- No secrets committed.

## Next Steps
- Tag `v1.10.0` and publish per updated process.
- After landing, archive plan via `/ck:plan archive`.
- Future optimisation paths (Option B: `build.py --release`; Option C: GH Actions on tag push) tracked in brainstorm; out of scope here.
