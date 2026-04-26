"""Shared widget logic for TikTok and Facebook browser sub-panels.

Subclasses implement ``_create_fetcher`` to return the platform-specific
QThread fetcher. Common UX (URL input, video table with checkboxes, select
all/none, download-selected) lives here.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from channel_fetcher import VideoInfo

_HEADERS = ("", "Title", "Duration", "Quality", "Views", "Date")


class BaseBrowserPanel(QWidget):
    """Base panel with URL input + video table + select/download controls."""

    download_requested = Signal(list)  # list[str] of video URLs

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fetcher = None
        self._videos: list[VideoInfo] = []

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(placeholder)
        self.url_input.returnPressed.connect(self._on_browse)
        top.addWidget(self.url_input, stretch=1)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._on_browse)
        top.addWidget(self.browse_btn)
        layout.addLayout(top)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        bottom = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        bottom.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        bottom.addWidget(self.deselect_all_btn)

        bottom.addStretch()

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.clicked.connect(self._on_download)
        bottom.addWidget(self.download_btn)
        layout.addLayout(bottom)

    # --- subclass extension point -------------------------------------------------

    def _create_fetcher(self, url: str):
        """Return a QThread fetcher for ``url`` or None if unsupported.

        Subclass implementations may also call ``self.status_label.setText(...)``
        with a precondition error and return None to short-circuit.
        """
        raise NotImplementedError

    def _start_status_text(self) -> str:
        return "Fetching videos..."

    # --- shared behavior ----------------------------------------------------------

    def _on_browse(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return

        if self._fetcher is not None and self._fetcher.isRunning():
            self._fetcher.cancel()
            self._fetcher.wait()

        self._videos.clear()
        self.table.setRowCount(0)
        self.browse_btn.setEnabled(False)

        fetcher = self._create_fetcher(url)
        if fetcher is None:
            self.browse_btn.setEnabled(True)
            return

        self.status_label.setText(self._start_status_text())
        self._fetcher = fetcher
        fetcher.video_found.connect(self._on_video_found)
        fetcher.error.connect(self._on_error)
        fetcher.finished_fetch.connect(self._on_fetch_done)
        fetcher.start()

    @Slot(object)
    def _on_video_found(self, video: VideoInfo) -> None:
        self._videos.append(video)
        row = self.table.rowCount()
        self.table.insertRow(row)

        cb = QCheckBox()
        cb.setChecked(True)
        self.table.setCellWidget(row, 0, cb)

        self.table.setItem(row, 1, QTableWidgetItem(video.title))
        dur = self._format_duration(video.duration) if video.duration else "—"
        self.table.setItem(row, 2, QTableWidgetItem(dur))
        self.table.setItem(row, 3, QTableWidgetItem(video.quality or "—"))
        views = f"{video.view_count:,}" if video.view_count else "—"
        self.table.setItem(row, 4, QTableWidgetItem(views))
        date = self._format_date(video.upload_date) if video.upload_date else "—"
        self.table.setItem(row, 5, QTableWidgetItem(date))

        self.status_label.setText(f"Found {len(self._videos)} videos...")

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self.status_label.setText(f"Error: {msg}")

    @Slot(int)
    def _on_fetch_done(self, total: int) -> None:
        self.browse_btn.setEnabled(True)
        self.status_label.setText(f"Found {total} videos")

    def _select_all(self) -> None:
        self._set_all_checks(True)

    def _deselect_all(self) -> None:
        self._set_all_checks(False)

    def _set_all_checks(self, value: bool) -> None:
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(value)

    def _on_download(self) -> None:
        urls: list[str] = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb and cb.isChecked():
                urls.append(self._videos[row].url)
        if urls:
            self.download_requested.emit(urls)

    @staticmethod
    def _format_duration(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"

    @staticmethod
    def _format_date(date_str: str) -> str:
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str
