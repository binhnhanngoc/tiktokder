"""Library — uploader sidebar (left) + filtered/sortable history table (right).

Per-platform: filters records to `record.platform == self.platform` so the
whole tab is platform-scoped. The Platform column from the legacy HistoryTab
is dropped — redundant under platform-first IA.

Sort: header click on any column. Default: Date desc (newest-first). Size
column uses a NumericItem subclass so byte-counts compare numerically rather
than as their human-readable text.

Filters: search box (existing) + uploader sidebar (existing) + a compact
filter row with Quality dropdown, From/To date range (each toggleable), Size
threshold (≥ MB), and Status (Available/Missing — derived via
`os.path.exists`).
"""

from __future__ import annotations

import os
from collections import Counter
from urllib.parse import urlparse

from PySide6.QtCore import QDate, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QPixmap, QPixmapCache
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSpinBox,
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
from gui.library_preview_pane import (
    PREVIEW_H as _PREVIEW_H,
    PREVIEW_W as _PREVIEW_W,
    LibraryPreviewPane,
)
from gui.library_thumbnail_delegate import (
    THUMB_H as _THUMB_H,
    THUMB_W as _THUMB_W,
    LibraryThumbnailDelegate,
)
from saved_channels_store import SavedChannelsStore

# Column 0 header is blank — the icon-only column doesn't need a label.
_HEADERS = ("", "Title", "Quality", "Size", "Date", "Path")
_ALL_LABEL = "All"

# Column indices — single source of truth for sort/render code.
_COL_THUMB = 0
_COL_TITLE = 1
_COL_QUALITY = 2
_COL_SIZE = 3
_COL_DATE = 4
_COL_PATH = 5

# Sensible default widths in px. Path is the stretch column so its number is
# only the lower bound — Qt grows it to fill the panel.
_DEFAULT_WIDTHS = {
    _COL_THUMB: 80,
    _COL_TITLE: 320,
    _COL_QUALITY: 80,
    _COL_SIZE: 90,
    _COL_DATE: 130,
    _COL_PATH: 240,
}

# Bump the per-process pixmap cache so the working set of Library thumbnails
# (small + large preview combined) doesn't get evicted on every scroll.
QPixmapCache.setCacheLimit(20 * 1024)  # kilobytes — 20 MB


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


class _NumericItem(QTableWidgetItem):
    """Table item that sorts by a stored numeric value, displays an arbitrary string.

    Used for the Size column so "1.5 MB" and "900 KB" compare by bytes rather
    than alphabetically.
    """

    def __init__(self, value: int, display: str) -> None:
        super().__init__(display)
        self._sort_value = value

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, _NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)  # type: ignore[arg-type]


class LibraryPanel(QWidget):
    """Two-pane Library — uploader sidebar + filtered/sortable history table."""

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

        # Right pane — filter row + search + table.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addLayout(self._build_filter_row())

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, uploader, URL, description…")
        right_layout.addWidget(self.search_input)

        self.stats_label = QLabel("")
        right_layout.addWidget(self.stats_label)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        header = self.table.horizontalHeader()
        # All Interactive so the user can drag-resize any column — including
        # Title, which used to be Stretch and silently refused to shrink.
        # Last section stretches so Path absorbs leftover horizontal space.
        for col in range(len(_HEADERS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, _DEFAULT_WIDTHS[col])
        # Thumb column is icon-only; lock its width so it can't be dragged
        # narrower than the pixmap cell.
        header.setSectionResizeMode(_COL_THUMB, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(_COL_THUMB, _DEFAULT_WIDTHS[_COL_THUMB])
        header.setStretchLastSection(True)

        # Lazy-paint thumbnail delegate. Placeholder is a flat dark cell that
        # matches the table's neutral background so empty rows don't pop.
        placeholder = QPixmap(_THUMB_W, _THUMB_H)
        placeholder.fill(QColor("#2a2a2a"))
        self._thumb_delegate = LibraryThumbnailDelegate(placeholder, self)
        self.table.setItemDelegateForColumn(_COL_THUMB, self._thumb_delegate)
        self.table.verticalHeader().setDefaultSectionSize(_THUMB_H + 8)

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(_COL_DATE, Qt.SortOrder.DescendingOrder)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        right_layout.addWidget(self.table)

        splitter.addWidget(right)

        # Preview pane (right) — populated on row selection. Placeholder pixmap
        # matches the dark frame around the live thumbnail area so the empty
        # state looks intentional, not broken.
        preview_placeholder = QPixmap(_PREVIEW_W, _PREVIEW_H)
        preview_placeholder.fill(QColor("#1c1c1c"))
        self.preview_pane = LibraryPreviewPane(preview_placeholder, self)
        splitter.addWidget(self.preview_pane)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        # Selection wiring — pulls the HistoryRecord from the Title cell's
        # UserRole and pushes it into the preview pane.
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        # Debounced filter (200 ms). Single timer for search + every filter
        # control — they all funnel into _apply_filters() which re-runs the
        # entire predicate chain anyway.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filters)
        self.search_input.textChanged.connect(lambda _t: self._search_timer.start())

    # ── filter row ────────────────────────────────────────────────────────

    def _build_filter_row(self) -> QHBoxLayout:
        """Create Quality / From / To / Size / Status controls in a single row."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Quality: All", None)
        row.addWidget(self.quality_combo)

        self.from_date_check = QCheckBox("From")
        self.from_date_edit = QDateEdit()
        self.from_date_edit.setCalendarPopup(True)
        self.from_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.from_date_edit.setEnabled(False)
        self.from_date_check.toggled.connect(self.from_date_edit.setEnabled)
        row.addWidget(self.from_date_check)
        row.addWidget(self.from_date_edit)

        self.to_date_check = QCheckBox("To")
        self.to_date_edit = QDateEdit()
        self.to_date_edit.setCalendarPopup(True)
        self.to_date_edit.setDate(QDate.currentDate())
        self.to_date_edit.setEnabled(False)
        self.to_date_check.toggled.connect(self.to_date_edit.setEnabled)
        row.addWidget(self.to_date_check)
        row.addWidget(self.to_date_edit)

        self.size_min_spin = QSpinBox()
        self.size_min_spin.setRange(0, 100_000)
        self.size_min_spin.setSuffix(" MB")
        # specialValueText replaces the displayed value at minimum (0). Lets
        # us show "Min: any" for 0 while keeping a plain int model.
        self.size_min_spin.setSpecialValueText("Min: any")
        row.addWidget(self.size_min_spin)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Status: All", "all")
        self.status_combo.addItem("Available", "available")
        self.status_combo.addItem("Missing", "missing")
        row.addWidget(self.status_combo)

        row.addStretch()

        # Wire every control through the same debounce as the search box.
        for sig in (
            self.quality_combo.currentIndexChanged,
            self.from_date_check.toggled,
            self.from_date_edit.dateChanged,
            self.to_date_check.toggled,
            self.to_date_edit.dateChanged,
            self.size_min_spin.valueChanged,
            self.status_combo.currentIndexChanged,
        ):
            sig.connect(lambda *_: self._search_timer.start())

        return row

    def _rebuild_quality_combo(self) -> None:
        """Repopulate Quality combo from observed values, preserving selection."""
        current = self.quality_combo.currentData()
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        self.quality_combo.addItem("Quality: All", None)
        for q in sorted({r.quality for r in self._records if r.quality}):
            self.quality_combo.addItem(q, q)
        idx = self.quality_combo.findData(current)
        self.quality_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.quality_combo.blockSignals(False)

    # ── public API ────────────────────────────────────────────────────────

    @Slot()
    def refresh(self) -> None:
        """Re-read history file and rebuild sidebar + quality combo + table."""
        records = load_history_records()
        self._records = [r for r in records if r.platform == self.platform]
        self._rebuild_sidebar()
        self._rebuild_quality_combo()
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

    @Slot()
    def _on_selection_changed(self) -> None:
        """Push the currently-selected HistoryRecord into the preview pane."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.preview_pane.set_record(None)
            return
        item = self.table.item(rows[0].row(), _COL_TITLE)
        rec = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.preview_pane.set_record(rec if isinstance(rec, HistoryRecord) else None)

    # ── filter / render ───────────────────────────────────────────────────

    def _apply_filters(self) -> None:
        needle = self.search_input.text().strip().lower()
        quality_filter = self.quality_combo.currentData()
        from_iso = (
            self.from_date_edit.date().toString("yyyy-MM-dd")
            if self.from_date_check.isChecked()
            else None
        )
        to_iso = (
            self.to_date_edit.date().toString("yyyy-MM-dd")
            if self.to_date_check.isChecked()
            else None
        )
        size_min_bytes = self.size_min_spin.value() * 1024 * 1024
        status_mode = self.status_combo.currentData() or "all"

        rows = []
        for r in self._records:
            if self._active_uploader and r.uploader != self._active_uploader:
                continue
            if needle:
                hay = " ".join(
                    filter(None, [r.title, r.uploader, r.url, r.description])
                ).lower()
                if needle not in hay:
                    continue
            if quality_filter and (r.quality or "") != quality_filter:
                continue
            # downloaded_at is ISO8601 ("2026-04-26T10:00:00+07:00") — slice
            # the date prefix so we can compare with from_iso/to_iso directly.
            rec_date = (r.downloaded_at or "")[:10]
            if from_iso and (not rec_date or rec_date < from_iso):
                continue
            if to_iso and (not rec_date or rec_date > to_iso):
                continue
            if size_min_bytes > 0 and (r.size_bytes or 0) < size_min_bytes:
                continue
            if status_mode != "all":
                exists = bool(r.file_path) and os.path.exists(r.file_path)
                if status_mode == "available" and not exists:
                    continue
                if status_mode == "missing" and exists:
                    continue
            rows.append(r)
        self._render_table(rows)
        self._render_stats(rows)

    def _render_table(self, records: list[HistoryRecord]) -> None:
        # Disable sorting during bulk insert — Qt would otherwise re-sort
        # after every insertRow, which is O(n log n) per row. Re-enabling
        # restores the indicator and triggers a single sort over the final
        # set.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            # Thumb cell — empty text, sidecar path on UserRole; the delegate
            # pulls the path from there during paint and ignores the text.
            thumb_item = QTableWidgetItem("")
            thumb_item.setFlags(thumb_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            thumb_item.setData(Qt.ItemDataRole.UserRole, rec.thumbnail_path)
            self.table.setItem(row, _COL_THUMB, thumb_item)
            self.table.setItem(row, _COL_TITLE, QTableWidgetItem(rec.title or "—"))
            self.table.setItem(row, _COL_QUALITY, QTableWidgetItem(rec.quality or "—"))
            self.table.setItem(
                row,
                _COL_SIZE,
                _NumericItem(rec.size_bytes or 0, format_size(rec.size_bytes)),
            )
            self.table.setItem(row, _COL_DATE, QTableWidgetItem(format_date(rec.downloaded_at)))
            self.table.setItem(row, _COL_PATH, QTableWidgetItem(rec.file_path or "—"))
            # Title cell still owns the full HistoryRecord — the context menu
            # and (Phase 4) selection handler both look it up here.
            self.table.item(row, _COL_TITLE).setData(Qt.ItemDataRole.UserRole, rec)
        self.table.setSortingEnabled(True)

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
        item = self.table.item(row, _COL_TITLE)
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
