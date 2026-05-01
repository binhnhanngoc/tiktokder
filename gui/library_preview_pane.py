"""Right-side preview pane for the Library tab.

Stateless beyond the current selected record. Reuses ``QPixmapCache`` so the
large preview thumbnail isn't re-decoded every time the user clicks back to a
previously-shown row. The cache key is prefixed with ``large:`` to avoid
collision with the small table-column thumbnail of the same path.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPixmapCache
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import HistoryRecord
from gui._history_helpers import format_date, format_size
from gui.library_thumbnail_delegate import load_thumbnail_pixmap

PREVIEW_W, PREVIEW_H = 360, 200
_LARGE_CACHE_PREFIX = "large:"


class LibraryPreviewPane(QWidget):
    """Detail pane: thumbnail + metadata + full description for one record."""

    def __init__(self, placeholder: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._placeholder = placeholder
        layout = QVBoxLayout(self)

        self.thumb = QLabel()
        self.thumb.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("background:#1c1c1c; border-radius:4px;")
        layout.addWidget(self.thumb, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel("Select a video to see details")
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.title_label.setFont(font)
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
        """Populate the pane from ``rec``, or reset it to the empty state."""
        if rec is None:
            self.thumb.setPixmap(self._placeholder)
            self.title_label.setText("Select a video to see details")
            for lbl in (
                self.uploader_label,
                self.date_label,
                self.quality_label,
                self.size_label,
                self.url_label,
            ):
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
        key = f"{_LARGE_CACHE_PREFIX}{path}"
        cached = QPixmapCache.find(key)
        if cached is not None:
            return cached
        pix = load_thumbnail_pixmap(path)
        if pix.isNull():
            return self._placeholder
        scaled = pix.scaled(
            PREVIEW_W,
            PREVIEW_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        QPixmapCache.insert(key, scaled)
        return scaled
