# Phase 01 — Version SSOT + Wireup

## Context Links
- Plan overview: `plan.md`
- Files verified: `app.py:27` (setApplicationName), `gui/main_window.py:68` (setWindowTitle), `main.py:15-29` (parse_args)

## Overview
- **Priority:** P2 (blocks all other phases)
- **Status:** pending
- **Description:** Create `version.py` SSOT and wire `__version__` into the three runtime touchpoints that affect end users: Qt application metadata, main-window title, and CLI `--version` flag.

## Key Insights
- `app.py` already calls `app.setApplicationName("TikTokDer")` — adding `setApplicationVersion(__version__)` is a one-line addition right after.
- `gui/main_window.py:68` currently sets `self.setWindowTitle("TikTokDer")` — change to f-string with version.
- `main.py:15` builds an `argparse.ArgumentParser` — argparse's built-in `action="version"` exits cleanly with stdout, no GUI side effects, safe to test via subprocess.
- `__version_info__` MUST be parsed from `__version__` at import time (DRY — never duplicate the digits).

## Requirements
**Functional**
- `version.py` exports `__version__: str` and `__version_info__: tuple[int, int, int]`.
- `__version_info__` derives from `__version__` via parsing — no double-source.
- Importing `version` raises `ValueError` if `__version__` doesn't match `^\d+\.\d+\.\d+$` (fail loud at import time).
- GUI window title becomes `TikTokDer v{__version__}`.
- Qt `QApplication.applicationVersion()` returns `__version__`.
- `python main.py --version` prints `TikTokDer 1.4.0` to stdout and exits 0.

**Non-functional**
- Zero new dependencies.
- Import cost: <1ms (regex parse of one string).

## Architecture
```
version.py  ──────► app.py            (setApplicationVersion)
            ──────► gui/main_window.py (setWindowTitle)
            ──────► main.py           (argparse --version)
            ──────► [phase 02] gui/main_window.py (_show_about)
            ──────► [phase 03] build.py + tiktokder.spec
            ──────► [phase 05] test_version.py
```
Single import direction — `version` never imports anything project-internal. No circulars possible.

## Related Code Files
**Create**
- `version.py`

**Modify**
- `app.py` (add 1 import + 1 line after `setApplicationName`)
- `gui/main_window.py` (line 68 — change `setWindowTitle` literal)
- `main.py` (add 1 import + 1 `add_argument`)

**Delete**
- None

## Implementation Steps
1. Create `version.py` with content:
   ```python
   """Single source of truth for TikTokDer version. Bump this string only."""
   import re

   __version__ = "1.4.0"

   _match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", __version__)
   if _match is None:
       raise ValueError(f"version.py: __version__={__version__!r} is not MAJOR.MINOR.PATCH")
   __version_info__: tuple[int, int, int] = tuple(int(p) for p in _match.groups())  # type: ignore[assignment]
   ```
2. Edit `app.py`:
   - Add `from version import __version__` near the other imports.
   - After `app.setApplicationName("TikTokDer")` (line 27), add `app.setApplicationVersion(__version__)`.
3. Edit `gui/main_window.py`:
   - Add `from version import __version__` near other imports.
   - Change line 68 from `self.setWindowTitle("TikTokDer")` → `self.setWindowTitle(f"TikTokDer v{__version__}")`.
4. Edit `main.py`:
   - Add `from version import __version__` near top.
   - Inside `parse_args()`, after `parser = argparse.ArgumentParser(...)`, add:
     ```python
     parser.add_argument("--version", "-V", action="version", version=f"TikTokDer {__version__}")
     ```
5. Compile-check: `python -c "import version, app, main"` (skip `gui.main_window` which needs Qt) and `python main.py --version`.

## Todo List
- [ ] Create `version.py` with parsing guard
- [ ] Wire `setApplicationVersion` in `app.py`
- [ ] Update window title in `gui/main_window.py:68`
- [ ] Add `--version` flag to `main.py` argparse
- [ ] Smoke-test: `python main.py --version` prints `TikTokDer 1.4.0`
- [ ] Smoke-test: `python -c "from version import __version__, __version_info__; print(__version__, __version_info__)"`

## Success Criteria
- `python main.py --version` exits 0 with stdout `TikTokDer 1.4.0`.
- Launching GUI shows window title `TikTokDer v1.4.0`.
- `from version import __version_info__; assert __version_info__ == (1, 4, 0)`.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Circular import via `version.py` | Very Low | Low | Module imports only `re` — no project deps |
| Malformed `__version__` ships | Low | Medium | Import-time regex guard raises `ValueError` |
| `setApplicationVersion` called before `QApplication` constructed | Very Low | Low | Order preserved — call sits right after `setApplicationName` on the same `app` instance |

## Security Considerations
None. Static string constant; no user input; no I/O.

## Next Steps
Phase 02 (About dialog), Phase 03 (build/spec), Phase 04 (docs), Phase 05 (tests) — all unblock once `version.py` exists.
