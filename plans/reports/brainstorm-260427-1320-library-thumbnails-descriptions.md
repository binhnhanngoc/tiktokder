# Brainstorm — Library Thumbnails + Descriptions + Pretty Lookup UI

**Date:** 2026-04-27
**Scope:** Capture thumbnail + description metadata for downloaded videos, display them in a pretty, lookup-friendly Library view.
**Status:** Design approved, ready for `/ck:plan`.

---

## Problem Statement

Library View today (`gui/library_panel.py:111`) is a text-only 5-column `QTableWidget` (Title | Quality | Size | Date | Path). `HistoryRecord` (`history_store.py:24`) has 8 fields — no description, no thumbnail path. yt-dlp already writes `.jpg`/`.webp` thumbnail sidecars when the "Write thumbnail" setting is on (`downloader.py:254`), but nothing references them. Description is never extracted from yt-dlp's `info_dict`.

Users want to:
1. See thumbnails to identify videos visually.
2. Read captions/descriptions to recall what a video is.
3. Search by description text.
4. Keep the table fast for filtering/sorting at scale (history cap = 10k).

---

## Approved Design (all "Recommended" picks)

### Layout — 3-pane Library

```
+--------------+----------------------+----------------+
|  Uploaders   |        Table         |   PREVIEW      |
|  (sidebar)   |  Thumb Title Qty ... |   [thumbnail]  |
|  @alice  12  |  [img] Cat   1080p   |   Title (bold) |
|  @bob★   3   |  [img] Dog    720p   |   @uploader    |
|  @cara   8   |  [img] Cook  1080p   |   Date / Size  |
|              |                      |   Quality      |
|              |  filter row above    |   ----         |
|              |  (search,quality,    |   Description  |
|              |   date, size, status)|   (wraps,      |
|              |                      |    scrolls)    |
+--------------+----------------------+----------------+
```

- **Splitter:** 3-way `QSplitter(Qt.Horizontal)` — replaces today's 2-way splitter.
- **Thumb column:** new column 0, fixed ~64×36 px, row height ~40 px. Other columns shift right.
- **Preview pane:** updates on row selection. Empty state when nothing selected.
- **Sidebar + filter row:** unchanged behavior; preview pane respects current filter (only shows selected row).

### Data — `HistoryRecord` schema v3

Add two fields to `history_store.py:24`:

```python
description: str | None = None       # full text from yt-dlp info["description"]
thumbnail_path: str | None = None    # absolute path to sidecar .jpg/.webp
```

- **Migration:** v2 → v3 — existing rows get `None` for both fields; preserve v1 → v2 ladder. No data loss. New downloads only — no automatic backfill.
- **Storage cost:** at 10k cap × ~1 KB description avg ≈ 10 MB JSON; negligible for desktop.

### Capture — `download_engine.py:313`

In the `_make_history_record` block:
```python
description = info.get("description")
thumbnail_path = _resolve_thumbnail_sidecar(info, video_path)
```
- `_resolve_thumbnail_sidecar` strategy: glob `{video_basename}.{jpg,webp,png}` next to the video file. Fall back to `info.get("thumbnail_filename")` if yt-dlp populates it.
- Force `opts["writethumbnail"] = True` always in `downloader.py:254` (mandatory; setting toggle becomes a no-op or is hidden in settings panel).

### Search — extend filter

`library_panel.py` search box matches title/URL/uploader today. Add description (case-insensitive substring). Single-line behavior, no new UI.

### Rendering — thumbnail in table

- `setIconSize(QSize(64, 36))` on the `QTableWidget`.
- Custom `QStyledItemDelegate` for column 0 with `QPixmapCache` (key = `thumbnail_path`).
- Lazy-load: only paint thumbnails for visible rows. Missing/broken file → render placeholder icon.
- Webp support: relies on Qt's image plugins (bundled with PySide6 on all 3 OS).

---

## Evaluated Alternatives (rejected with rationale)

| Option | Why rejected |
|---|---|
| Card grid view | Pretty but lower density and weaker for sort/filter. Fights "easy to look up" goal. |
| Hover tooltip for description | Hides description behind interaction; not "pretty". |
| Toggle table+grid | YAGNI for v1; double the dev. |
| Sidecar `.description` file | Forces lazy-load to read; complicates search-by-description. |
| Always-on + dedicated thumb cache dir | Extra I/O step; sidecars are already stable beside videos. |
| Bulk backfill on first launch | Heavy, network-bound, may hit rate limits, slow startup. |
| Manual "Refresh metadata" right-click | Future enhancement, not v1. |

---

## Implementation Considerations

### Phases (proposed for `/ck:plan`)

1. **Schema** — `history_store.py`: add 2 fields, v2→v3 migration, update tests.
2. **Capture** — `download_engine.py`: extract description + resolve thumbnail path; `downloader.py`: force `writethumbnail=True`.
3. **UI – Table** — `library_panel.py`: add thumbnail column + delegate + `QPixmapCache`; update column index references.
4. **UI – Preview pane** — extend splitter to 3-way; build preview widget (QLabel scaled-thumb, metadata grid, scrollable QTextEdit description, "Open file" button).
5. **Search** — include description in filter substring match.
6. **Settings cleanup** — hide/remove "Write thumbnail" toggle in `settings_panel.py`; document in README.
7. **Tests** — migration v2→v3, missing thumb file, empty description, search-by-description hit.

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 10k thumbnails → memory pressure | `QPixmapCache` (default 10 MB) + lazy paint via delegate. |
| Webp not rendered on stripped Qt installs | Test on Win/macOS/Linux PySide6; fall back to placeholder if `QPixmap.isNull()`. |
| TikTok webp vs jpeg path | Glob `*.{jpg,webp,png}` next to video; first match wins. |
| Long Facebook descriptions | Preview pane uses scrollable read-only `QTextEdit`. |
| Old v2 rows look empty in preview | Empty-state UI: "No metadata captured (older download)". |
| Width sizing: thumb col stretching | Set column 0 to `QHeaderView.Fixed`, others retain current sizing. |
| Schema bump breaks downgrade | One-way migration only; document in CHANGELOG. |

### Out of Scope (Phase 2+)

- Right-click "Refresh metadata" to re-fetch yt-dlp info on existing rows.
- Bulk backfill action under a Tools menu.
- Card-grid view toggle.
- Description full-text indexing (current substring scan is fine at 10k).
- Per-row star/favorite / tags.

---

## Success Metrics

- All new downloads write `description` + `thumbnail_path` to `history.json`.
- Library shows a thumbnail icon for new rows; preview pane fills on selection.
- Searching the description text returns matching rows.
- v2 history files load cleanly post-upgrade (existing tests still pass).
- No noticeable scroll lag on 10k rows on a typical laptop.

## Validation

- `pytest -v` — schema migration tests + new search-by-description test.
- Manual smoke: download 3 TikTok + 2 Facebook videos, confirm thumb + desc in preview.
- Load a 10k-row `history.json` (synthetic) and scroll the table — measure FPS.

## Next Steps

1. Run `/ck:plan` with this report as context to scaffold phase files.
2. Implement Phase 1 (schema) first; everything else depends on it.
3. Update README "History" section to mention v3 + new fields.

---

## Unresolved Questions

1. **Settings toggle fate:** remove the "Write thumbnail" GUI toggle entirely, or keep it visible-but-disabled with a tooltip ("always on")? Slightly user-facing — confirm before settings_panel edits.
2. **Preview pane "Open file" / "Open folder" buttons:** add to preview pane, or rely on existing right-click table actions only? (Leaning: rely on existing context menu — YAGNI.)
3. **Description max-length cap in storage:** truncate at e.g. 8 KB to bound `history.json` size, or store as-is? (Leaning: as-is; FB descriptions rarely exceed ~2 KB.)
