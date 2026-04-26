"""History tab — browses persisted HistoryRecord rows with stats + actions.

Top-level tab. Refreshes on `engine.history_changed` (Phase 07 wiring) and on
`showEvent`. Right-click row menu emits Qt signals; MainWindow wires them to
engine actions (re-download, remove from history).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import HistoryRecord, load_history_records

_HEADERS = ("Title", "Platform", "Uploader", "Quality", "Size", "Date", "Path")
_PLATFORM_OPTIONS = (("All", None), ("TikTok", "tiktok"), ("Facebook", "facebook"))
_TOP_UPLOADER_LIMIT = 5


def _format_size(size_bytes: int | None) -> str:
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    val = float(size_bytes)
    idx = 0
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:.1f} {units[idx]}"


def _format_date(iso: str | None) -> str:
    if not iso:
        return "—"
    # Trim seconds tz noise; keep "YYYY-MM-DD HH:MM" if parseable.
    date_part, _, rest = iso.partition("T")
    time_part = rest.split("+", 1)[0].split("-", 1)[0]
    return f"{date_part} {time_part[:5]}".strip() if rest else date_part


def _open_path(path: str) -> bool:
    """Open ``path`` in the OS default handler. Returns False if missing."""
    if not path or not os.path.exists(path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except OSError:
        return False


class HistoryTab(QWidget):
    """4th top-level tab — full HistoryRecord list with search + actions."""

    redownload_requested = Signal(str)            # url
    remove_history_requested = Signal(str)        # video_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[HistoryRecord] = []

        layout = QVBoxLayout(self)

        # Filter row.
        filters = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, uploader, or URL...")
        filters.addWidget(self.search_input, stretch=1)

        self.platform_combo = QComboBox()
        for label, _value in _PLATFORM_OPTIONS:
            self.platform_combo.addItem(label, _value)
        filters.addWidget(self.platform_combo)
        layout.addLayout(filters)

        # Stats row.
        self.stats_label = QLabel("")
        layout.addWidget(self.stats_label)

        # Table.
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.table)

        # Debounced search filter (200 ms).
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filters)
        self.search_input.textChanged.connect(lambda _t: self._search_timer.start())
        self.platform_combo.currentIndexChanged.connect(lambda _i: self._apply_filters())

    # --- public API ---------------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Re-read history file, recompute stats, repopulate table."""
        self._records = load_history_records()
        self._render_stats(self._records)
        self._apply_filters()

    def showEvent(self, event):  # noqa: D401 (Qt naming)
        """Refresh on tab-show so reopening reflects latest state."""
        super().showEvent(event)
        self.refresh()

    # --- filtering / rendering ----------------------------------------------------

    def _apply_filters(self) -> None:
        needle = self.search_input.text().strip().lower()
        platform_value = self.platform_combo.currentData()
        filtered = [r for r in self._records if self._matches(r, needle, platform_value)]
        self._render_table(filtered)

    @staticmethod
    def _matches(rec: HistoryRecord, needle: str, platform: str | None) -> bool:
        if platform and rec.platform != platform:
            return False
        if not needle:
            return True
        haystack = " ".join(filter(None, [rec.title, rec.uploader, rec.url])).lower()
        return needle in haystack

    def _render_table(self, records: list[HistoryRecord]) -> None:
        self.table.setRowCount(0)
        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(rec.title or "—"))
            self.table.setItem(row, 1, QTableWidgetItem(rec.platform or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(rec.uploader or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(rec.quality or "—"))
            self.table.setItem(row, 4, QTableWidgetItem(_format_size(rec.size_bytes)))
            self.table.setItem(row, 5, QTableWidgetItem(_format_date(rec.downloaded_at)))
            self.table.setItem(row, 6, QTableWidgetItem(rec.file_path or "—"))
            # Stash record on first cell for context menu lookup.
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, rec)

    def _render_stats(self, records: list[HistoryRecord]) -> None:
        total = len(records)
        size = sum(r.size_bytes or 0 for r in records)
        by_platform = Counter(r.platform or "unknown" for r in records)
        top_uploaders = Counter(r.uploader for r in records if r.uploader).most_common(_TOP_UPLOADER_LIMIT)

        platform_summary = " | ".join(
            f"{p}: {n}" for p, n in sorted(by_platform.items())
        ) or "—"
        top_summary = ", ".join(f"{u}({n})" for u, n in top_uploaders) or "—"
        self.stats_label.setText(
            f"Total: {total} | Size: {_format_size(size)} | "
            f"Platforms: {platform_summary} | Top: {top_summary}"
        )

    # --- context menu -------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        item = self.table.item(row, 0)
        rec: HistoryRecord | None = item.data(Qt.ItemDataRole.UserRole) if item else None
        if rec is None:
            return

        menu = QMenu(self)
        open_file_act = menu.addAction("Open file")
        open_folder_act = menu.addAction("Open containing folder")
        redownload_act = menu.addAction("Re-download")
        copy_url_act = menu.addAction("Copy URL")
        remove_act = menu.addAction("Remove from history")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action is open_file_act:
            if not _open_path(rec.file_path or ""):
                self.stats_label.setText("File no longer exists at recorded path.")
        elif action is open_folder_act:
            folder = os.path.dirname(rec.file_path) if rec.file_path else ""
            if not _open_path(folder):
                self.stats_label.setText("Folder no longer exists at recorded path.")
        elif action is redownload_act:
            if rec.url:
                self.redownload_requested.emit(rec.url)
        elif action is copy_url_act:
            if rec.url:
                clipboard = QGuiApplication.clipboard()
                if clipboard:
                    clipboard.setText(rec.url)
        elif action is remove_act:
            self.remove_history_requested.emit(rec.video_id)
