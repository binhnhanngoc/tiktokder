"""Download queue table with per-row progress bars and status indicators."""

from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QPushButton,
    QHeaderView,
    QMenu,
    QApplication,
)

from downloader import DownloadResult


# Status constants
STATUS_QUEUED = "Queued"
STATUS_DOWNLOADING = "Downloading"
STATUS_COMPLETE = "Complete"
STATUS_FAILED = "Failed"
STATUS_SKIPPED = "Skipped"
STATUS_CANCELLED = "Cancelled"

# Color map for status text
STATUS_COLORS = {
    STATUS_QUEUED: "#888888",
    STATUS_DOWNLOADING: "#d4a017",
    STATUS_COMPLETE: "#2ecc71",
    STATUS_FAILED: "#e74c3c",
    STATUS_SKIPPED: "#95a5a6",
    STATUS_CANCELLED: "#95a5a6",
}


class DownloadTableWidget(QWidget):
    """Table showing download queue with progress bars and context menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._url_to_row: dict[str, int] = {}
        self._row_data: dict[int, dict] = {}  # row -> {url, status, filepath}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.clicked.connect(self._clear_completed)
        toolbar.addWidget(self.clear_btn)

        self.cancel_all_btn = QPushButton("Cancel All")
        toolbar.addWidget(self.cancel_all_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Title", "Status", "Progress", "Size"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

    def add_download(self, url: str) -> None:
        """Add a new URL to the download table with Queued status."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._url_to_row[url] = row
        self._row_data[row] = {"url": url, "status": STATUS_QUEUED, "filepath": None}

        # Title (show URL initially, updated when download finishes)
        title_item = QTableWidgetItem(url)
        title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, title_item)

        # Status
        self._set_status(row, STATUS_QUEUED)

        # Progress bar
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        self.table.setCellWidget(row, 2, bar)

        # Size placeholder
        self.table.setItem(row, 3, QTableWidgetItem("—"))

    @Slot(str)
    def on_download_started(self, url: str) -> None:
        """Update row status to Downloading."""
        row = self._url_to_row.get(url)
        if row is not None:
            self._set_status(row, STATUS_DOWNLOADING)

    @Slot(str, float)
    def on_download_progress(self, url: str, percent: float) -> None:
        """Update progress bar for a URL."""
        row = self._url_to_row.get(url)
        if row is not None:
            bar = self.table.cellWidget(row, 2)
            if bar:
                bar.setValue(int(percent))

    @Slot(str, object)
    def on_download_finished(self, url: str, result: DownloadResult) -> None:
        """Update row with final status and title."""
        row = self._url_to_row.get(url)
        if row is None:
            return

        if result.skipped:
            self._set_status(row, STATUS_SKIPPED)
        elif result.success:
            self._set_status(row, STATUS_COMPLETE)
            bar = self.table.cellWidget(row, 2)
            if bar:
                bar.setValue(100)
        else:
            self._set_status(row, STATUS_FAILED)

        # Update title if available
        if result.title:
            self.table.item(row, 0).setText(result.title)

        self._row_data[row]["status"] = (
            STATUS_SKIPPED if result.skipped
            else STATUS_COMPLETE if result.success
            else STATUS_FAILED
        )

    def _set_status(self, row: int, status: str) -> None:
        """Set status cell with color."""
        item = QTableWidgetItem(status)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        color = STATUS_COLORS.get(status, "#888888")
        item.setForeground(Qt.GlobalColor.white)
        # Use simple text coloring
        from PySide6.QtGui import QColor
        item.setForeground(QColor(color))
        self.table.setItem(row, 1, item)
        if row in self._row_data:
            self._row_data[row]["status"] = status

    def _show_context_menu(self, pos) -> None:
        """Right-click context menu for table rows."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        data = self._row_data.get(row, {})
        menu = QMenu(self)

        # Copy URL
        copy_action = menu.addAction("Copy URL")
        copy_action.triggered.connect(lambda: self._copy_url(data.get("url", "")))

        # Retry (only for failed)
        if data.get("status") == STATUS_FAILED:
            retry_action = menu.addAction("Retry")
            retry_action.triggered.connect(lambda: self._retry_url(data.get("url", "")))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_url(self, url: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(url)

    def _retry_url(self, url: str) -> None:
        """Re-add a failed URL. Parent should connect this to engine."""
        # Remove old row, re-add
        row = self._url_to_row.get(url)
        if row is not None:
            self._set_status(row, STATUS_QUEUED)
            bar = self.table.cellWidget(row, 2)
            if bar:
                bar.setValue(0)

    def _clear_completed(self) -> None:
        """Remove completed and skipped rows from table."""
        rows_to_remove = []
        for row in range(self.table.rowCount()):
            data = self._row_data.get(row, {})
            if data.get("status") in (STATUS_COMPLETE, STATUS_SKIPPED):
                rows_to_remove.append(row)

        # Remove from bottom up to preserve row indices
        for row in reversed(rows_to_remove):
            url = self._row_data[row].get("url")
            self.table.removeRow(row)
            if url and url in self._url_to_row:
                del self._url_to_row[url]
            if row in self._row_data:
                del self._row_data[row]

        # Rebuild mappings after removal
        self._rebuild_mappings()

    def _rebuild_mappings(self) -> None:
        """Rebuild url-to-row and row-data mappings after row removal."""
        new_url_to_row = {}
        new_row_data = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            status_item = self.table.item(row, 1)
            if item:
                url = None
                # Find URL from old mappings
                for u, r in self._url_to_row.items():
                    if r == row:
                        url = u
                        break
                # Fallback: check remaining old data
                if not url:
                    for old_row, data in self._row_data.items():
                        if data.get("url") and item.text() in (data["url"], data.get("title", "")):
                            url = data["url"]
                            break
                if url:
                    new_url_to_row[url] = row
                    new_row_data[row] = {"url": url, "status": status_item.text() if status_item else STATUS_QUEUED}

        self._url_to_row = new_url_to_row
        self._row_data = new_row_data

    def get_completed_count(self) -> int:
        """Return number of completed downloads."""
        return sum(1 for d in self._row_data.values() if d.get("status") == STATUS_COMPLETE)

    def get_total_count(self) -> int:
        """Return total number of downloads in table."""
        return self.table.rowCount()
