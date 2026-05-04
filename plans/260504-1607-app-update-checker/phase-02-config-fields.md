# Phase 02 — `config.py` persistence fields

**Priority:** P2 · **Status:** todo · **Effort:** ~30min

## Context Links
- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md) — section "Config Additions"
- File: `config.py` — `AppConfig` dataclass at line 82
- Filter behaviour: `load_config()` at lines 170-187 already drops unknown keys, so additive change is safe both forward and backward.

## Overview
Add three fields to `AppConfig`. JSON config is plain dict-of-fields (`asdict` in `save_config`); `load_config` already filters to known fields. No migration logic needed.

## Key Insights
- The `load_config()` filter (`filtered = {k: v for k, v in data.items() if k in known}`) means **old configs without these keys load cleanly** with defaults, and **new configs roll back cleanly** because the unknown keys get dropped.
- `last_update_check_at: float = 0.0` — `0.0` sentinel = "never", read by `should_check_now`.
- `skipped_update_version: str = ""` — empty = none skipped. Compared against `ReleaseInfo.version_str`.
- `update_check_enabled: bool = True` — default opt-in, no first-run prompt (per brainstorm decision #5).

## Requirements

**Functional:**
- Three new `AppConfig` fields with the names, types, and defaults from the brainstorm.
- `load_config` round-trips them (existing test pattern in `test_config.py`).
- `save_config` persists them (covered by `asdict` already).

**Non-functional:**
- Zero changes to existing fields. Pure additive.
- `__all__` export unchanged.

## Architecture

```python
# config.py: inside @dataclass class AppConfig
last_update_check_at: float = 0.0       # epoch seconds, 0 = never
skipped_update_version: str = ""        # "1.10.1" if user clicked Skip
update_check_enabled: bool = True       # opt-out flag (default ON)
```

Insert location: after `facebook_browse_downloaded_filter` (current line ~109), before the closing of the dataclass body. Group the three together with a section comment `# ── update checker (Phase 02) ──`.

## Related Code Files

**Modify:**
- `config.py` — add three fields to `AppConfig`
- `test_config.py` — add round-trip test for the new fields

**Read (no edits):**
- `update_checker.py` (post phase-01) — to confirm field name/type alignment with `should_check_now(last_check_ts, ...)`

## Implementation Steps

1. Open `config.py:82` (`@dataclass class AppConfig:`).
2. Insert three field declarations after the existing `facebook_browse_downloaded_filter` line, with a one-line section comment.
3. Compile-check: `python -c "from config import AppConfig; c = AppConfig(); print(c.last_update_check_at, c.skipped_update_version, c.update_check_enabled)"` → `0.0  True`.
4. Open `test_config.py`. Find an existing round-trip test (e.g., one that calls `save_config` then `load_config`) and add a sibling test that mutates the three new fields, saves, reloads, and asserts equality. Use `tmp_path` if the existing tests do; otherwise mirror their pattern.
5. Run `python -m pytest test_config.py -v`.

## Todo List

- [ ] Add three fields to `AppConfig`
- [ ] Compile-check
- [ ] Add round-trip test for new fields
- [ ] Verify backward compat: hand-craft a `config.json` lacking the new keys, confirm `load_config()` returns defaults
- [ ] Verify forward compat: hand-craft a `config.json` with extra unknown keys, confirm filter drops them silently (this is existing behaviour, regression-check it)
- [ ] All `test_config.py` green

## Success Criteria

- `AppConfig()` exposes the three fields with documented defaults
- Existing `test_config.py` tests still pass
- New round-trip test green
- A pre-existing `config.json` from v1.9.0 still loads without error

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Field name typo causes phase-04 import to fail silently | Phase-04 starts only after this phase merges; integration test at phase-04 catches it |
| `update_check_enabled=True` default surprises users on upgrade | Acceptable per brainstorm decision; check is silent unless newer version exists |

## Security Considerations
None — three primitive fields persisted to local JSON. No secrets, no PII.

## Next Steps
Unblocks phase-04 (worker reads/writes these fields).
