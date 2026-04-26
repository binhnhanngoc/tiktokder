# Phase 01 — Saved-channels store + persistence

**Status:** pending
**Effort:** 0.5d
**Depends on:** —

## Context Links
- Plan: `plan.md`
- Brainstorm: `plans/reports/brainstorm-260426-2222-platform-first-ui-restructure.md` (§3.2.1, §4.3)
- Reference: `history_store.py` (atomic write + tolerant loader pattern to mirror)

## Overview
Standalone module that owns `data/saved_channels.json`. No UI yet. Built first so later phases can wire UI against a stable API + tested behaviour.

## Key Insights
- Mirror `history_store.py` shape: `_atomic_write`, schema-versioned dict, tolerant `_read_*`, never raises on malformed.
- Store keyed by platform string (`"tiktok"` / `"facebook"`); inside each, list of `SavedChannel` dataclasses.
- Cap = 200 per platform; trim oldest by `last_fetched_at` (None sorts oldest).
- "Download all new" filter logic lives here (pure function over `set[str] history_ids` + `last_fetched_at` + fetched videos) so UI just calls and queues.

## Requirements
**Functional**
- CRUD: `add`, `update`, `remove`, `list_all`, `find_by_url`.
- Update post-fetch: `mark_fetched(platform, url, video_ids, fetched_at)` writes `last_fetched_video_ids` + `last_fetched_at`.
- Filter helper: `select_new_videos(channel, fetched_videos, history_ids) -> list[VideoInfo]`.
- Cap enforcement on add.

**Non-functional**
- Atomic write (no torn JSON on crash).
- Tolerant load: malformed/missing → empty defaults, warning log.
- No PySide6 import (pure data layer; testable without Qt).

## Architecture
```
saved_channels_store.py  (NEW, project root)
├── @dataclass SavedChannel
├── @dataclass SavedChannelsStore   (in-memory + file-backed)
├── load_saved_channels(path) -> SavedChannelsStore
├── save_saved_channels(path, store)
└── select_new_videos(channel, fetched, history_ids) -> list[VideoInfo]
```

`SavedChannel` fields: `url, nickname, note, starred, last_fetched_at, last_fetched_video_ids`.

## Related Code Files
**Create**
- `saved_channels_store.py` (project root, ~150 LOC)
- `test_saved_channels_store.py` (project root, ~120 LOC)

**Modify**
- `config.py` — add `SAVED_CHANNELS_PATH = CONFIG_DIR / "saved_channels.json"` and re-export.

**Read for context**
- `history_store.py:86-99` — `_atomic_write` (consider extracting to a shared `_io_utils.py` only if duplication crosses 3 sites; otherwise copy once).
- `channel_fetcher.py` — `VideoInfo` shape.

## Implementation Steps
1. Create `saved_channels_store.py` with:
   - `SavedChannel` dataclass.
   - Tolerant `_read_file(path)` returning `(schema_version, store)`.
   - `load_saved_channels(path)`, `save_saved_channels(path, store)`.
   - `add_channel`, `remove_channel(platform, url)`, `update_channel`, `mark_fetched`.
   - `select_new_videos(channel, fetched_videos, history_ids)`:
     - keep `v` if `v.video_id not in history_ids` AND (`v.upload_date` is None OR `v.upload_date > channel.last_fetched_at`).
     - `upload_date` is `YYYYMMDD` per `channel_fetcher.VideoInfo`; compare lexicographically (works because zero-padded).
     - `last_fetched_at` is ISO8601 — convert to `YYYYMMDD` for comparison via `[:4]+[5:7]+[8:10]` slice.
   - Cap-200 trim on `add_channel`: drop oldest by `last_fetched_at` (None last).
2. Add `SAVED_CHANNELS_PATH` constant in `config.py`; export in `__all__`.
3. Write `test_saved_channels_store.py`:
   - empty file → empty store
   - malformed JSON → empty store + warning
   - round-trip add/save/load
   - cap enforcement (add 201, oldest dropped)
   - `select_new_videos` — id-only path (no upload_date)
   - `select_new_videos` — date-aware path (some videos pre-cutoff, dropped)
   - `select_new_videos` — fallback when `last_fetched_at` is None (id-only)
   - `mark_fetched` updates correct channel
   - `remove_channel` no-op on missing url
4. Run `pytest test_saved_channels_store.py -v`. Compile-check with `python -c "import saved_channels_store"`.

## Todo List
- [ ] `saved_channels_store.py` created
- [ ] `SAVED_CHANNELS_PATH` added to `config.py`
- [ ] `test_saved_channels_store.py` ≥9 tests passing
- [ ] No PySide6 imports in `saved_channels_store.py`
- [ ] Module imports cleanly

## Success Criteria
- All new tests pass (`pytest test_saved_channels_store.py -v`).
- Existing test suite unaffected (`pytest -v` green).
- Module under 200 LOC.

## Risk Assessment
- **Date comparison edge cases** — TikTok flat-playlist sometimes returns `upload_date=None`. Falling back to id-only when `upload_date` missing keeps behaviour deterministic.
- **Schema migration** — None needed (new file). v1 schema chosen up-front.

## Security Considerations
- File written under `CONFIG_DIR` (user-controlled location). No external input. JSON parsing is the only attack surface — tolerant loader handles malformed input gracefully.

## Next Steps
Phase 02 consumes this module via `SavedChannelsPanel`.
