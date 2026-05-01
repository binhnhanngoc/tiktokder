# Phase 3 — Library Table: Thumbnail Column

**Status:** pending · **Priority:** P1 · **Effort:** M (~1.5h) · **Risk:** Med (perf)

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Files: `gui/library_panel.py:53` (column constants), `gui/library_panel.py:153` (table widget), `gui/library_panel.py:369` (`_render_table`).
- Depends on: Phase 1 (schema), Phase 2 (data populated).

## Goal

Insert a fixed-width thumbnail column at index 0 of the Library table. Render thumbnails lazily through a `QStyledItemDelegate` backed by `QPixmapCache`, so a 10k-row history doesn't load 10k pixmaps eagerly.

## Key Insights

- Column index reshuffles: Title moves from 0 → 1, Quality 1 → 2, etc. There is a **single source of truth** at `library_panel.py:56-71` (`_COL_*` constants + `_DEFAULT_WIDTHS`) — only file we need to update.
- `setItem(row, _COL_TITLE, ...).setData(UserRole, rec)` (line 388) is how the rest of the panel attaches the full record to the row. **Keep that on Title** — context menu uses `_COL_TITLE` for record lookup. Don't move it to the new thumbnail column.
- `QStyledItemDelegate.paint()` is called only for visible rows by Qt's lazy-paint viewport — perfect for thumbnails. Cache by `thumbnail_path` string.
- `QPixmapCache` default budget is 10 MB — plenty for 64×36 pixmaps (~7 KB each → ~1400 cached). Older entries auto-evicted.
- Webp may need Qt's image plugin; PySide6 wheels ship them. Failure path: `QPixmap.isNull()` → fallback to a placeholder icon.

## Requirements

- New column 0 labeled "Thumb" (or icon-only header), fixed width = 80 px (visual padding around 64×36).
- Row height grows to ~40 px (auto via `setIconSize`/delegate `sizeHint`).
- Thumbnail renders from `record.thumbnail_path`; missing/None → placeholder.
- Lazy load: pixmaps only built when a row is painted.
- Cache hit on re-scroll (no flicker, no re-decode).
- Column not sortable (sorting on it is meaningless); other columns retain their current sort behavior.
- Column index constants stay the single source of truth.

## Architecture

```
QTableWidget (Library)
   ├─ col 0  Thumbnail   ← QStyledItemDelegate.paint() reads UserRole=path → QPixmapCache
   ├─ col 1  Title       ← still owns the UserRole=HistoryRecord pointer
   ├─ col 2  Quality
   ├─ col 3  Size        ← _NumericItem
   ├─ col 4  Date
   └─ col 5  Path
```

Delegate uses `QPixmapCache.find(path)` → on miss, decode → scale to 64×36 KeepAspectRatio → cache.

## Related Code Files

**Modify:**
- `gui/library_panel.py` — add column, delegate, cache; rebump every `_COL_*` constant; widen the panel default sizes.

**Optional new module (if delegate grows):**
- `gui/library_thumbnail_delegate.py` — only if the delegate exceeds ~50 LOC.
  Naming: kebab-style snake module, descriptive — matches existing helper modules.

**Read for context:**
- `gui/library_panel.py:399` (`_on_context_menu`) — confirms `_COL_TITLE` is where the record attaches; updated index will still flow correctly because we use the constant.
- `gui/icons.py` (qtawesome helper) — for placeholder icon.

## Implementation Steps

1. **Re-index columns** in `library_panel.py:53-71`:
   ```python
   _HEADERS = ("", "Title", "Quality", "Size", "Date", "Path")  # col 0 header blank — icon-only
   _COL_THUMB = 0
   _COL_TITLE = 1
   _COL_QUALITY = 2
   _COL_SIZE = 3
   _COL_DATE = 4
   _COL_PATH = 5
   _DEFAULT_WIDTHS = {
       _COL_THUMB: 80,
       _COL_TITLE: 320,
       _COL_QUALITY: 80,
       _COL_SIZE: 90,
       _COL_DATE: 130,
       _COL_PATH: 240,
   }
   ```

2. **Lock thumbnail column width** in `__init__` after the existing resize-mode loop:
   ```python
   header.setSectionResizeMode(_COL_THUMB, QHeaderView.ResizeMode.Fixed)
   self.table.setColumnWidth(_COL_THUMB, _DEFAULT_WIDTHS[_COL_THUMB])
   ```

3. **Define the delegate** (in same file or new `gui/library_thumbnail_delegate.py`):
   ```python
   from PySide6.QtCore import QSize
   from PySide6.QtGui import QPixmap, QPixmapCache
   from PySide6.QtWidgets import QStyledItemDelegate

   _THUMB_W, _THUMB_H = 64, 36

   class LibraryThumbnailDelegate(QStyledItemDelegate):
       """Lazy-paint thumbnails with QPixmapCache. Reads path from UserRole."""

       def __init__(self, placeholder: QPixmap, parent=None):
           super().__init__(parent)
           self._placeholder = placeholder

       def sizeHint(self, option, index):
           return QSize(_THUMB_W + 16, _THUMB_H + 8)

       def paint(self, painter, option, index):
           path = index.data(Qt.ItemDataRole.UserRole)
           pix = self._lookup(path)
           # Center within the cell rect.
           cx = option.rect.x() + (option.rect.width() - pix.width()) // 2
           cy = option.rect.y() + (option.rect.height() - pix.height()) // 2
           painter.drawPixmap(cx, cy, pix)

       def _lookup(self, path: str | None) -> QPixmap:
           if not path:
               return self._placeholder
           cached = QPixmapCache.find(path)
           if cached is not None:
               return cached
           pix = QPixmap(path)
           if pix.isNull():
               return self._placeholder
           pix = pix.scaled(_THUMB_W, _THUMB_H,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
           QPixmapCache.insert(path, pix)
           return pix
   ```

4. **Build a placeholder pixmap** once at init (use qtawesome for an "image" icon, fall back to a flat gray rect):
   ```python
   placeholder = QPixmap(_THUMB_W, _THUMB_H)
   placeholder.fill(QColor("#2a2a2a"))   # neutral gray, theme-friendly
   ```
   (qtawesome icon optional — keep simple.)

5. **Install the delegate** in `__init__` after the table is created:
   ```python
   self._thumb_delegate = LibraryThumbnailDelegate(placeholder, self)
   self.table.setItemDelegateForColumn(_COL_THUMB, self._thumb_delegate)
   self.table.verticalHeader().setDefaultSectionSize(_THUMB_H + 8)
   ```

6. **Render path in `_render_table`** — set a no-text item on column 0 with the path in UserRole:
   ```python
   thumb_item = QTableWidgetItem("")
   thumb_item.setData(Qt.ItemDataRole.UserRole, rec.thumbnail_path)
   thumb_item.setFlags(thumb_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
   self.table.setItem(row, _COL_THUMB, thumb_item)
   # Title item still owns the full HistoryRecord on UserRole — unchanged.
   ```

7. **Disable sort** on the thumbnail column header — no sort key. By default Qt allows it; the easy way is leaving it alone since the items have no `Qt.DisplayRole` text and sort key (`__lt__`) compares empty strings (stable). Acceptable. Skip optimization.

8. **Bump cache budget** modestly for safety:
   ```python
   QPixmapCache.setCacheLimit(20 * 1024)   # 20 MB (kilobytes!)
   ```
   Place once at module import time or in `__init__`.

9. Smoke test:
   - Run app with at least 5 rows that have `thumbnail_path` and 1 with `None`.
   - Expect: thumbnails render for the 5; placeholder shows for the 1.
   - Scroll up/down rapidly — no flicker, no rebuild.

## Todo List

- [ ] Re-index `_COL_*` constants and `_DEFAULT_WIDTHS`.
- [ ] Update `_HEADERS` tuple.
- [ ] Add `LibraryThumbnailDelegate` (inline or new module).
- [ ] Build a placeholder QPixmap.
- [ ] Install delegate + fixed column width + row height bump.
- [ ] Update `_render_table` to set a thumbnail-column item with path on UserRole.
- [ ] Set `QPixmapCache.setCacheLimit(20480)` (20 MB).
- [ ] Smoke test with mixed available/missing thumbs.
- [ ] Confirm context menu still resolves the record (uses `_COL_TITLE`).

## Success Criteria

- Library renders 6 columns; column 0 shows ~64×36 thumbnails.
- Rows without `thumbnail_path` show a flat gray placeholder.
- Row context menu, sort, and filter all behave as before.
- Scrolling 10k synthetic rows stays interactive (≥30 FPS subjective).

## Risks

| Risk | Mitigation |
|---|---|
| Off-by-one column references elsewhere in `library_panel.py` | Strict use of `_COL_*` constants; grep for hardcoded `0`, `1`, `2` post-change. |
| Delegate paints over selection highlight | Call `super().paint()` first (or draw selection bg manually) — easy fix if observed. |
| Webp fails to decode on some Qt builds | `pix.isNull()` → placeholder; surfaced as visible gap (not crash). |
| Default `QPixmapCache` size too small for working set | Bump to 20 MB; revisit if perf regressions seen. |

## Security Considerations

`QPixmap(path)` reads arbitrary local files at recorded paths. Path comes from `_resolve_thumbnail_sidecar` which only inspects sibling files of yt-dlp output → trusted source. No user-supplied path is fed in.

## Next Steps

→ Phase 4 reuses the same QPixmapCache to render the large preview-pane thumbnail.
