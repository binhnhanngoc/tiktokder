# Phase 05 — Tests

## Context Links
- Plan overview: `plan.md`
- Blockers: phase-01 (SSOT), phase-04 (changelog/README drift target)
- Test infra: existing `test_*.py` files at repo root (pytest), e.g. `test_config.py`, `test_download_engine.py`

## Overview
- **Priority:** P2
- **Status:** pending
- **Description:** Add `test_version.py` covering: SSOT format/parse, CLI `--version` invocation, drift between SSOT / README / changelog. No GUI tests.

## Key Insights
- argparse `action="version"` writes to **stdout** (not stderr) and exits 0 — subprocess capture is straightforward.
- `sys.executable` ensures the test uses the same interpreter as pytest (works in venv, on CI, on contributor machines).
- Drift test parses README and changelog with simple regex — no Markdown library dependency.
- About dialog test deliberately **skipped** — Qt-based UI test would need offscreen platform plugin and `QtTest`; YAGNI for v1.4.0. Manual smoke-test in release checklist (phase-04) covers it.

## Requirements
**Functional**
- `test_version.py` contains 5 tests:
  1. `test_version_string_format` — `__version__` matches `^\d+\.\d+\.\d+$`.
  2. `test_version_info_tuple` — `__version_info__` is a 3-tuple of ints; equals parsed `__version__`.
  3. `test_cli_version_flag` — `subprocess.run([sys.executable, "main.py", "--version"])` exits 0, stdout starts with `TikTokDer ` followed by `__version__`.
  4. `test_readme_version_matches_ssot` — first 20 lines of `README.md` contain `**v{__version__}**`.
  5. `test_changelog_latest_matches_ssot` — first `## [X.Y.Z]` heading in `docs/project-changelog.md` (skipping the `## Versioning Policy` preamble) has `X.Y.Z == __version__`.

**Non-functional**
- All tests pass without spawning Qt or GUI.
- Test file ≤ 80 lines.
- Tests use only stdlib + pytest (no new deps).

## Architecture
```
test_version.py
  ├─ imports: re, sys, subprocess, pathlib
  ├─ imports: version (__version__, __version_info__)
  ├─ test_version_string_format         (pure)
  ├─ test_version_info_tuple            (pure)
  ├─ test_cli_version_flag              (subprocess)
  ├─ test_readme_version_matches_ssot   (file read + regex)
  └─ test_changelog_latest_matches_ssot (file read + regex)
```

## Related Code Files
**Create**
- `test_version.py`

**Read-only references**
- `version.py`, `main.py`, `README.md`, `docs/project-changelog.md`

## Implementation Steps
1. Create `test_version.py` with the 5 tests outlined above. Sketch:
   ```python
   """Version SSOT and drift tests."""
   import re
   import subprocess
   import sys
   from pathlib import Path

   from version import __version__, __version_info__

   ROOT = Path(__file__).resolve().parent

   def test_version_string_format():
       assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__

   def test_version_info_tuple():
       parts = tuple(int(p) for p in __version__.split("."))
       assert __version_info__ == parts
       assert all(isinstance(p, int) for p in __version_info__)
       assert len(__version_info__) == 3

   def test_cli_version_flag():
       result = subprocess.run(
           [sys.executable, str(ROOT / "main.py"), "--version"],
           capture_output=True, text=True, timeout=15,
       )
       assert result.returncode == 0, result.stderr
       # argparse writes version to stdout (Python 3.4+)
       assert result.stdout.strip() == f"TikTokDer {__version__}"

   def test_readme_version_matches_ssot():
       text = (ROOT / "README.md").read_text(encoding="utf-8")
       head = "\n".join(text.splitlines()[:20])
       assert f"**v{__version__}**" in head, "README.md badge does not match version.py"

   def test_changelog_latest_matches_ssot():
       text = (ROOT / "docs" / "project-changelog.md").read_text(encoding="utf-8")
       # First "## [X.Y.Z]" heading wins; skip "## Versioning Policy" preamble.
       match = re.search(r"^##\s*\[(\d+\.\d+\.\d+)\]", text, flags=re.MULTILINE)
       assert match, "no version heading found in changelog"
       assert match.group(1) == __version__, (
           f"latest changelog entry {match.group(1)} != version.py {__version__}"
       )
   ```
2. Run tests: `python -m pytest test_version.py -v`. All 5 must pass.
3. Run full suite: `python -m pytest` to confirm no regressions.

## Todo List
- [ ] Create `test_version.py` (≤ 80 lines, 5 tests)
- [ ] `pytest test_version.py` — all pass
- [ ] `pytest` (full suite) — no regressions

## Success Criteria
- `python -m pytest test_version.py` exits 0.
- All 5 tests pass.
- Test file does not import any GUI module.
- No new test dependencies in `requirements.txt` (or test-deps file).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `main.py --version` requires deps not in test env | Low | Medium | argparse + version flag exits before importing yt-dlp/rich heavy deps; if it fails, refactor `main.py` to register `--version` before other imports |
| Subprocess test slow on Windows (process startup) | Medium | Low | 15s timeout, single invocation — acceptable |
| Changelog regex matches wrong heading after future edits | Low | Low | Anchored `^##\s*\[` is strict; preamble uses `## Versioning Policy` (no brackets) |
| README literal moved to a different line in future | Low | Low | Test scans first 20 lines, not exact line — covers minor reflows |

## Security Considerations
- Subprocess invocation uses `sys.executable` (same interpreter) and a fixed file path — no shell injection vector.

## Next Steps
None — terminal phase. After this lands, the plan is complete and v1.4.0 ships with full versioning infrastructure.
