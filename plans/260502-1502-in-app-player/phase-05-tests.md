# Phase 5 — Tests

**Status:** completed · **Priority:** P1 · **Effort:** S (~2h) · **Risk:** Low

## Context

- Files: extend `test_history_records.py`, new `test_library_player.py` (project root, matching existing convention).
- Covers Phases 1–3 (Phase 4 is validated by manual clean-VM smoke).

## Goal

Lock in: schema v3→v4 migration round-trip, position-persist debounce semantics, codec-fallback path, stack widget flip, and resume-position bounds. No real video file dependency in tests — use mocks where the QMediaPlayer can't be exercised headlessly.

## Requirements

- 3 schema/migration tests (v3 load + v4 save round-trip + `update_history_record_fields` patch).
- 1 debounce test (timer fires once per ≥5s window).
- 1 fallback-on-error test (errorOccurred → fallback panel visible).
- 1 stacked-widget flip test (play → player page; stop → thumb page).
- 1 resume-bounds test (5–(duration-5) range only).
- 1 keyboard test (synthetic key event triggers seek).

## Architecture

```
test_history_records.py  (extend existing)
├── test_load_v3_history_into_v4_dataclass
├── test_save_then_load_v4_round_trip
└── test_update_history_record_fields_atomic_patch

test_library_player.py  (new)
├── test_position_persist_debounce_5s
├── test_resume_seek_within_bounds
├── test_resume_no_seek_outside_bounds
├── test_codec_error_shows_fallback
├── test_stack_flip_on_play_and_stop
└── test_keyboard_seek_relative
```

## Related Code Files

**Create / extend:**
- `test_history_records.py` (extend).
- `test_library_player.py` (new).

**Read for context:**
- `test_library_panel.py` — Qt fixture pattern (`QApplication`, `qtbot` if available, otherwise plain construction).
- `test_history_records.py` — existing migration test pattern.
- `test_settings_split.py` — minimal Qt widget test bootstrap.

## Implementation Steps

1. **Schema v3 → v4 round-trip:**
   - Write a v3-shape dict to a tmp `data/history.json`.
   - `load_history_records(path)` → records have `last_played_at = None` and `play_position_seconds = None`.
   - `save_history_records(path, records)` → file now has `"schema": 4`.
2. **`update_history_record_fields` atomic patch:**
   - Seed file with 3 records.
   - Call `update_history_record_fields(path, video_id="abc", play_position_seconds=42.0)`.
   - Reload — only the matching record changed; file remains valid v4.
3. **Debounce test:**
   - Use `QTimer` + a stub player that fakes `positionChanged` ticks every 250ms.
   - Run for 6 seconds (use `QTest.qWait`).
   - Assert `update_history_record_fields` was called exactly **once** during the run + once on stop (= 2 total).
4. **Resume bounds test:**
   - Stub player with `duration() = 60_000`. For each of `play_position_seconds in [3.0, 30.0, 58.0]`, assert `setPosition` is called only for `30.0`.
5. **Codec error test:**
   - Build `LibraryPreviewPane`, call `play(record)`, manually emit `player.errorOccurred.emit(...)`.
   - Assert fallback panel becomes visible; assert clicking its button calls `open_path`.
6. **Stack flip test:**
   - Initial `stack.currentWidget() == thumb_page`.
   - `pane.play(record)` → `currentWidget() == player_page`.
   - `pane.stop_and_show_thumb()` → back to `thumb_page`.
7. **Keyboard test:**
   - Show pane, set stack to player page, focus it.
   - `QTest.keyPress(pane._player_page, Qt.Key_L)` → assert `_seek_relative(+10000)` was called (spy via monkeypatch).

## Todo List

- [x] Extend `test_history_records.py` with 5 v4-related tests (load v3-into-v4, save+load v4 round-trip, atomic patch happy path, missing-id no-op, unknown-key filter).
- [x] Create `test_library_player.py` with 22 tests across stack-flip, codec-fallback, resume-bounds (parametrized), position-persist (incl. real debounce window), keyboard-seek, and set-record switching.
- [x] All tests pass under `pytest -q` (455/455 across the repo, 1 unrelated existing warning).
- [x] Coverage check (informal): all branches of `play()`, `_persist_position()`, `_on_media_status_changed`, `_on_error_occurred`, `_seek_relative`, `_toggle_play`, and `update_history_record_fields` exercised.

## Success Criteria

- All new tests pass on CI.
- Existing test suite stays green (no regressions in `test_history_records.py`, `test_library_panel.py`).
- Manual: a real H.264 mp4 from a TikTok download plays inside the preview pane and resumes correctly across an app restart.

## Risks

| Risk | Mitigation |
|---|---|
| QMediaPlayer can't be exercised in headless CI | Use stub/mocks for player in tests; reserve real-media validation for manual smoke. |
| Qt event-loop quirks make debounce timing flaky | Use `QTest.qWait` (event-loop-aware) instead of `time.sleep`; pad assertion windows by 250ms. |
| `QTest` not consistently available across PySide6 versions | Fallback: drive `QTimer` ticks manually with `QCoreApplication.processEvents()`. |

## Security Considerations

None — test-only changes.

## Next Steps

Plan complete. After this phase ships, the in-app player + health view are both live. Future plan candidates:
- Transcript search (Whisper integration) — now unblocked by the in-app player's timestamp jump capability.
- "Watch" sub-tab with full-screen player + playlist — defer until users ask.
- Cross-platform multimedia plugin coverage (macOS / Linux) — defer until macOS/Linux build path is exercised.
