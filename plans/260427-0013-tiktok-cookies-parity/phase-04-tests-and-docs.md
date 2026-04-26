# Phase 04 — Tests + README Sync

## Context Links
- Phases 01–03

## Overview
- **Priority:** P2
- **Status:** completed
- **Depends on:** Phase 02, Phase 03
- **Effort:** XS (~20 min)
- **Description:** Unit-test `apply_cookies()` precedence; add config-migration test; update README Settings table.

## Key Insights
- The helper is pure (no I/O beyond `Path.exists()`). Trivial to unit-test with `tmp_path` fixture.
- Migration shim is also pure dict→object — trivial test target.

## Requirements
**Functional**
- New unit tests cover `apply_cookies()` precedence cases
- New unit test covers config legacy-key migration
- Existing tests still pass (no regression)
- README Settings table reflects new TikTok cookies row + renamed FB field

**Non-functional**
- Tests fast (<1s combined), no network, no GUI launch

## Test Cases — `apply_cookies()`
| Case | Inputs | Expected `ydl_opts` mutation |
|------|--------|------------------------------|
| Both None | `browser=None, file=None` | no `cookiefile`, no `cookiesfrombrowser` |
| Browser only | `browser="chrome", file=None` | `cookiesfrombrowser=("chrome",)` |
| File only (exists) | `browser=None, file=existing_path` | `cookiefile=str(path)` |
| File missing | `browser=None, file=nonexistent_path` | no keys (silent skip — yt-dlp would fail loudly anyway) |
| Both set, file exists | `browser="chrome", file=existing_path` | `cookiefile=str(path)` only — file wins |
| Both set, file missing | `browser="chrome", file=nonexistent_path` | `cookiesfrombrowser=("chrome",)` — falls through |

## Test Cases — Config Migration
- Load JSON containing `cookies_file: "/path/a.txt"` and no `facebook_cookies_file` → `config.facebook_cookies_file == Path("/path/a.txt")`
- Load JSON containing both keys → `facebook_cookies_file` wins (new key authoritative)
- Save config with `facebook_cookies_file` set → output JSON has `facebook_cookies_file` key, no `cookies_file` key

## Related Code Files
**Modify:**
- `tests/` — add new test file `test_apply_cookies.py` (kebab style: `test_apply_cookies.py`)
- `tests/test_config.py` (or equivalent) — add migration test cases
- `README.md` — Settings table row for TikTok Cookies File; tooltip text in row description

**Read for context:**
- Existing `tests/` files for fixture / style conventions

## Implementation Steps
1. Create `tests/test_apply_cookies.py` with 6 cases above
2. Locate existing config tests (if any). Add migration tests; if no config test file exists, create `tests/test_config_migration.py`
3. Run `pytest -v tests/test_apply_cookies.py tests/test_config_migration.py` — all pass
4. Run full suite `pytest -v` — no regressions
5. Update `README.md` Settings table:
   - TikTok group: add "Cookies File" row mirroring FB row format
   - Facebook group: confirm "Cookies File" row description still accurate
6. Read README diff; ensure phrasing matches existing style (concise, single line per row)

## Todo List
- [x] Wrote `test_apply_cookies.py` at project root (matches existing flat test layout) — 6 cases
- [x] Added `TestCookiesFileMigration` class to `test_config.py` — 3 cases
- [x] All new tests pass (9 cases)
- [x] Full suite passes (366 tests) — no regressions
- [x] README Settings table updated for TikTok cookies row
- [x] README features bullet mentions TikTok cookies.txt

## Success Criteria
- `pytest -v` reports new tests passing, full suite green
- README accurately documents TikTok cookies setting
- A user reading only README can configure TikTok cookies without inspecting code

## Risk Assessment
| Risk | Mitigation |
|------|------------|
| `tmp_path` fixture not used in existing tests | Standard pytest fixture, safe to introduce |
| Test file naming inconsistent with existing convention | Inspect existing `tests/` first; match style |
| README example formatting drifts from existing tables | Copy exact row format from FB row |

## Security Considerations
- Tests use `tmp_path` for fixture cookie files — no real cookies committed
- README does not embed any cookie examples

## Next Steps
- Implementation complete. Run `/ck:cook` to execute the plan.
- Post-implementation: docs-manager update if `docs/code-standards.md` mentions cookie config (likely no impact, but verify).
