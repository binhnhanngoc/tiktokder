# Code Review — App Release SemVer (v1.4.0)

**Date:** 2026-05-01
**Reviewer:** code-reviewer (adversarial)
**Branch:** main (HEAD = 36c2822, working tree dirty)
**Tests:** 394 passed locally (`pytest -q`)
**Plan:** `plans/260501-2314-app-release-semver/`

---

## Verdict

Implementation is solid: SSOT via `version.py`, fail-loud regex guard, no circular import risk, drift tests cover the three manual-bump locations, and Windows VERSIONINFO magic constants are correct (`mask=0x3F`, `OS=0x40004 NT_WINDOWS32`, `fileType=0x1 VFT_APP`, `subtype=0x0` is required for VFT_APP). All 394 tests green.

Two real bugs to fix before commit, one drift-test gap that will bite a future release, and a handful of MINOR/NIT items.

---

## CRITICAL

### C1. Changelog [1.4.0] re-claims [1.3.1] feature — duplicate content

`docs/project-changelog.md`:

- Line 16 (under `[1.4.0]`):
  `- **Library**: filter row (Quality / Date range / Size / Status) + sortable columns by header click.`
- Line 30 (under `[1.3.1]`):
  `- **Library**: All columns now sortable by header click (Size sorts by raw bytes, default Date desc)`
  `- **Library**: Added compact filter row — Quality dropdown, Date range (From/To)…`

Cross-reference with `git log`: commit `36c2822 feat(library): sortable columns + filter row, fix Title resize` is the SAME commit that introduced the `[1.3.1]` changelog entry (verified via `git show 36c2822 -- docs/project-changelog.md`). That feature shipped under 1.3.1, so listing it again under 1.4.0 is incorrect attribution.

**Fix:** Remove line 16 from the `[1.4.0]` block. Keep only the genuinely 1.4.0-new items: thumbnails always-on + preview pane (line 15), TikTok cookies parity (17), Facebook page-name folders (18), QSS progress bar polish (19), versioning infra (20), rapid-profile-switch fix (23).

### C2. Drift test will not catch `v`-prefix or pre-release suffix in changelog

`test_changelog_latest_matches_ssot` regex: `^##\s*\[(\d+\.\d+\.\d+)\]`

Verified failure modes (run experiment, all return `NO MATCH`):
- `## [v1.4.0]` → no match → test reports "no version heading found" rather than reporting a drift.
- `### [1.4.0]` → no match → same.
- `## [1.4.0-rc.1]` → no match → would silently fall through to whatever `[1.4.0]` heading is next, masking actual release-candidate drift.

Mitigation: the user explicitly out-of-scoped pre-release suffixes, so `-rc` is acceptable. But `v` prefix and `###` reformat are realistic typos a future contributor will make. Tighten regex OR add a sanity assertion that at least one `## [...]` heading exists; currently absent, only assert match-or-no-match.

**Fix (recommended):** Loosen the regex to `^#{2,3}\s*\[v?(\d+\.\d+\.\d+)\]` and keep the rest. Pre-release suffixes remain rejected, which is the documented stance.

---

## MAJOR

### M1. `version.py` regex accepts leading zeros

`re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", "01.4.0")` → matches, parses to `(1, 4, 0)`. SemVer 2.0.0 §2 explicitly forbids leading zeros in numeric identifiers. The `int()` cast silently fixes it at runtime, but `__version__` (the user-visible string) still says `"01.4.0"` and would propagate to window title, About dialog, EXE metadata, and zip filename.

**Fix:** Use `r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"` per SemVer spec, or add a separate assertion `assert str(__version_info__[0]) == _match.group(1)` etc. to catch leading-zero drift.

### M2. `tiktokder.spec` import depends on PyInstaller invocation CWD

Line 22: `from version import __version_info__`. PyInstaller `exec()`s the spec file with the spec's directory NOT automatically on `sys.path` — only the original CWD is. Today this works because `build.py` runs `subprocess.run([..., spec_file, ...])` inheriting `cwd=ROOT`, so `ROOT` is on `sys.path` and `version.py` resolves.

Brittle case: a contributor running `pyinstaller tiktokder.spec` manually from a sibling directory (e.g., `cd /tmp; pyinstaller /repo/tiktokder.spec`) → `ImportError: No module named version`. The error surfaces inside PyInstaller, not from `python build.py`, which makes diagnosis harder.

**Fix:** Add a defensive `sys.path` insertion at the top of the spec, before the import:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(SPEC)))
from version import __version_info__
```
PyInstaller injects `SPEC` as a global into spec files; this guarantees the spec's directory is importable regardless of caller CWD.

### M3. `test_cli_version_flag` 15s timeout vs cold yt-dlp import on Windows

`main.py` imports `yt_dlp` (transitively through `downloader`) and `rich` at module top, before argparse runs. On a cold Python interpreter on Windows with antivirus scanning site-packages, yt-dlp's >100-module import has been measured at 3–8s. 15s is adequate for a developer machine but could flake on a slow CI runner or after a fresh `pip install`. Symptom would be `subprocess.TimeoutExpired` rather than a clear assertion message.

**Fix (cheap):** bump to 30s. **Fix (proper):** move heavy imports inside `main()` so `--version` is sub-second. The user's plan called this out as out-of-scope; flagging here so the constraint is acknowledged in writing.

---

## MINOR

### m1. README has TWO `1.4.0` literals; drift test only enforces line 5

`README.md:5` — current-version badge (enforced).
`README.md:111` — historical reference: `_The toggle was removed in v1.4.0._`

Line 111 is a milestone reference and SHOULD remain `v1.4.0` even after bumping to 1.5.0. So this is correct behavior — but the release-process doc says "manual-bump locations (3)" and lists README line 5 as one. Worth noting in `docs/release-process.md` that *historical* version references in body text are intentionally not bumped, to avoid future contributors scrubbing them.

### m2. `gui/settings_panel.py:126` historical comment

`# Subtitles toggle. Thumbnails were promoted to always-on in v1.4.0`

Same category as m1 — code-comment milestone reference. Won't drift, intentionally pinned. Mention in release-process doc as "historical refs are exempt".

### m3. `OriginalFilename` is `TikTokDer.exe` for both GUI and CLI EXE

Spec lines 48 (GUI) and 186 (CLI both use `_build_version_info()`). The CLI's `OriginalFilename` will read `TikTokDer.exe` in Properties → Details, even though the file on disk is `TikTokDer-CLI.exe`. Microsoft's spec says `OriginalFilename` "identifies the original name of the file, not including a path. This information enables an application to determine whether a file has been renamed by a user."

Cosmetic, but would mildly confuse a forensic analyst. Either parameterize `_build_version_info(name="TikTokDer.exe")` or accept as deliberate (both EXEs are halves of one product). Plan documented this as "defensible" — agreed; flagging only because it's the specific question asked.

### m4. `__version_info__` type annotation correctness

```python
__version_info__: tuple[int, int, int] = tuple(int(p) for p in _match.groups())  # type: ignore[assignment]
```

Runtime confirmed: `tuple` of 3 `int`. The `type: ignore[assignment]` is needed because `tuple(generator)` is inferred as `tuple[int, ...]` (variadic). Cleaner pattern that avoids the ignore:
```python
_parts = _match.groups()
__version_info__: tuple[int, int, int] = (int(_parts[0]), int(_parts[1]), int(_parts[2]))
```
YAGNI says leave it — `# type: ignore` is fine. Just noting an alternative if the user wants to drop the directive.

### m5. Old unversioned zip will be silently deleted on next `build.py` run

`dist/TikTokDer-portable.zip` (Apr 27, 420 MB) currently sits in `dist/`. `build.py` runs `shutil.rmtree(dist)` before each build, so it'll vanish along with the old `dist/TikTokDer/` folder. That's the desired hygiene, but a user who's been hand-archiving the 1.3.x zip for safekeeping would lose it. Worth a one-line note in `docs/release-process.md` Build section: "previous unversioned/versioned zips in `dist/` are deleted on rebuild — copy out manually if you need to keep them."

---

## NIT

### n1. `test_readme_version_matches_ssot` 20-line window

Asked: "is 20 too aggressive or too lax?" — Today the badge sits on line 5. 20 lines gives a 4× safety margin. If a future README rewrite adds badges/intros pushing it past line 20, the test fails fast with a clear message. **20 is correct** — wide enough to absorb minor rearrangement, narrow enough to catch a moved-to-bottom badge. No change.

### n2. About dialog HTML — Qt theme rendering

`<h3>`, `<p>`, `<small>`, `&amp;`, `&mdash;` are all standard Qt rich-text supported subset. `QMessageBox.about` uses `QLabel` with Qt's HTML subset (per docs/richtext-html-subset). All entities and tags used here are in the supported set across Qt 5/6 + light/dark themes. **No issue.**

### n3. Idempotency / re-runs of `python build.py`

`shutil.rmtree(build); shutil.rmtree(dist)` at top → each run starts clean. Re-running with the same version overwrites cleanly. No locking risk because PyInstaller doesn't hold filesystem handles after exit. **No issue.**

---

## YAGNI Check (asked in prompt)

`__version_info__` parsing: **kept**, used in `tiktokder.spec` for `FixedFileInfo.filevers=(major, minor, patch, 0)`. Not speculative. ✓

Regex guard in `version.py`: **kept**, fails loud at import. Not speculative. ✓

No other speculative additions detected.

---

## Security Check (asked in prompt)

`__version__` is a static literal in `version.py` with regex-validated character set `[0-9.]`. There is NO path for user-controllable input to reach the version string display (window title, About dialog HTML, CLI output, EXE metadata, zip filename). Fail-loud import-time guard prevents shipping malformed values. **No injection risk.** ✓

---

## Recommended Action Order

1. **Fix C1** — drop the duplicated Library bullet from `[1.4.0]` changelog entry.
2. **Fix C2** — loosen changelog regex to accept `### [` and `[v` prefix; keep pre-release rejection.
3. **Fix M1** — tighten version regex to disallow leading zeros (one-line change).
4. **Fix M2** — add `sys.path.insert(0, os.path.dirname(SPEC))` in `tiktokder.spec` before `from version import …`.
5. Bump `test_cli_version_flag` timeout 15s → 30s (M3 cheap fix).
6. (Optional) Add release-process note about historical version refs (m1, m2) and dist hygiene (m5).

After fixes, re-run `pytest -q` (should still be 394 green) and one manual `python build.py` smoke-test to confirm the spec import path defensiveness.

---

## Unresolved Questions

- Should the [1.4.0] changelog also call out the working-tree-uncommitted feature surfaces (library_preview_pane, library_thumbnail_delegate, the download_engine/downloader/history_store/settings_panel mods)? They are listed via "thumbnails always-on + right-side preview pane" but the engine/downloader changes are invisible. Not a SemVer-infra concern, but the release commit will include them — confirm intent.
- Will `36c2822` be force-amended to fold in the SemVer infra, or will a new commit `release: v1.4.0` chain on top? `docs/release-process.md` documents the latter; current uncommitted state is consistent with that — confirm.
- Pre-release suffix support (`-rc`, `-beta`) explicitly out of scope per prompt — accepted; flagging that this also means the changelog regex is intentionally strict on three-part SemVer only.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** SemVer wiring is correctly implemented end-to-end and all 394 tests pass; two real defects to fix before commit (changelog content duplication of 1.3.1 features under 1.4.0, and changelog regex won't survive `v`-prefix or `###` reformat) plus a SemVer-spec violation (regex accepts leading zeros) and a spec-file CWD fragility worth defending against.
**Concerns/Blockers:** C1 is a content/correctness bug in the user-visible changelog; C2 will fail open in a future release. Both should be fixed before tagging v1.4.0.
