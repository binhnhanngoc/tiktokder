# Phase 3 — Resume + position persist + keyboard + codec fallback

**Status:** completed · **Priority:** P1 · **Effort:** S (~2h) · **Risk:** Low

## Context

- Files: `gui/library_preview_pane.py` (extends Phase 2 work), `history_store.py` (a small helper if needed for partial-update writes).
- Builds on Phase 1 (schema v4 fields) and Phase 2 (player wiring).

## Goal

Three small behaviors that turn the player from "plays once" into a useful archive tool:
1. **Resume** from `play_position_seconds` if the value is between 5s and `duration - 5s`.
2. **Persist** position every 5s during playback + on stop/pause/source-change.
3. **Keyboard** shortcuts (J/K/L/space/←/→) when the player page has focus.
4. **Fallback** — on `QMediaPlayer.errorOccurred`, surface a small "Open externally" button that uses the existing `gui/_history_helpers.open_path`.

## Key Insights

- `QMediaPlayer.positionChanged(int ms)` fires ~4×/sec — debouncing in Qt-land is best done with a `QTimer(singleShot=True, interval=5000)` reset on each tick, only writing when the timer fires.
- Updating one record in `data/history.json` shouldn't rewrite the whole file mid-playback. Add `update_history_record_fields(video_id, **patch)` to `history_store.py` — atomic load → mutate → atomic save. Cheap at our scale (≤10k rows).
- For "resume," seek **after** `mediaStatusChanged == LoadedMedia`, not immediately after `setSource` (position is invalid until media loads).
- Keyboard shortcuts via `QShortcut` scoped to `_player_page` so they don't fire when typing in search boxes.

## Requirements

- Resume only triggers when `5 < play_position_seconds < duration - 5`. Outside that range, start at 0.
- Position writes batched: at most one disk write per 5s + one final write on stop/pause/source-change/closeEvent.
- Keyboard shortcuts active **only when** `_player_page` is the visible stack widget.
- Codec failure: on `errorOccurred(error, errorString)`, show a `QLabel` ("Can't play this format") + `QPushButton("Open externally")` overlay; clicking calls `open_path(record.file_path)`. Don't crash, don't loop.

## Architecture

```
LibraryPreviewPane (extends Phase 2)
├── self._position_persist_timer: QTimer(singleShot=True, interval=5000)
├── self._current_record: HistoryRecord | None
├── self._fallback_panel: QWidget (hidden by default)
├── self.player.mediaStatusChanged.connect(self._on_media_status)
├── self.player.errorOccurred.connect(self._on_error)
├── self.player.positionChanged.connect(self._on_position_changed)
└── Shortcuts (QShortcut on self._player_page):
    Space, K           → toggle play/pause
    J, Left            → seek -5s (or -10s for J)
    L, Right           → seek +5s (or +10s for L)

history_store.py
└── + def update_history_record_fields(records_path: Path, video_id: str, **patch) -> None
       atomic load → find by video_id → set fields → atomic save (returns silently on miss)
```

## Related Code Files

**Modify:**
- `gui/library_preview_pane.py` — extend the player wiring from Phase 2.
- `history_store.py` — add `update_history_record_fields`.
- `gui/_history_helpers.py` — already provides `open_path`; just import.

**Read for context:**
- `gui/library_preview_pane.py:30-118` (Phase 2 baseline).
- `history_store.py:113-148` (existing `save_history_records` for pattern matching).
- Phase 1 (schema v4 fields).

## Implementation Steps

1. **Resume logic:**
   - In `play(record)`, store `self._current_record = record` and `self._pending_resume_seconds = record.play_position_seconds`.
   - Connect once to `mediaStatusChanged`. When status == `LoadedMedia` and `_pending_resume_seconds` is in range:
     ```python
     dur_s = self.player.duration() / 1000
     if 5 < self._pending_resume_seconds < dur_s - 5:
         self.player.setPosition(int(self._pending_resume_seconds * 1000))
     self._pending_resume_seconds = None
     ```
2. **Debounced persist:**
   - `_on_position_changed(ms)` updates the scrubber UI (Phase 2 already), then `(re)starts the persist timer`.
   - `_position_persist_timer.timeout` → `_persist_position()`:
     ```python
     if self._current_record is None: return
     pos_s = self.player.position() / 1000
     update_history_record_fields(
         HISTORY_PATH,
         self._current_record.video_id,
         last_played_at=datetime.now(timezone.utc).isoformat(),
         play_position_seconds=pos_s,
     )
     ```
   - Also call `_persist_position()` on `playbackStateChanged == StoppedState`, on `stop_and_show_thumb()`, and on `closeEvent`.
3. **Keyboard shortcuts:** add 5 `QShortcut` entries scoped to `self._player_page`. Map J/L to ±10s, ←/→ to ±5s, space/K to toggle. `QShortcut(QKeySequence(Qt.Key_J), self._player_page).activated.connect(lambda: self._seek_relative(-10000))`.
4. **Codec fallback:**
   - Build `self._fallback_panel` once (hidden) — a `QFrame` with a label + button.
   - On `errorOccurred`: stop player, show fallback panel overlaying the player area (use a stacked-page-within-page or hide the video widget + show the fallback frame); button → `open_path(record.file_path)`.
   - On next successful `play()`, reset fallback panel hidden.
5. **`update_history_record_fields` in `history_store.py`:**
   - Accept `records_path: Path`, `video_id: str`, `**patch`.
   - Load via existing `_read_history_file`. If no records or no match, return silently.
   - Patch the matching record's fields (only those present in `_RECORD_FIELDS`).
   - Save via existing `save_history_records`.
   - Atomic-replace already covered by save path.
6. **closeEvent on MainWindow:** call `library_preview_pane.stop_and_show_thumb()` so the final position writes before exit.

## Todo List

- [x] Add `_position_persist_timer` + `_on_position_changed` debounce.
- [x] Add `update_history_record_fields` to `history_store.py`.
- [x] Implement `_persist_position()` slot.
- [x] Implement resume seek on `LoadedMedia`.
- [x] Add 6 QShortcut entries (J/L = ±10s, ←/→ = ±5s, space/K = toggle).
- [x] Implement codec fallback panel + `errorOccurred` slot.
- [x] Hook `MainWindow.closeEvent` to flush position.
- [ ] Manual: play, scrub to 30s, close app, reopen, double-click → resumes ~30s. (deferred)
- [ ] Manual: try a known-bad codec file → fallback button works. (deferred)

## Success Criteria

- Resume restores within ±2s of saved position.
- During 1 minute of continuous playback, exactly **12** disk writes happen (5s debounce). Verify with mtime polling in test or instrumentation.
- All 5 keyboard shortcuts trigger the correct action.
- Forcing a synthetic `errorOccurred` (e.g. set source to a non-media file) shows fallback button instead of crashing.

## Risks

| Risk | Mitigation |
|---|---|
| Disk-write storm if debounce fails | Test asserts ≤1 write per 4s window; covered in Phase 5. |
| Resume to position past actual duration → black screen | Range check `< duration - 5` already guards this. |
| Shortcuts hijack typing in Library search box | `QShortcut` scoped to `_player_page`, not the whole window. Verify Library search typing isn't blocked. |
| `update_history_record_fields` race with mainline save | Both go through atomic-replace; last-writer-wins is fine for this single-user app. Don't introduce locks. |

## Security Considerations

- `open_path` already handles cross-platform open safely. No additional surface.
- Position values are clamped to `int >= 0` at write time to avoid garbage data.

## Next Steps

→ Phase 4 — PyInstaller spec updates so the bundle includes Qt6 multimedia plugins.
