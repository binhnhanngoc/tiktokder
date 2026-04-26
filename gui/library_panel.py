"""Library — uploader sidebar (left) + filtered history table (right).

Per-platform: filters records to `record.platform == self.platform` so the
whole tab is platform-scoped. The Platform column from the legacy HistoryTab
is dropped — redundant under platform-first IA.
"""

from __future__ import annotations

import os
from collections import Counter
from urllib.parse import urlparse

from PySide6.QtCore import QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import HistoryRecord, load_history_records
from gui._history_helpers import (
    format_date,
    format_size,
    open_path,
    reveal_in_file_manager,
)
from saved_channels_store import SavedChannelsStore

_HEADERS = ("Title", "Quality", "Size", "Date", "Path")
_ALL_LABEL = "All"


def _uploader_from_url(url: str | None) -> str | None:
    """Best-effort uploader handle from a saved-channel URL.

    TikTok: ``/@user`` segment. Facebook: first path component.
    Used only for the star marker so misses are silent.
    """
    if not url:
        return None
    try:
        parts = urlparse(url).path.strip("/").split("/")
    except ValueError:
        return None
    if not parts:
        return None
    first = parts[0]
    if first.startswith("@"):
        return first
    return first or None


class LibraryPanel(QWidget):
    """Two-pane Library — uploader sidebar + history table."""

    redownload_requested = Signal(str)         # url
    remove_history_requested = Signal(str)     # video_id

    def __init__(
        self,
        platform: str,
        saved_store: SavedChannelsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.platform = platform
        self.saved_store = saved_store
        self._records: list[HistoryRecord] = []
        self._active_uploader: str | None = None  # None = "All"

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        # Left pane — uploader sidebar.
        self.sidebar = QListWidget()
        self.sidebar.itemClicked.connect(self._on_uploader_clicked)
        splitter.addWidget(self.sidebar)

        # Right pane — search + table.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, URL...")
        right_layout.addWidget(self.search_input)

        self.stats_label = QLabel("")
        right_layout.addWidget(self.stats_label)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        right_layout.addWidget(self.table)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        # Debounced search (200 ms).
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filters)
        self.search_input.textChanged.connect(lambda _t: self._search_timer.start())

    # ── public API ────────────────────────────────────────────────────────

    @Slot()
    def refresh(self) -> None:
        """Re-read history file and rebuild sidebar + table."""
        records = load_history_records()
        self._records = [r for r in records if r.platform == self.platform]
        self._rebuild_sidebar()
        self._apply_filters()

    def set_active_uploader(self, name: str | None) -> None:
        self._active_uploader = name or None
        # Reflect selection in the sidebar.
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == self._active_uploader:
                self.sidebar.setCurrentItem(item)
                break
        self._apply_filters()

    def active_uploader(self) -> str | None:
        return self._active_uploader

    # ── sidebar ───────────────────────────────────────────────────────────

    def _saved_uploader_names(self) -> set[str]:
        """Set of uploader handles derived from saved-channel URLs."""
        names: set[str] = set()
        for ch in self.saved_store.list_all(self.platform):
            handle = _uploader_from_url(ch.url)
            if handle:
                names.add(handle)
        return names

    def _rebuild_sidebar(self) -> None:
        self.sidebar.clear()
        # "All" pseudo-row.
        all_item = QListWidgetItem(f"{_ALL_LABEL} ({len(self._records)})")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        self.sidebar.addItem(all_item)

        counts = Counter(r.uploader for r in self._records if r.uploader)
        starred = self._saved_uploader_names()
        for name, count in counts.most_common():
            label = f"{'★ ' if name in starred else ''}{name} ({count})"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.sidebar.addItem(it)

        # Re-select active uploader if it survived the rebuild.
        if self._active_uploader is None:
            self.sidebar.setCurrentItem(all_item)
        else:
            for i in range(self.sidebar.count()):
                item = self.sidebar.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self._active_uploader:
                    self.sidebar.setCurrentItem(item)
                    break

    @Slot(QListWidgetItem)
    def _on_uploader_clicked(self, item: QListWidgetItem) -> None:
        self._active_uploader = item.data(Qt.ItemDataRole.UserRole)
        self._apply_filters()

    # ── filter / render ───────────────────────────────────────────────────

    def _apply_filters(self) -> None:
        needle = self.search_input.text().strip().lower()
        rows = []
        for r in self._records:
            if self._active_uploader and r.uploader != self._active_uploader:
                continue
            if needle:
                hay = " ".join(filter(None, [r.title, r.uploader, r.url])).lower()
                if needle not in hay:
                    continue
            rows.append(r)
        self._render_table(rows)
        self._render_stats(rows)

    def _render_table(self, records: list[HistoryRecord]) -> None:
        self.table.setRowCount(0)
        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(rec.title or "—"))
            self.table.setItem(row, 1, QTableWidgetItem(rec.quality or "—"))
            self.table.setItem(row, 2, QTableWidgetItem(format_size(rec.size_bytes)))
            self.table.setItem(row, 3, QTableWidgetItem(format_date(rec.downloaded_at)))
            self.table.setItem(row, 4, QTableWidgetItem(rec.file_path or "—"))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, rec)

    def _render_stats(self, records: list[HistoryRecord]) -> None:
        total = len(records)
        size = sum(r.size_bytes or 0 for r in records)
        scope = self._active_uploader or "All uploaders"
        self.stats_label.setText(f"{scope}: {total} items · {format_size(size)}")

    # ── context menu ──────────────────────────────────────────────────────

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
        open_explorer_act = menu.addAction("Open in Explorer")
        open_folder_act = menu.addAction("Open containing folder")
        redownload_act = menu.addAction("Re-download")
        copy_url_act = menu.addAction("Copy URL")
        remove_act = menu.addAction("Remove from history")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action is open_file_act:
            if not open_path(rec.file_path or ""):
                self.stats_label.setText("File no longer exists at recorded path.")
        elif action is open_explorer_act:
            if not reveal_in_file_manager(rec.file_path or ""):
                self.stats_label.setText("File no longer exists at recorded path.")
        elif action is open_folder_act:
            folder = os.path.dirname(rec.file_path) if rec.file_path else ""
            if not open_path(folder):
                self.stats_label.setText("Folder no longer exists at recorded path.")
        elif action is redownload_act:
            if rec.url:
                self.redownload_requested.emit(rec.url)
        elif action is copy_url_act:
            if rec.url:
                clip = QGuiApplication.clipboard()
                if clip:
                    clip.setText(rec.url)
        elif action is remove_act:
            self.remove_history_requested.emit(rec.video_id)
