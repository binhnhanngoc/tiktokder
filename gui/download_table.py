"""Download queue table with per-row progress bars and status indicators."""

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QColor
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
    QMessageBox,
)

from app_state import QueueItemState
from downloader import DownloadResult
from gui.icons import icon
from gui.tokens import token


# Status constants
STATUS_QUEUED = "Queued"
STATUS_DOWNLOADING = "Downloading"
STATUS_COMPLETE = "Complete"
STATUS_FAILED = "Failed"
STATUS_SKIPPED = "Skipped"
STATUS_CANCELLED = "Cancelled"

# Map status → semantic token name. Resolved per-call so a live theme switch
# repaints the next ``_set_status`` invocation with the new palette.
_STATUS_TOKENS = {
    STATUS_QUEUED: "text.muted",
    STATUS_DOWNLOADING: "state.warning",
    STATUS_COMPLETE: "state.success",
    STATUS_FAILED: "state.error",
    STATUS_SKIPPED: "text.muted",
    STATUS_CANCELLED: "text.muted",
}


class DownloadTableWidget(QWidget):
    """Table showing download queue with progress bars and context menu."""

    # Emitted when the user requests a retry for one or more URLs.
    # Parent (MainWindow) connects this to DownloadEngine.retry_urls.
    retry_requested = Signal(list)

    # Emitted when the user requests a forced re-download (bypass history,
    # overwrite existing files). Parent connects to retry_urls(force=True).
    force_download_requested = Signal(list)

    # Emitted when 'Clear All' is invoked. Parent should cancel any active
    # downloads and drop dedup tracking on the engine so URLs can be re-added.
    clear_all_requested = Signal(list)  # list of URLs being cleared

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._url_to_row: dict[str, int] = {}
        self._row_data: dict[int, dict] = {}  # row -> {url, status, filepath}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.setIcon(icon("mdi6.broom"))
        self.clear_btn.clicked.connect(self._clear_completed)
        toolbar.addWidget(self.clear_btn)

        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setIcon(icon("mdi6.delete-sweep"))
        self.clear_all_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(self.clear_all_btn)

        self.retry_failed_btn = QPushButton("Retry Failed")
        self.retry_failed_btn.setIcon(icon("mdi6.refresh"))
        self.retry_failed_btn.clicked.connect(self._retry_all_failed)
        toolbar.addWidget(self.retry_failed_btn)

        self.cancel_all_btn = QPushButton("Cancel All")
        self.cancel_all_btn.setIcon(icon("mdi6.stop"))
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
        """Set status cell with semantic-token-resolved color."""
        item = QTableWidgetItem(status)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        token_name = _STATUS_TOKENS.get(status, "text.muted")
        item.setForeground(QColor(token(token_name)))
        self.table.setItem(row, 1, item)
        if row in self._row_data:
            self._row_data[row]["status"] = status

    def _show_context_menu(self, pos) -> None:
        """Right-click context menu for table rows."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        data = self._row_data.get(row, {})
        status = data.get("status")
        url = data.get("url", "")
        menu = QMenu(self)

        # Copy URL — always available.
        copy_action = menu.addAction("Copy URL")
        copy_action.triggered.connect(lambda: self._copy_url(url))

        # Retry: re-runs the download for terminal-state rows. Skipped rows
        # without a force flag would just be skipped again, so only offer
        # Retry where re-attempting can change the outcome (Failed/Cancelled).
        if status in (STATUS_FAILED, STATUS_CANCELLED):
            retry_action = menu.addAction("Retry")
            retry_action.triggered.connect(lambda: self._retry_url(url))

        # Force Download: bypasses history and overwrites files. Useful for
        # rows that landed in Skipped/Complete (already in history) or for
        # forcing a clean replacement of a previous failure.
        if status in (STATUS_FAILED, STATUS_CANCELLED, STATUS_SKIPPED, STATUS_COMPLETE):
            force_action = menu.addAction("Force Download")
            force_action.triggered.connect(lambda: self._force_download(url))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_url(self, url: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(url)

    def _reset_row(self, url: str) -> bool:
        """Reset a row's status to Queued and zero its progress bar. Returns
        True if the row was found and reset, False otherwise.
        """
        row = self._url_to_row.get(url)
        if row is None:
            return False
        self._set_status(row, STATUS_QUEUED)
        bar = self.table.cellWidget(row, 2)
        if bar:
            bar.setValue(0)
        return True

    def _retry_url(self, url: str) -> None:
        """Reset a failed/cancelled row to Queued and emit retry_requested."""
        if self._reset_row(url):
            self.retry_requested.emit([url])

    def _force_download(self, url: str) -> None:
        """Reset row and request a forced re-download (bypass history)."""
        if self._reset_row(url):
            self.force_download_requested.emit([url])

    def _retry_all_failed(self) -> None:
        """Bulk retry every Failed/Cancelled row in the table."""
        urls: list[str] = []
        for row, data in self._row_data.items():
            if data.get("status") in (STATUS_FAILED, STATUS_CANCELLED):
                url = data.get("url")
                if not url:
                    continue
                urls.append(url)
                self._set_status(row, STATUS_QUEUED)
                bar = self.table.cellWidget(row, 2)
                if bar:
                    bar.setValue(0)
        if urls:
            self.retry_requested.emit(urls)

    def _clear_all(self) -> None:
        """Confirm, then clear every row from the table.

        Emits clear_all_requested with all URLs so the engine can cancel
        in-flight workers and drop dedup tracking.
        """
        if self.table.rowCount() == 0:
            return
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Remove all downloads from the list?\n"
            "Active downloads will be cancelled.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        urls = [d.get("url") for d in self._row_data.values() if d.get("url")]
        self.table.setRowCount(0)
        self._url_to_row.clear()
        self._row_data.clear()
        self.clear_all_requested.emit(urls)

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

    # --- persistence --------------------------------------------------------------

    def snapshot(self) -> list[QueueItemState]:
        """Return a serializable snapshot of every row, in display order."""
        items: list[QueueItemState] = []
        for row in range(self.table.rowCount()):
            data = self._row_data.get(row, {})
            url = data.get("url")
            if not url:
                continue
            title_item = self.table.item(row, 0)
            title = title_item.text() if title_item else None
            # Title cell defaults to URL — collapse that back to None so on
            # restore we don't display the URL twice.
            if title == url:
                title = None
            items.append(
                QueueItemState(
                    url=url,
                    status=data.get("status", STATUS_QUEUED),
                    title=title,
                )
            )
        return items

    def load_from_state(self, items: list[QueueItemState]) -> None:
        """Repopulate the table from a persisted snapshot.

        In-flight statuses (Downloading) are downgraded to Cancelled — the
        worker died with the previous app instance, so the row is no longer
        actively making progress.
        """
        for item in items:
            url = item.url
            if not url or url in self._url_to_row:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._url_to_row[url] = row

            display_title = item.title or url
            title_item = QTableWidgetItem(display_title)
            title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, title_item)

            status = item.status
            if status == STATUS_DOWNLOADING:
                status = STATUS_CANCELLED
            elif status not in _STATUS_TOKENS:
                status = STATUS_QUEUED
            self._row_data[row] = {"url": url, "status": status, "filepath": None}
            self._set_status(row, status)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(100 if status == STATUS_COMPLETE else 0)
            self.table.setCellWidget(row, 2, bar)

            self.table.setItem(row, 3, QTableWidgetItem("—"))
