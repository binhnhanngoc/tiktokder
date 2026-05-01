# Phase 1 — History Schema v3

**Status:** pending · **Priority:** P1 · **Effort:** S (~30 min) · **Risk:** Low

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Files: `history_store.py:24` (HistoryRecord), `history_store.py:51` (`_read_history_file`), `history_store.py:114` (`save_history_records`).

## Goal

Add `description` and `thumbnail_path` fields to `HistoryRecord`. Bump `SCHEMA_VERSION` from 2 → 3. Read path stays backward-compatible: v1 list, v2 dict, v3 dict (new schema marker) all load cleanly.

## Key Insights

- `_record_from_dict` (line 42) already filters unknown keys via `_RECORD_FIELDS` set, so loading v2 records into a v3 dataclass is automatic — missing fields fall back to `None` defaults.
- Dropping a field would break loading; **only adding** fields here keeps full back-compat.
- Writes always emit the latest schema version; we just bump the version constant and the dict literal.

## Requirements

- `HistoryRecord` gains two optional fields with `None` defaults.
- New `SCHEMA_VERSION = 3`.
- Existing v2 files load and re-save as v3 with old fields preserved + new fields = `None`.
- v1 list-of-ids files still load and migrate transparently.
- No behavioral change for any reader that doesn't reference the new fields.

## Architecture

`HistoryRecord` is a frozen-shape dataclass; everything downstream consumes it via attribute access. Adding fields is non-breaking provided defaults are `None`.

`_read_history_file` shape detection currently keys on `data.get("schema") == SCHEMA_VERSION`. We loosen this to **accept v2 _and_ v3 dicts** (treat both as the dict-shape branch) so v2 files keep working when SCHEMA_VERSION advances.

## Related Code Files

**Modify:**
- `history_store.py` — schema version, dataclass, shape check.

**Read for context:**
- `download_engine.py:291-323` (`_build_record`) — confirm no positional `HistoryRecord(...)` calls; all kwargs.
- `gui/library_panel.py:262` — uses `load_history_records()` API; unchanged.
- `tests/test_history_store.py` (or equivalent) — existing migration tests.

## Implementation Steps

1. Bump `SCHEMA_VERSION` constant from `2` to `3` in `history_store.py:20`.
2. Append two fields to `HistoryRecord` (after `downloaded_at`):
   ```python
   description: str | None = None     # full caption from yt-dlp info["description"]
   thumbnail_path: str | None = None  # absolute path to sidecar .jpg/.webp
   ```
3. Update the docstring on `HistoryRecord` from "schema v2" → "schema v3".
4. Update top-of-file module docstring: add "Schema v3: ``{...}`` with `description` + `thumbnail_path`. Read paths transparently accept v1/v2/v3."
5. Loosen the shape check in `_read_history_file` (line 71):
   ```python
   if isinstance(data, dict) and data.get("schema") in (2, 3):
   ```
   Both versions parse via the same `_record_from_dict` filter — it discards unknown keys and fills missing ones with defaults.
6. No change to `save_history_records` — it already writes `SCHEMA_VERSION` (now 3) and `asdict(r)` (auto-includes new fields).

## Todo List

- [ ] Bump `SCHEMA_VERSION` to 3.
- [ ] Add `description` and `thumbnail_path` fields to `HistoryRecord` dataclass.
- [ ] Update class + module docstrings.
- [ ] Update `_read_history_file` to accept schema 2 or 3.
- [ ] `python -c "import history_store; print(history_store.SCHEMA_VERSION)"` smoke check.
- [ ] Run existing test suite — must remain green.

## Success Criteria

- `python -c "from history_store import HistoryRecord; r = HistoryRecord(video_id='x'); print(r.description, r.thumbnail_path)"` prints `None None`.
- Loading a v2 `data/history.json` produces records where new fields are `None`.
- Resaving immediately writes the file with `"schema": 3`.
- Existing pytest suite passes unchanged.

## Risks

| Risk | Mitigation |
|---|---|
| Forgetting to update shape check → v2 files start "empty" after upgrade | Test v2 → v3 round-trip explicitly in Phase 7. |
| Downgrading the app to v2 binary post-upgrade | Old `_read_history_file` rejects schema 3 → returns empty list; documented in CHANGELOG. |

## Security Considerations

None — schema-only change, no new I/O surface.

## Next Steps

→ Phase 2 (capture description + thumbnail_path during download). The new fields stay `None` until Phase 2 lands.
