# Phase 4 — Library Preview Pane (3-way Splitter)

**Status:** pending · **Priority:** P1 · **Effort:** M (~1.5h) · **Risk:** Low

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Files: `gui/library_panel.py:131` (splitter setup), `gui/library_panel.py:167-170` (table selection wiring).
- Depends on: Phase 1 (schema), Phase 2 (data), Phase 3 (delegate already loads pixmaps).

## Goal

Convert the existing 2-pane Library splitter into a 3-pane horizontal splitter: `[uploader sidebar | filter+table | preview pane]`. Build the preview-pane widget showing a large thumbnail, key metadata, and the full description. Wire it to update on table-row selection.

## Key Insights

- The splitter is already horizontal at line 131 — we add a third widget instead of re-creating it.
- Selection signal: `QTableWidget.itemSelectionChanged` fires once per selection change. Pull the current row → look up the `HistoryRecord` from `_COL_TITLE` UserRole (already attached at line 388).
- Description widget = `QTextEdit` read-only with word-wrap. For long FB descriptions it scrolls naturally.
- Reuse `QPixmapCache` from Phase 3 for the preview-pane thumbnail (different size key — pre-pend `"large:"` to the path).
- No buttons in preview — context menu on the table row already handles open file / open folder / re-download / copy URL / remove.

## Requirements

- 3-pane horizontal splitter; existing stretch factors 1:3 → new ratios e.g. 1:3:2.
- Preview pane shows:
  - Large thumbnail (~360 × 200 px), centered, scaled with `KeepAspectRatio`.
  - Title (bold, ~14pt), wraps over multiple lines.
  - Uploader (with "@" if TikTok handle).
  - Date (formatted), Quality, Size (human-readable).
  - URL (selectable).
  - Description (read-only, scrollable, word-wrapped).
- When **no row is selected** → empty state: greyed text "Select a video to see details".
- When `record.thumbnail_path is None` or unreadable → placeholder fills the thumbnail area.
- When `record.description is None / ""` → italic "(No description)".
- Pane **collapsible** via the splitter's drag handle (no separate toggle button — YAGNI).

## Architecture

```
QSplitter (Qt.Horizontal)
   ├─ uploader sidebar     [QListWidget]
   ├─ right_pane            [QWidget: filter row + table]
   └─ preview_pane          [LibraryPreviewPane (new widget)]
                                ├─ QLabel  thumbnail (scaled pixmap)
                                ├─ QLabel  title (bold, word-wrap)
                                ├─ key/value grid (uploader, date, quality, size)
                                ├─ QLabel  url (selectable, elided)
                                └─ QTextEdit description (read-only, scrollable)
```

Selection → `_on_selection_changed()` → `preview_pane.set_record(record)` → widget updates labels & description.

## Related Code Files

**Modify:**
- `gui/library_panel.py` — extend splitter, instantiate preview pane, wire selection signal.

**New file:**
- `gui/library_preview_pane.py` — the `LibraryPreviewPane(QWidget)` class. Kebab-case naming consistent with sibling modules (`library_panel.py`, `download_table.py`).

**Read for context:**
- `gui/_history_helpers.py` — `format_size`, `format_date` helpers (already used in panel).

## Implementation Steps

1. **Create `gui/library_preview_pane.py`** with a `LibraryPreviewPane(QWidget)` class:
   ```python
   from __future__ import annotations
   from PySide6.QtCore import Qt
   from PySide6.QtGui import QPixmap, QPixmapCache
   from PySide6.QtWidgets import (
       QFormLayout, QLabel, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
   )
   from config import HistoryRecord
   from gui._history_helpers import format_date, format_size

   _PREVIEW_W, _PREVIEW_H = 360, 200

   class LibraryPreviewPane(QWidget):
       """Right-side detail pane for the Library tab. Stateless beyond the current record."""

       def __init__(self, placeholder: QPixmap, parent: QWidget | None = None) -> None:
           super().__init__(parent)
           self._placeholder = placeholder
           layout = QVBoxLayout(self)

           self.thumb = QLabel()
           self.thumb.setFixedSize(_PREVIEW_W, _PREVIEW_H)
           self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
           self.thumb.setStyleSheet("background:#1c1c1c; border-radius:4px;")
           layout.addWidget(self.thumb, alignment=Qt.AlignmentFlag.AlignHCenter)

           self.title_label = QLabel("Select a video to see details")
           self.title_label.setWordWrap(True)
           f = self.title_label.font()
           f.setPointSize(f.pointSize() + 2)
           f.setBold(True)
           self.title_label.setFont(f)
           layout.addWidget(self.title_label)

           form = QFormLayout()
           form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
           self.uploader_label = QLabel("—")
           self.date_label = QLabel("—")
           self.quality_label = QLabel("—")
           self.size_label = QLabel("—")
           self.url_label = QLabel("—")
           self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
           self.url_label.setWordWrap(True)
           form.addRow("Uploader", self.uploader_label)
           form.addRow("Date", self.date_label)
           form.addRow("Quality", self.quality_label)
           form.addRow("Size", self.size_label)
           form.addRow("URL", self.url_label)
           layout.addLayout(form)

           self.description = QTextEdit()
           self.description.setReadOnly(True)
           self.description.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
           self.description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
           self.description.setPlaceholderText("(No description)")
           layout.addWidget(self.description, stretch=1)

           self.set_record(None)

       def set_record(self, rec: HistoryRecord | None) -> None:
           if rec is None:
               self.thumb.setPixmap(self._placeholder)
               self.title_label.setText("Select a video to see details")
               for lbl in (self.uploader_label, self.date_label,
                          self.quality_label, self.size_label, self.url_label):
                   lbl.setText("—")
               self.description.clear()
               return
           self.thumb.setPixmap(self._lookup(rec.thumbnail_path))
           self.title_label.setText(rec.title or "—")
           self.uploader_label.setText(rec.uploader or "—")
           self.date_label.setText(format_date(rec.downloaded_at))
           self.quality_label.setText(rec.quality or "—")
           self.size_label.setText(format_size(rec.size_bytes))
           self.url_label.setText(rec.url or "—")
           self.description.setPlainText(rec.description or "")

       def _lookup(self, path: str | None) -> QPixmap:
           if not path:
               return self._placeholder
           key = f"large:{path}"
           cached = QPixmapCache.find(key)
           if cached is not None:
               return cached
           pix = QPixmap(path)
           if pix.isNull():
               return self._placeholder
           pix = pix.scaled(_PREVIEW_W, _PREVIEW_H,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
           QPixmapCache.insert(key, pix)
           return pix
   ```

2. **Update `gui/library_panel.py`** imports:
   ```python
   from gui.library_preview_pane import LibraryPreviewPane
   ```

3. **Add the third splitter pane** after the existing `splitter.addWidget(right)` (line 173):
   ```python
   placeholder = QPixmap(_PREVIEW_W, _PREVIEW_H)
   placeholder.fill(QColor("#1c1c1c"))
   self.preview_pane = LibraryPreviewPane(placeholder, self)
   splitter.addWidget(self.preview_pane)
   splitter.setStretchFactor(0, 1)
   splitter.setStretchFactor(1, 3)
   splitter.setStretchFactor(2, 2)
   ```
   (Replace the existing two `setStretchFactor` calls with three.)

4. **Wire selection** after the table is built:
   ```python
   self.table.itemSelectionChanged.connect(self._on_selection_changed)
   ```

5. **Selection handler** (new private method):
   ```python
   def _on_selection_changed(self) -> None:
       rows = self.table.selectionModel().selectedRows()
       if not rows:
           self.preview_pane.set_record(None)
           return
       row = rows[0].row()
       item = self.table.item(row, _COL_TITLE)
       rec = item.data(Qt.ItemDataRole.UserRole) if item else None
       self.preview_pane.set_record(rec if isinstance(rec, HistoryRecord) else None)
   ```

6. **Smoke test:**
   - Click rows → preview pane updates immediately.
   - Click empty area → pane resets to "Select a video".
   - Drag splitter handle to collapse the preview — table fills the freed space.
   - Verify long Facebook description scrolls inside the description widget.

## Todo List

- [ ] Create `gui/library_preview_pane.py` with `LibraryPreviewPane`.
- [ ] Import + instantiate in `LibraryPanel.__init__`.
- [ ] Add to splitter as the 3rd widget; set 3 stretch factors.
- [ ] Connect `itemSelectionChanged` → `_on_selection_changed`.
- [ ] Implement `_on_selection_changed` resolving the `HistoryRecord` from `_COL_TITLE`.
- [ ] Smoke test: select / deselect / long description / missing thumb.

## Success Criteria

- Selecting any row populates: thumbnail, title, uploader, date, quality, size, URL, description.
- Deselecting (click empty cell or use ESC) resets the pane.
- Long descriptions scroll within the description widget; pane height stable.
- Splitter is draggable; preview pane can be collapsed to width 0 and restored.
- No memory regression after selecting 100 distinct rows in a row (cache works).

## Risks

| Risk | Mitigation |
|---|---|
| Pane crowds narrow windows | Splitter handle lets user collapse it; default ratio favors the table. Future Phase: add menu toggle if reported. |
| Selection signal fires on filter rebuild → flickers pane | `_render_table` clears rows → selection cleared → pane resets to empty (acceptable). |
| Large preview pixmaps dominate cache budget | 20 MB cache holds ~30 × 360×200 large + many 64×36 — fine. |
| Cyclic import (panel ↔ preview pane) | Preview pane only imports `HistoryRecord` and helpers; no panel reference needed. |

## Security Considerations

Same as Phase 3 — `QPixmap(path)` only consumes paths originating from yt-dlp sidecar resolution.

## Next Steps

→ Phase 5 — search box also queries description text so the new metadata is discoverable.
