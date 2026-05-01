---
title: "Library Thumbnails + Descriptions + Pretty Lookup UI"
description: "HistoryRecord schema v3 (description + thumbnail_path), 3-pane Library with thumbnail column + preview pane, description-aware search."
status: complete
priority: P2
effort: ~6h
branch: main
tags: [gui, library, history, schema-migration, thumbnail, description, pyside6]
created: 2026-04-27
completed: 2026-04-27
blockedBy: []
blocks: []
---

# Library Thumbnails + Descriptions + Pretty Lookup UI

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Touches: `history_store.py`, `download_engine.py`, `downloader.py`, `gui/library_panel.py`, `gui/settings_panel.py`, `README.md`, `tests/`

## Goal

Capture and surface thumbnail + description metadata for every newly-downloaded video, and rebuild the Library tab into a 3-pane visual lookup tool: `[uploader sidebar | table-with-thumbnail-column | preview pane]`. Existing search box gains description-aware filtering.

## Approved Decisions (from brainstorm)

| Decision | Choice |
|---|---|
| Display layout | Table + right-side preview pane |
| Description storage | Inline in `history.json`, searchable |
| Thumbnail download | Mandatory (always-on); store `thumbnail_path` on record |
| Backfill of old rows | None — new downloads only |
| Pane position | Right (vertical splitter), 3-way splitter |
| Thumbnail in table | Yes, fixed-width column at index 0 |
| Settings toggle fate | Hide entirely (default) |
| Preview-pane buttons | None (rely on existing right-click context menu) |
| Description length cap | None (store as-is) |

## Out of Scope

- Backfill of pre-v3 rows (no automatic re-fetch).
- Right-click "Refresh metadata" action (Phase 2 idea).
- Card-grid view toggle.
- Description full-text indexing (substring scan is fine at 10k cap).
- Settings panel cleanup beyond hiding the thumbnail toggle.
- Tauri migration concerns (separate blocked plan; will need to re-implement UI when it resumes).

## Phases

| # | Phase | File | Status | Effort | Risk |
|---|-------|------|--------|--------|------|
| 1 | History schema v3 (add fields + migrate) | [phase-01-history-schema-v3.md](phase-01-history-schema-v3.md) | complete | S | Low |
| 2 | Capture description + thumbnail path on download | [phase-02-capture-thumbnail-description.md](phase-02-capture-thumbnail-description.md) | complete | M | Low |
| 3 | Library table — thumbnail column + delegate + cache | [phase-03-table-thumbnail-column.md](phase-03-table-thumbnail-column.md) | complete | M | Med (perf) |
| 4 | Library preview pane (3-way splitter) | [phase-04-preview-pane.md](phase-04-preview-pane.md) | complete | M | Low |
| 5 | Search includes description text | [phase-05-search-includes-description.md](phase-05-search-includes-description.md) | complete | XS | Low |
| 6 | Hide thumbnail-toggle setting + README updates | [phase-06-settings-readme-cleanup.md](phase-06-settings-readme-cleanup.md) | complete | S | Low |
| 7 | Tests — migration, missing thumb, search-by-desc, perf smoke | [phase-07-tests.md](phase-07-tests.md) | complete | M | Low |

**Strict order:** 1 → 2 → 3 → 4 → 5 → 6 → 7. Phase 3+ depends on schema (1) and capture (2) for usable data.

## Dependencies

- yt-dlp's `info["description"]` field — present for both TikTok and Facebook in current versions.
- yt-dlp's `writethumbnail` postprocessor — already in use; sidecar lands beside the video as `{basename}.{jpg|webp|png}`.
- Qt webp image plugin — bundled with PySide6 wheels; verify on PyInstaller build later.
- `QPixmapCache` — built-in Qt cache (default 10 MB).

## Success Criteria

- [x] New `HistoryRecord` writes include non-null `description` (when yt-dlp returns one) and `thumbnail_path` (when sidecar exists).
- [x] Library table renders a thumbnail icon for new rows; existing rows show a placeholder.
- [x] Selecting a row populates the right preview pane with thumbnail + metadata + description.
- [x] Searching the description text returns matching rows.
- [x] Old v2 history files load cleanly (existing tests pass; new migration tests pass).
- [x] No noticeable scroll lag on a 10k-row history (perf-smoke test constructs panel + filters in <1s).

## Risk Snapshot

| Risk | Mitigation |
|---|---|
| QTableWidget perf with 10k thumbnails | Lazy paint via QStyledItemDelegate + QPixmapCache. Perf-smoke test with synthetic 10k rows. |
| webp not rendered on stripped builds | `QPixmap.isNull()` check → placeholder fallback. Re-validate on next PyInstaller build. |
| yt-dlp may not populate `description` for all platforms/videos | Field is optional (nullable). UI shows "(no description)" when empty. |
| Schema v3 breaks downgrade to v2 | One-way migration; document in CHANGELOG. Old binaries should refuse v3 cleanly (handled by `_read_history_file` shape check). |

## Resolved Open Questions (from brainstorm)

1. **Settings toggle fate:** hide entirely — remove the row from `settings_panel.py`. Old config value remains harmlessly in `config.json`; downloader ignores it.
2. **Preview-pane action buttons:** none — keep parity with the right-click context menu on the table.
3. **Description length cap:** none — store as-is; FB descriptions rarely exceed ~2 KB.

## Next Steps

1. Implement Phase 1 (schema). All later phases assume v3 fields exist.
2. Phase 2 capture before any UI work — easier to test UI with real data.
3. Phases 3 + 4 can be combined in one PR or split (3 first lets you eyeball thumbnails before pane work).
4. Phase 7 tests run last but write fixtures incrementally as each phase lands.
