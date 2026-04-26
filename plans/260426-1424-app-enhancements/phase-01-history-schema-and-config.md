---
title: "Phase 01 — History schema v2 + AppConfig extensions"
priority: P0
effort: 50m
status: planned
depends: []
---

# Phase 01 — History Schema v2 + AppConfig Extensions

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ History persistence, § File-Level Impact Map)
- Affected file: `config.py` (currently 182 LOC)
- Existing tests: `test_config.py` (203 LOC)

## Overview
Upgrade `data/history.json` from `list[str]` (schema v1) to `list[record]` (schema v2). Add new `AppConfig` fields for quality default and subs/thumb toggles. Auto-migrate on first load with zero data loss. Keep `load_history() -> set[str]` for back-compat callers.

## Key Insights
- 1 internal call site uses `load_history()` (`download_engine.py`); History tab is the only new consumer needing rich records.
- New `HistoryRecord` dataclass is immutable; we serialize via `dataclasses.asdict`.
- Migration is one-shot: detect `list[str]` shape → wrap each ID into a partial record with `null` for new fields.
- Atomic write (temp + `os.replace`) prevents corruption on crash.

## Requirements

### Functional
- `load_history() -> set[str]` returns video-ID set; transparently reads v1 or v2.
- `load_history_records() -> list[HistoryRecord]` returns full records; empty list when file absent or v1 minimal.
- `save_history_records(records: list[HistoryRecord]) -> None` persists v2 format atomically.
- `add_history_record(record: HistoryRecord) -> None` appends one record, applies FIFO soft-cap, writes atomically. Convenience wrapper for engine.
- `AppConfig` new fields:
  - `quality_default: str = "best"` — one of `best|1080p|720p|480p|audio`
  - `write_subtitles: bool = False`
  - `write_thumbnail: bool = False`
  - `history_max_entries: int = 10000`

### Non-Functional
- File-size budget: keep `config.py` under 250 LOC. If approaching limit, extract `history_store.py` module for record I/O.
- Migration must be idempotent (running it twice over a v2 file is a no-op).
- Reject malformed JSON gracefully → return empty / log warning, never raise.

## Architecture

### Data Model
```python
# config.py
@dataclass
class HistoryRecord:
    video_id: str
    platform: str | None = None        # "tiktok" | "facebook" | None
    uploader: str | None = None
    title: str | None = None
    url: str | None = None
    quality: str | None = None         # e.g. "1080p", "audio"
    file_path: str | None = None       # relative to output_dir or absolute
    size_bytes: int | None = None
    downloaded_at: str | None = None   # ISO8601 with tz
```

### File Format (schema v2)
```json
{
  "schema": 2,
  "entries": [{ "video_id": "...", "platform": "tiktok", ... }]
}
```

### Migration Rules
- File missing → return empty.
- Top-level is `list` of `str` → schema v1 → wrap each into `HistoryRecord(video_id=id)` and persist as v2 on next write (lazy migration).
- Top-level is `dict` with `schema == 2` → load `entries` as records.
- Top-level is unrecognized JSON → log + return empty (never raise).

### FIFO Soft-Cap
On `add_history_record`, if `len(records) > history_max_entries`, drop the oldest. Files on disk are NOT touched.

## Related Code Files

### To Modify
- `config.py` — add `HistoryRecord`, `load_history_records`, `save_history_records`, `add_history_record`, schema v2 read/write, migration; rewrite `load_history` to read v1 or v2; rewrite `save_history` to write v2.
- `test_config.py` — extend with v1→v2 migration test, soft-cap test, malformed file test.

### To Create
- (optional) `history_store.py` if `config.py` exceeds 250 LOC after additions. Decision deferred to implementation.

### Not Touched This Phase
- `download_engine.py` — Phase 07 will swap `save_history` calls for `add_history_record`.

## Implementation Steps
1. Add `HistoryRecord` dataclass in `config.py`.
2. Add new `AppConfig` fields with defaults; existing field-filter in `load_config()` already drops unknown keys, so old configs load unchanged.
3. Implement `_read_history_file() -> tuple[int, list[HistoryRecord]]` — pure parser; returns `(schema_version, records)`.
4. Rewrite `load_history()` to call `_read_history_file()` and return `{r.video_id for r in records}`.
5. Implement `load_history_records()` returning the records list.
6. Implement `save_history_records(records)` — write `{"schema": 2, "entries": [...]}` atomically (temp + `os.replace`).
7. Implement `add_history_record(record, max_entries)` — load → append → FIFO trim → save.
8. Keep deprecated `save_history(ids: set[str])` as a thin shim that wraps each ID into a bare record (used only by tests and any leftover call site; remove once Phase 07 lands).
9. Write tests covering: v1 migration, v2 round-trip, malformed file fallback, FIFO trim at cap.
10. `python -m py_compile config.py` then `pytest test_config.py -v`.

## Todo
- [ ] Add `HistoryRecord` dataclass.
- [ ] Add `AppConfig.quality_default`, `write_subtitles`, `write_thumbnail`, `history_max_entries`.
- [ ] Implement `_read_history_file` parser + migration detection.
- [ ] Rewrite `load_history` to delegate to parser.
- [ ] Implement `load_history_records`, `save_history_records`, `add_history_record`.
- [ ] Atomic write helper (temp + `os.replace`).
- [ ] Tests: v1→v2 migration, v2 round-trip, malformed JSON fallback, FIFO cap.
- [ ] Compile check + targeted test run.

## Success Criteria
- `load_history()` returns the same `set[str]` for both a v1 file and an equivalent v2 file.
- `save_history_records` writes valid JSON conforming to schema v2.
- Reading a malformed file returns `(0, [])` and emits one log warning, no exception.
- All existing `test_config.py` cases still pass.
- New tests for migration + cap pass.
- `config.py` ≤ 250 LOC OR refactored into `history_store.py` if it exceeds.

## Risk & Mitigation
- **Concurrent writes corrupting file** → atomic write via temp + `os.replace`.
- **`save_history` callers expecting old format** → shim accepts `set[str]`, wraps into bare records, calls `save_history_records`. Behaviour preserved.
- **`config.py` LOC bloat** → extract to `history_store.py` if needed; LOC check is part of acceptance.

## Security
- JSON parse uses stdlib `json`, no `eval`. Validate types per field; ignore unknown keys.
- File paths in records are stored as-is; never executed. Path traversal mitigated when used (Phase 07 normalizes via `os.path.realpath` before opening).

## Next Steps
- Phase 03 reads `AppConfig.quality_default` etc. for `get_ydl_opts`.
- Phase 05 (History tab) consumes `load_history_records`.
- Phase 06 (Settings) writes the new config fields.
- Phase 07 swaps engine `save_history(set)` → `add_history_record(rec)`.
