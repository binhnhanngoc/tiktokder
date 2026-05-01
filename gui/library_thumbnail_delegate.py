"""Lazy-paint thumbnail delegate for the Library table column.

Reads the sidecar thumbnail path from ``Qt.ItemDataRole.UserRole`` on the
column-0 cell, decodes the image on first paint, and caches the result via
``QPixmapCache`` so re-scrolls don't re-decode. Missing or unreadable files
fall back to a flat placeholder pixmap.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QPixmapCache
from PySide6.QtWidgets import QStyledItemDelegate

# Cell budget — generous enough that 16:9 vertical (TikTok) and horizontal
# (Facebook) thumbnails both fit without distortion.
THUMB_W, THUMB_H = 64, 36
_CELL_PAD_X, _CELL_PAD_Y = 16, 8


def load_thumbnail_pixmap(path: str) -> QPixmap:
    """Decode ``path`` as a QPixmap, sniffing the format from magic bytes.

    ``QPixmap(path)`` picks a decoder by file extension, which fails on
    TikTok's ``.image`` sidecars (real JPEG bytes wrapped in a generic
    extension). Reading the raw bytes and calling ``loadFromData`` lets Qt's
    image plugins detect the format from the header — JPEG, WebP and PNG all
    decode regardless of what the file is named.

    Returns a null QPixmap on any failure; callers should fall back to a
    placeholder via ``QPixmap.isNull()``.
    """
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return QPixmap()
    pix = QPixmap()
    pix.loadFromData(data)
    return pix


class LibraryThumbnailDelegate(QStyledItemDelegate):
    """Delegate that paints a cached thumbnail from a sidecar path."""

    def __init__(self, placeholder: QPixmap, parent=None) -> None:
        super().__init__(parent)
        self._placeholder = placeholder

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 — Qt API
        return QSize(THUMB_W + _CELL_PAD_X, THUMB_H + _CELL_PAD_Y)

    def paint(self, painter, option, index) -> None:
        # Let the base class paint the selection / hover background first so
        # our pixmap doesn't clobber the highlight rectangle.
        super().paint(painter, option, index)
        path = index.data(Qt.ItemDataRole.UserRole)
        pix = self._lookup(path)
        cx = option.rect.x() + (option.rect.width() - pix.width()) // 2
        cy = option.rect.y() + (option.rect.height() - pix.height()) // 2
        painter.drawPixmap(cx, cy, pix)

    def _lookup(self, path: str | None) -> QPixmap:
        if not path:
            return self._placeholder
        cached = QPixmapCache.find(path)
        if cached is not None:
            return cached
        pix = load_thumbnail_pixmap(path)
        if pix.isNull():
            return self._placeholder
        scaled = pix.scaled(
            THUMB_W,
            THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        QPixmapCache.insert(path, scaled)
        return scaled
