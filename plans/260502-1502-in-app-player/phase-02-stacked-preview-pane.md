# Phase 2 — `LibraryPreviewPane` stacked thumbnail ↔ player

**Status:** completed · **Priority:** P1 · **Effort:** M (~3-4h) · **Risk:** Med (codec)

## Context

- Files: `gui/library_preview_pane.py` (heavy edits), `gui/library_panel.py` (double-click wiring).
- This is the "meat" phase. Phase 3 layers behavior (resume, keyboard, fallback) on top.

## Goal

Replace the static `QLabel thumb` (line 38 of `library_preview_pane.py`) with a `QStackedWidget` containing two pages:
1. `_ThumbPage` — the existing thumbnail display.
2. `_PlayerPage` — `QVideoWidget` + a slim transport bar (play/pause + seek slider + time label).

`LibraryPanel` emits a new signal `play_requested(record)` on row double-click; preview pane handles it by switching to `_PlayerPage` and starting playback.

## Key Insights

- `QMediaPlayer` is set up once in `__init__`; the source URL changes per record. This avoids per-play widget churn.
- `QAudioOutput` must be assigned to the player; without it audio is silent.
- `setSource(QUrl.fromLocalFile(path))` is the right entry point for local files.
- Aspect ratio: `QVideoWidget.setAspectRatioMode(Qt.KeepAspectRatio)`. Letterbox is the simplest; fits the fixed preview frame.
- Switching records mid-play: stop player, persist position of outgoing record (Phase 3), set new source, start.

## Requirements

- Double-click on Library row triggers `play_requested(record)` (preview pane already shows that record from single-click selection).
- Player page renders inside the existing 360×200 preview frame (PREVIEW_W × PREVIEW_H).
- Transport bar: play/pause button (toggles), `QSlider` scrubber bound to `positionChanged`, time label `mm:ss / mm:ss`.
- Switching back to thumbnail: when user closes player or selects a different record, stop and switch page.
- Audio-only files: hide `QVideoWidget`, keep thumbnail visible behind controls.
- The pane never grows beyond its current footprint — playback is "preview-sized," not full-screen. (Future Watch sub-tab is the full-screen affordance.)

## Architecture

```
LibraryPreviewPane
├── self.stack: QStackedWidget(fixed PREVIEW_W × PREVIEW_H + transport)
│   ├── self._thumb_page: QLabel (existing)
│   └── self._player_page: QWidget
│       ├── QVideoWidget (or hidden when audio-only)
│       ├── transport bar:
│       │   ├── play_btn: QPushButton (toggles ▶ / ⏸)
│       │   ├── scrubber: QSlider
│       │   └── time_label: QLabel
├── self.player: QMediaPlayer (single instance)
├── self.audio_output: QAudioOutput (assigned to player)
├── + Slot: play(record) — switch to player page, set source, start
├── + Slot: stop_and_show_thumb() — stop player, switch back
├── + Signal: external_open_requested(record)  # Phase 3 codec fallback uses this
└── set_record(rec) — keep current behavior; if currently playing and rec changes,
                     emit position_should_persist(old_rec, position_ms) (Phase 3),
                     stop player, switch to thumbnail.

LibraryPanel
├── + Signal: play_requested(object)  # HistoryRecord
├── + double-click on table row → emit play_requested(rec_for_row)
└── (existing single-click selection behavior unchanged)

Library page wiring (in MainWindow or platform_tab)
└── library_panel.play_requested.connect(library_preview_pane.play)
```

## Related Code Files

**Modify:**
- `gui/library_preview_pane.py` — add stack, player, transport bar, slots.
- `gui/library_panel.py` — add `play_requested` signal + double-click handler.
- `gui/platform_tab.py` (or wherever the panel + preview pane are wired) — connect signals.

**Read for context:**
- `gui/library_preview_pane.py` (entire file — only 119 lines).
- `gui/library_panel.py` — find existing row-context-menu handler for the right click → reuse pattern.
- `gui/_history_helpers.py` — `open_path` is the existing "open externally" routine; reuse for fallback.

## Implementation Steps

1. In `LibraryPreviewPane.__init__`, wrap the existing `self.thumb` `QLabel` setup in a `_ThumbPage` widget. Keep the public `self.thumb` attribute pointing at the same QLabel so `set_record` keeps working.
2. Build `_PlayerPage` widget: `QVideoWidget` + transport bar inside a `QVBoxLayout`. Fixed size matches preview frame.
3. Replace the direct `layout.addWidget(self.thumb, ...)` with `self.stack = QStackedWidget(); self.stack.addWidget(self._thumb_page); self.stack.addWidget(self._player_page); layout.addWidget(self.stack, ...)`.
4. Construct `self.player = QMediaPlayer(self)` + `self.audio_output = QAudioOutput(self)`; `self.player.setAudioOutput(self.audio_output)`; `self.player.setVideoOutput(self._video_widget)`.
5. Wire transport:
   - `self.play_btn.clicked` → `self._toggle_play()`
   - `self.player.positionChanged` → update `scrubber` value (block signals during programmatic set) + `time_label`
   - `self.scrubber.sliderMoved` → `self.player.setPosition(value)` (user scrub)
   - `self.player.durationChanged` → `self.scrubber.setRange(0, duration_ms)`
6. Implement `play(record)`:
   - If `record.file_path` missing or file not on disk → `external_open_requested.emit(record)` and return.
   - If audio-only (extension `.m4a` or `.mp3` etc.): hide `_video_widget`, keep thumbnail behind transport bar (overlay layout).
   - `self.player.setSource(QUrl.fromLocalFile(record.file_path))`
   - `self.stack.setCurrentWidget(self._player_page)`
   - `self.player.play()` (Phase 3 adds resume-position seek before this).
7. Implement `stop_and_show_thumb()`:
   - If currently playing, capture `position_ms` for Phase 3 persist hook.
   - `self.player.stop()`
   - `self.stack.setCurrentWidget(self._thumb_page)`
8. Hook `set_record(rec)`: if `rec` is different from currently-playing record, call `stop_and_show_thumb()` first, then update thumb/metadata as today.
9. In `LibraryPanel`, add `play_requested = Signal(object)` and `cellDoubleClicked.connect(self._on_row_double_clicked)` → emit signal with the row's `HistoryRecord`.
10. In `platform_tab.py` (or wherever both panels are siblings), connect `library_panel.play_requested` → `library_preview_pane.play`.
11. Manual smoke: launch app, double-click a row → video plays in preview pane.

## Todo List

- [x] Refactor `LibraryPreviewPane` to use `QStackedWidget`.
- [x] Build `_PlayerPage` with `QVideoWidget` + transport bar.
- [x] Wire `QMediaPlayer` + `QAudioOutput`.
- [x] Implement `play(record)` + audio-only branch.
- [x] Implement `stop_and_show_thumb()` + record-switch handling.
- [x] Add `play_requested` signal + double-click handler in `LibraryPanel`.
- [x] Wire signal across panels (in-panel; preview pane is owned by `LibraryPanel`).
- [ ] Manual smoke test on a TikTok H.264 mp4. (deferred — needs interactive run)
- [ ] Manual smoke test on a `.m4a` audio-only file. (deferred)

## Success Criteria

- Double-click → video plays within 1s on warm filesystem cache.
- Single-click still updates thumbnail/metadata as before.
- Switching records mid-play stops the previous video cleanly.
- Audio-only files play with thumbnail visible behind transport.
- No new warnings in Qt log on launch.

## Risks

| Risk | Mitigation |
|---|---|
| `QVideoWidget` flickers/black on first play | Pre-warm by calling `setSource("")` once in `__init__`; or accept first-play delay, document. |
| Audio-only path silent because `QAudioOutput` not connected | Always assign `setAudioOutput` regardless of file type. |
| Double-click conflicts with row context menu | Verify `cellDoubleClicked` and right-click context menu don't both fire on same gesture (Qt gives them separate signals — should be fine). |
| Source path with non-ASCII characters | Use `QUrl.fromLocalFile`, not string concatenation. |
| `QMediaPlayer` instance leaks if pane closed mid-play | Set Qt parent → auto-deleted; explicit `self.player.stop()` in `closeEvent`. |

## Security Considerations

- Player sources are always local file paths constructed from `HistoryRecord.file_path` — never user-typed URLs.
- `QUrl.fromLocalFile` correctly escapes special characters; don't manually concatenate.

## Next Steps

→ Phase 3 — resume from last position, position persistence, keyboard shortcuts, codec fallback.
