# Phase 1 — History schema v4

**Status:** completed · **Priority:** P1 · **Effort:** XS (~30 min) · **Risk:** Low

## Context

- File: `history_store.py:24` (`SCHEMA_VERSION`), `history_store.py:30-44` (`HistoryRecord`), `history_store.py:25` (`_ACCEPTED_DICT_SCHEMAS`).
- Mirrors the v2→v3 migration path from plan `260427-1320-library-thumbnails-descriptions/phase-01-history-schema-v3.md` — same pattern, additive only.

## Goal

Add `last_played_at: str | None` and `play_position_seconds: float | None` to `HistoryRecord`. Bump `SCHEMA_VERSION` 3 → 4. Read path stays backward-compatible: v1 list, v2 dict, v3 dict, v4 dict all load cleanly.

## Key Insights

- `_record_from_dict` already filters unknown keys via `_RECORD_FIELDS`, so v3 records auto-load into v4 dataclass with `None` defaults.
- The v3 plan already loosened `_ACCEPTED_DICT_SCHEMAS = (2, 3)`. We extend it to `(2, 3, 4)` here. Same one-line change.
- Writes always emit `SCHEMA_VERSION` and `asdict(r)` — auto-includes new fields, no save-path edits required.

## Requirements

- `HistoryRecord` gains two optional fields with `None` defaults.
- New `SCHEMA_VERSION = 4`.
- `_ACCEPTED_DICT_SCHEMAS` accepts 2, 3, and 4.
- Existing v3 files load + re-save as v4 with old fields preserved + new fields = `None`.
- v1 list / v2 dict still migrate transparently.
- No behavioral change for any reader that doesn't reference the new fields.

## Architecture

Pure additive schema change — no new code paths, no new I/O.

## Related Code Files

**Modify:**
- `history_store.py` — bump version, append fields, extend tuple.

**Read for context:**
- `download_engine.py:291-323` (`_build_record`) — confirm only kwargs are used; new fields can stay `None` at write time (Phase 2 sets them on play).
- Existing `test_history_records.py` — fixture pattern for round-trip tests.

## Implementation Steps

1. Bump `SCHEMA_VERSION` constant from `3` to `4` at `history_store.py:24`.
2. Extend `_ACCEPTED_DICT_SCHEMAS` from `(2, 3)` to `(2, 3, 4)` at line 25.
3. Append two fields to `HistoryRecord` (after `thumbnail_path`):
   ```python
   last_played_at: str | None = None        # ISO8601 with tz; updated on play
   play_position_seconds: float | None = None  # seconds, for resume
   ```
4. Update class docstring from "schema v3" → "schema v4".
5. Update top-of-file module docstring: add "Schema v4: same shape as v3 plus `last_played_at` + `play_position_seconds` per record. Read paths transparently accept v1/v2/v3/v4."
6. Smoke check: `python -c "from history_store import HistoryRecord; r = HistoryRecord(video_id='x'); print(r.last_played_at, r.play_position_seconds)"` → `None None`.
7. Run existing test suite — must remain green.

## Todo List

- [x] Bump `SCHEMA_VERSION` to 4.
- [x] Extend `_ACCEPTED_DICT_SCHEMAS` to `(2, 3, 4)`.
- [x] Add `last_played_at` and `play_position_seconds` fields to `HistoryRecord`.
- [x] Update class + module docstrings.
- [x] Run `pytest -v` — green (455/455 across the repo).

## Success Criteria

- `from history_store import HistoryRecord; r = HistoryRecord(video_id='x'); assert r.last_played_at is None and r.play_position_seconds is None`.
- Existing `test_history_records.py` passes unchanged.
- A v3-shape `data/history.json` loads cleanly and re-saves as v4 (covered in Phase 5).

## Risks

| Risk | Mitigation |
|---|---|
| Forgetting to update `_ACCEPTED_DICT_SCHEMAS` → v3 files load empty after upgrade | Explicit Phase 5 test for v3 → v4 round-trip. |
| Downgrading the app to v3 binary post-upgrade | Old `_read_history_file` rejects schema 4 → returns empty list; document in CHANGELOG. |

## Security Considerations

None — additive schema, no new I/O surface.

## Next Steps

→ Phase 2 — wire `QStackedWidget` + `QMediaPlayer` into `LibraryPreviewPane`. The new fields stay `None` until Phase 3 starts persisting them.
