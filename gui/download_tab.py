"""Download tab wrapper: URL input + queue table + drag-drop + import/export.

Sits between MainWindow and the inner widgets so drag-drop and the import/export
buttons live in one place. Emits high-level signals MainWindow forwards to the
DownloadEngine.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.download_table import DownloadTableWidget
from gui.url_input_panel import UrlInputPanel
from url_parser import read_batch_file, validate_url


class DownloadTab(QWidget):
    """Composite widget for the Download tab — handles drag-drop + import/export."""

    urls_dropped = Signal(list)             # list[str] — already validated
    import_requested = Signal(list)         # list[str] from .txt file
    export_requested = Signal(str)          # destination path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)

        self.url_input = UrlInputPanel()
        layout.addWidget(self.url_input)

        # Import/Export toolbar lives above the queue table.
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        self.import_btn = QPushButton("Import URLs...")
        self.import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(self.import_btn)
        self.export_btn = QPushButton("Export URLs...")
        self.export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.download_table = DownloadTableWidget()
        layout.addWidget(self.download_table)

    # --- drag-and-drop ------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: D401, N802
        mime = event.mimeData()
        if mime and (mime.hasUrls() or mime.hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: D401, N802
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return

        urls: list[str] = []
        # File or web URIs.
        for u in mime.urls():
            local = u.toLocalFile()
            if local:
                if local.lower().endswith(".txt"):
                    try:
                        urls.extend(read_batch_file(local))
                    except OSError:
                        continue
                else:
                    # Non-txt local file is unusual on this tab — ignore.
                    continue
            else:
                urls.append(u.toString())

        # Plain-text drops (e.g. URL from a browser address bar).
        if not urls and mime.hasText():
            for line in mime.text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

        valid = [u for u in urls if validate_url(u)]
        if valid:
            self.urls_dropped.emit(valid)
            event.acceptProposedAction()
        else:
            event.ignore()

    # --- import / export ----------------------------------------------------------

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import URL list", "", "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            urls = read_batch_file(path)
        except OSError:
            return
        valid = [u for u in urls if validate_url(u)]
        if valid:
            self.import_requested.emit(valid)

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export URL list", "urls.txt", "Text files (*.txt)"
        )
        if path:
            self.export_requested.emit(path)
