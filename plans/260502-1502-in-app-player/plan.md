---
title: "In-app player — embed playback in Library"
description: "Replace 'Open in OS player' bounce with inline QtMultimedia playback inside LibraryPreviewPane. Adds resume-from-position via HistoryRecord schema v4."
status: completed
priority: P1
effort: ~1-2d
branch: main
tags: [gui, multimedia, library, preview-pane, schema-migration, pyinstaller, pyside6]
created: 2026-05-02
completed: 2026-05-02
shipOrder: 2  # ship after health-view
blockedBy: []
blocks: []
---

# In-app Player

## Context

- Origin: brutal-honesty review (turn 1 in this session) — current flow bounces the user to OS default player; that breaks the "personal archive" experience and forecloses on transcript-jump features.
- Touches: `gui/library_preview_pane.py`, `history_store.py` (schema v4), `gui/library_panel.py` (double-click wiring), `tiktokder.spec` (Qt6 multimedia plugins), tests.
- Dependency: PySide6's `QtMultimedia` + `QtMultimediaWidgets` — already shipped, **no new pip dep**.

## Goal

Double-click a Library row → playback starts inside the right-side preview pane (replacing the static thumbnail). Persist last position so the next play resumes. Fall back to OS default player on codec failure (don't fight VP9). All within ~400 LOC across 5 phases.

## Approved Decisions

| Decision | Choice |
|---|---|
| Placement | Inline in `LibraryPreviewPane` via `QStackedWidget` (thumbnail ↔ player). Deferred: dedicated "Watch" sub-tab. |
| Player widget | `QMediaPlayer` + `QVideoWidget` + `QAudioOutput` |
| Trigger | Double-click row in Library table. Single-click still selects (existing behavior). |
| Schema bump | `HistoryRecord` v3 → v4: add `last_played_at`, `play_position_seconds`. Reuse existing `_ACCEPTED_DICT_SCHEMAS` migration. |
| Persist cadence | Debounced `positionChanged` (every 5s) + on stop/pause/close. |
| Resume | If `play_position_seconds > 5s` and `< duration - 5s`, resume there. Otherwise start at 0. |
| Keyboard | J/K/L (rewind 10s / play-pause / forward 10s), space (play-pause), ←/→ (±5s). |
| Audio-only `.m4a` | Same widget; QVideoWidget hidden, thumbnail kept visible behind controls. |
| Codec fallback | On `QMediaPlayer.errorOccurred`, log + show a small "Open externally" button. Don't ship codec packs. |
| Aspect ratio | Letterbox; respect source aspect inside the fixed preview frame. |
| Bundling | Update `tiktokder.spec` to include `PySide6.QtMultimedia`, `QtMultimediaWidgets`, and Qt's Windows multimedia plugins (mediaservice/imageformats). |

## Out of Scope

- Dedicated "Watch" sub-tab (deferred — measure demand first).
- Playlist / queue inside the player (deferred).
- Transcript search / timestamp jump (separate future feature; this plan unblocks it).
- Audio-track / subtitle pickers in the UI (yt-dlp downloads them as sidecars; player just plays the primary track).
- Custom controls beyond play/pause/scrubber/keyboard. Use Qt-stock controls where possible.
- macOS / Linux multimedia plugin testing — Windows-first, document gaps in CHANGELOG.

## Phases

| # | Phase | File | Effort | Risk | Status |
|---|-------|------|--------|------|--------|
| 1 | History schema v4 — `last_played_at` + `play_position_seconds` | [phase-01-history-schema-v4.md](phase-01-history-schema-v4.md) | XS (~30m) | Low | ✅ done |
| 2 | `LibraryPreviewPane` — QStackedWidget + player wiring | [phase-02-stacked-preview-pane.md](phase-02-stacked-preview-pane.md) | M (~3-4h) | Med (codec) | ✅ done |
| 3 | Resume + position persist + keyboard + fallback | [phase-03-resume-keyboard-fallback.md](phase-03-resume-keyboard-fallback.md) | S (~2h) | Low | ✅ done |
| 4 | PyInstaller spec — Qt6 multimedia plugins | [phase-04-pyinstaller-spec.md](phase-04-pyinstaller-spec.md) | S (~1h) | Med | ✅ done (manual clean-VM smoke deferred to release-build) |
| 5 | Tests — schema, debounce, fallback, smoke | [phase-05-tests.md](phase-05-tests.md) | S (~2h) | Low | ✅ done (28 new tests; 455 total green) |

**Strict order:** 1 → 2 → 3 → 4 → 5. Phase 4 lands together with the source change before any release build.

## Dependencies

- `PySide6.QtMultimedia`, `PySide6.QtMultimediaWidgets` — already in transitive PySide6.
- Windows Media Foundation system libs for H.264 — present on every supported Windows.
- ffmpeg (already documented as optional) — not required for playback, only for some yt-dlp merges.

## Success Criteria

- [ ] Double-clicking a Library row plays the video inside the preview pane within 1s on a warm cache.
- [ ] Schema v4 migration loads existing v3 history without data loss.
- [ ] Resume from position works after closing/reopening the app.
- [ ] J/K/L/space/←/→ keyboard shortcuts behave per spec.
- [ ] Failed codec triggers fallback button, not a crash.
- [ ] `python build.py` (PyInstaller) produces an exe whose Library player works on a clean Windows test machine.
- [ ] All new tests pass; existing suite stays green.

## Risk Snapshot

| Risk | Mitigation |
|---|---|
| Qt multimedia plugins missing in PyInstaller bundle (silent on dev, broken on user PC) | Phase 4 explicitly collects plugins via `collect_data_files('PySide6', subdir='Qt/plugins/multimedia')` and validates with a clean-VM smoke test. |
| VP9/WebM from FB doesn't play | Detect via `errorOccurred` → `_show_external_fallback()`. No codec install dance. |
| 10k-row Library + frequent position writes hammer disk | Debounce position-persist to 5s intervals + on-stop only. Atomic-replace pattern from history_store. |
| Schema v4 confuses old binaries | Same one-way migration model as v2→v3; old binary returns empty list, documented in CHANGELOG. |
| Audio-only `.m4a` shows blank video area | Detect by extension or `mediaStatusChanged` "no video"; keep thumbnail visible behind player. |
| Re-entrancy: switching rows mid-playback | Always `player.stop()` then re-set source; persist position of outgoing record before switching. |

## Open Questions

1. Should "play" replace the thumbnail or overlay it (with semi-transparent control bar)? (Default: replace via QStackedWidget; simpler, fewer paint bugs.)
2. Should we add a "Now playing" header in the status bar? (Default: no — YAGNI.)
3. Should resume threshold be configurable in Settings? (Default: no — hardcode 5s; revisit if users complain.)
