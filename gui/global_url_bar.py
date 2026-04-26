"""Persistent URL bar above the platform tabs.

Accepts pasted/typed URLs and `.txt` drops. Splits text by whitespace,
validates each line, and emits the surviving list — MainWindow groups by
platform and dispatches to per-platform queues.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from gui.icons import icon
from url_parser import read_batch_file, validate_url

_BAR_HEIGHT = 28


class GlobalUrlBar(QWidget):
    """Single URL input bar with drag-drop, shared by both platform tabs."""

    # List of validated URLs (may span platforms — caller groups them).
    urls_submitted = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMaximumHeight(_BAR_HEIGHT + 8)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste URL or drop .txt here — auto-routes by platform")
        self.url_input.setFixedHeight(_BAR_HEIGHT)
        self.url_input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.url_input, stretch=1)

        self.add_btn = QPushButton("Add")
        self.add_btn.setIcon(icon("mdi6.plus"))
        self.add_btn.setFixedHeight(_BAR_HEIGHT)
        self.add_btn.clicked.connect(self._on_submit)
        layout.addWidget(self.add_btn)

    # ── input ─────────────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        text = self.url_input.text().strip()
        if not text:
            return
        urls = [t for t in text.split() if t]
        valid = [u for u in urls if validate_url(u)]
        if valid:
            self.urls_submitted.emit(valid)
            self.url_input.clear()

    # ── drag-drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime and (mime.hasUrls() or mime.hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return

        urls: list[str] = []
        for u in mime.urls():
            local = u.toLocalFile()
            if local and local.lower().endswith(".txt"):
                try:
                    urls.extend(read_batch_file(local))
                except OSError:
                    continue
            elif not local:
                urls.append(u.toString())

        if not urls and mime.hasText():
            for line in mime.text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

        valid = [u for u in urls if validate_url(u)]
        if valid:
            self.urls_submitted.emit(valid)
            event.acceptProposedAction()
        else:
            event.ignore()
