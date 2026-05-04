"""Shared widget logic for TikTok and Facebook browser sub-panels.

Subclasses implement ``_create_fetcher`` to return the platform-specific
QThread fetcher. Common UX (URL input, video table with checkboxes, search +
filter row, sortable headers, select all/none, download-selected) lives here.

Filtering is view-only — the underlying ``self._videos`` list is never mutated
because ``SavedChannelsPanel`` consumes it for the "Download new only" flow.
Rows are hidden via ``setRowHidden`` and the bottom-row actions ignore hidden
rows so users can't accidentally select or download something they filtered out.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QDate, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_state import BrowserPanelState, VideoInfoState
from channel_fetcher import VideoInfo
from gui import progress_styles
from gui._table_items import NumericItem
from gui.icons import icon

_HEADERS = ("", "✓", "Title", "Duration", "Quality", "Views", "Date")

# Column indices — single source of truth for sort/render code.
_COL_CHECK = 0
_COL_DOWNLOADED = 1
_COL_TITLE = 2
_COL_DURATION = 3
_COL_QUALITY = 4
_COL_VIEWS = 5
_COL_DATE = 6


class BaseBrowserPanel(QWidget):
    """Base panel with URL input + filter row + video table + select/download controls."""

    # Emits (urls, page_hint) — page_hint is the source page URL the user
    # browsed to scrape these videos. Empty string when not applicable.
    download_requested = Signal(list, str)

    # Emitted after a successful fetch with the count of videos found.
    # Listeners can read `self._videos` and `self.url_input.text()` to snapshot
    # the result (used by SavedChannelsPanel to refresh the per-channel cache).
    fetch_completed = Signal(int)

    # Lifecycle signals — fired regardless of success/cancel/error so siblings
    # (saved-channels list, etc.) can disable rapid-click triggers without
    # peeking at internal fetcher state. fetch_finished always pairs with
    # fetch_started, even on cancel/error.
    fetch_started = Signal()
    fetch_finished = Signal()

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fetcher = None
        self._videos: list[VideoInfo] = []
        self._is_fetching = False

        # MainWindow injects these after construction so the panel can render
        # the ✓ column + filter without holding a hard ref to DownloadEngine.
        # `history_record_resolver` is optional; falls back to plain
        # "Downloaded" tooltip when the lookup is missing.
        self.history_ids_resolver: Callable[[], set[str]] | None = None
        self.history_record_resolver: Callable[[str], object | None] | None = None
        # Per-pass cache populated by _apply_filters so per-row predicate +
        # cell render avoids calling the resolver N times.
        self._cached_history_ids: set[str] = set()

        layout = QVBoxLayout(self)

        self._top_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(placeholder)
        self.url_input.returnPressed.connect(self._on_browse)
        self._top_row.addWidget(self.url_input, stretch=1)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setIcon(icon("mdi6.magnify"))
        self.browse_btn.clicked.connect(self._on_browse)
        self._top_row.addWidget(self.browse_btn)

        # Cancel button — only visible while a fetch is running. Click sets
        # the fetcher's cancel flag without blocking the GUI thread.
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(icon("mdi6.close"))
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._top_row.addWidget(self.cancel_btn)
        layout.addLayout(self._top_row)

        # Indeterminate "busy" bar — yt-dlp/Playwright don't report a total
        # so we use the marquee mode (range 0–0). Hidden when idle.
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        progress_styles.apply(self.progress_bar, "indeterminate", "normal")
        layout.addWidget(self.progress_bar)

        # Filter row + search box — both funnel into one debounced timer that
        # re-runs `_apply_filters` over every fetched row. Mirrors LibraryPanel.
        layout.addLayout(self._build_filter_row())

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title…")
        layout.addWidget(self.search_input)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.horizontalHeader().setSectionResizeMode(_COL_TITLE, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            _COL_DOWNLOADED, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(_COL_DATE, Qt.SortOrder.DescendingOrder)
        layout.addWidget(self.table)

        self._bottom_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setIcon(icon("mdi6.checkbox-multiple-marked-outline"))
        self.select_all_btn.clicked.connect(self._select_all)
        self._bottom_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setIcon(icon("mdi6.checkbox-multiple-blank-outline"))
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        self._bottom_row.addWidget(self.deselect_all_btn)

        self._bottom_row.addStretch()

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setIcon(icon("mdi6.download"))
        self.download_btn.clicked.connect(self._on_download)
        self._bottom_row.addWidget(self.download_btn)
        layout.addLayout(self._bottom_row)

        # Debounced filter (200 ms). Single timer for search + every filter
        # control — they all funnel into _apply_filters() which re-runs the
        # entire predicate chain anyway.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filters)
        self.search_input.textChanged.connect(lambda _t: self._search_timer.start())

        # Coalesces bursts of engine.history_changed (e.g. 5 downloads
        # finishing back-to-back) into a single ✓ column re-render.
        self._history_refresh_timer = QTimer(self)
        self._history_refresh_timer.setSingleShot(True)
        self._history_refresh_timer.setInterval(100)
        self._history_refresh_timer.timeout.connect(self._refresh_downloaded_state)

    # --- filter row ---------------------------------------------------------------

    def _build_filter_row(self) -> QHBoxLayout:
        """Quality dropdown + From/To date toggles in a single row."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Quality: All", None)
        row.addWidget(self.quality_combo)

        self.downloaded_combo = QComboBox()
        self.downloaded_combo.addItem("Downloaded: All", "all")
        self.downloaded_combo.addItem("New only", "new")
        self.downloaded_combo.addItem("Downloaded only", "downloaded")
        row.addWidget(self.downloaded_combo)

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

        row.addStretch()

        # Wire every control through the same debounce as the search box.
        for sig in (
            self.quality_combo.currentIndexChanged,
            self.downloaded_combo.currentIndexChanged,
            self.from_date_check.toggled,
            self.from_date_edit.dateChanged,
            self.to_date_check.toggled,
            self.to_date_edit.dateChanged,
        ):
            sig.connect(lambda *_: self._search_timer.start())

        return row

    def _rebuild_quality_combo(self) -> None:
        """Repopulate Quality combo from observed values, preserving selection."""
        current = self.quality_combo.currentData()
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        self.quality_combo.addItem("Quality: All", None)
        for q in sorted({v.quality for v in self._videos if v.quality}):
            self.quality_combo.addItem(q, q)
        idx = self.quality_combo.findData(current)
        self.quality_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.quality_combo.blockSignals(False)

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

        # Re-entry guard. While a fetch is in flight, the surrounding controls
        # (URL input, browse button, saved-channels table) are disabled — but
        # programmatic callers (e.g. SavedChannelsPanel._refresh_channel) bypass
        # those, so we still need this short-circuit to avoid overlap.
        if self._is_fetching:
            return

        fetcher = self._create_fetcher(url)
        if fetcher is None:
            return

        self._videos.clear()
        self.table.setRowCount(0)
        self._start_fetcher(fetcher)

    def _start_fetcher(self, fetcher) -> None:
        """Wire signals and start ``fetcher`` without clearing the current table.

        Subclasses use this to launch additional fetchers (e.g. "Load more")
        that append rows instead of replacing them.
        """
        self._is_fetching = True
        self.browse_btn.setEnabled(False)
        self.url_input.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText(self._start_status_text())
        self._fetcher = fetcher
        fetcher.video_found.connect(self._on_video_found)
        fetcher.error.connect(self._on_error)
        fetcher.finished_fetch.connect(self._on_fetch_done)
        fetcher.start()
        self.fetch_started.emit()

    def _make_downloaded_item(self, video: VideoInfo) -> NumericItem:
        """Render the ✓ cell. Sort key 1=downloaded, 0=new so DESC groups ✓ rows.

        Tooltip shows ``Downloaded {YYYY-MM-DD HH:MM}`` when the record
        resolver is wired and returns a value with ``downloaded_at``;
        otherwise falls back to plain ``Downloaded``.
        """
        history_ids = (
            self._cached_history_ids
            if self._cached_history_ids
            else (self.history_ids_resolver() if self.history_ids_resolver else set())
        )
        vid = video.video_id or ""
        if vid and vid in history_ids:
            item = NumericItem(1, "✓")
            tooltip = "Downloaded"
            if self.history_record_resolver is not None:
                record = self.history_record_resolver(vid)
                stamp = getattr(record, "downloaded_at", None) if record else None
                if isinstance(stamp, str) and stamp:
                    # ISO8601 → strip seconds + tz for compact tooltip.
                    pretty = stamp.replace("T", " ")[:16]
                    tooltip = f"Downloaded {pretty}"
            item.setToolTip(tooltip)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            return item
        item = NumericItem(0, "")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    @Slot(object)
    def _on_video_found(self, video: VideoInfo) -> None:
        self._videos.append(video)
        # Disable sorting during insert so Qt doesn't reshuffle the table for
        # every row — re-enabled at the end of the method.
        self.table.setSortingEnabled(False)
        row = self.table.rowCount()
        self.table.insertRow(row)

        cb = QCheckBox()
        cb.setChecked(True)
        self.table.setCellWidget(row, _COL_CHECK, cb)

        self.table.setItem(row, _COL_DOWNLOADED, self._make_downloaded_item(video))

        # Title cell carries the VideoInfo on UserRole so `_apply_filters` can
        # re-evaluate the predicate without re-parsing display text.
        title_item = QTableWidgetItem(video.title)
        title_item.setData(Qt.ItemDataRole.UserRole, video)
        self.table.setItem(row, _COL_TITLE, title_item)

        dur_secs = video.duration or 0
        dur_text = self._format_duration(video.duration) if video.duration else "—"
        self.table.setItem(row, _COL_DURATION, NumericItem(dur_secs, dur_text))

        self.table.setItem(row, _COL_QUALITY, QTableWidgetItem(video.quality or "—"))

        views_val = video.view_count or 0
        views_text = f"{video.view_count:,}" if video.view_count else "—"
        self.table.setItem(row, _COL_VIEWS, NumericItem(views_val, views_text))

        date_val = int(video.upload_date) if (video.upload_date or "").isdigit() else 0
        date_text = self._format_date(video.upload_date) if video.upload_date else "—"
        self.table.setItem(row, _COL_DATE, NumericItem(date_val, date_text))

        self.table.setSortingEnabled(True)

        # Re-apply the predicate over EVERY row by current index — re-enabling
        # sorting can reorder rows, so the freshly captured `row` index is no
        # longer guaranteed to point at this video. _apply_filters reads the
        # VideoInfo from each cell's UserRole and is index-correct.
        self._apply_filters()
        # Show ellipsis during live fetch so the user can tell more rows are
        # still streaming in. _apply_filters' final-state text gets overwritten.
        total = len(self._videos)
        visible = sum(
            1 for r in range(self.table.rowCount()) if not self.table.isRowHidden(r)
        )
        if visible == total:
            self.status_label.setText(f"Found {total} videos…")
        else:
            self.status_label.setText(f"Found {total} videos — showing {visible}…")

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self.status_label.setText(f"Error: {msg}")

    @Slot(int)
    def _on_fetch_done(self, total: int) -> None:
        self._is_fetching = False
        self.browse_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self._rebuild_quality_combo()
        self._apply_filters()
        self.fetch_completed.emit(total)
        self.fetch_finished.emit()

    @Slot()
    def _on_cancel_clicked(self) -> None:
        """Request cancellation without blocking the GUI thread.

        The fetcher's ``_cancelled`` flag exits ``run()`` between iterations.
        We never call ``wait()`` — the worker emits ``finished_fetch`` when it
        exits naturally, which routes through ``_on_fetch_done`` to restore UI.
        """
        if self._fetcher is None or not self._fetcher.isRunning():
            return
        self._fetcher.cancel()
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling…")

    def _select_all(self) -> None:
        self._set_all_checks(True)

    def _deselect_all(self) -> None:
        self._set_all_checks(False)

    def _set_all_checks(self, value: bool) -> None:
        # Skip hidden rows so users don't accidentally toggle filtered-out
        # entries — they can't see them and probably didn't mean them.
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            cb = self.table.cellWidget(row, _COL_CHECK)
            if cb:
                cb.setChecked(value)

    def _on_download(self) -> None:
        urls: list[str] = []
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            cb = self.table.cellWidget(row, _COL_CHECK)
            if cb and cb.isChecked():
                title_item = self.table.item(row, _COL_TITLE)
                video = (
                    title_item.data(Qt.ItemDataRole.UserRole)
                    if title_item
                    else None
                )
                if isinstance(video, VideoInfo):
                    urls.append(video.url)
        if urls:
            self.download_requested.emit(urls, self.url_input.text().strip())

    # --- filter predicate ---------------------------------------------------------

    def _matches(self, video: VideoInfo) -> bool:
        """True if ``video`` passes search + quality + date + downloaded filters."""
        needle = self.search_input.text().strip().lower()
        if needle and needle not in (video.title or "").lower():
            return False

        quality_filter = self.quality_combo.currentData()
        if quality_filter and (video.quality or "") != quality_filter:
            return False

        # upload_date is stored as YYYYMMDD; QDateEdit gives us yyyyMMdd via
        # toString — same lexical ordering as numeric, so direct compare works.
        if self.from_date_check.isChecked():
            from_str = self.from_date_edit.date().toString("yyyyMMdd")
            if not video.upload_date or video.upload_date < from_str:
                return False
        if self.to_date_check.isChecked():
            to_str = self.to_date_edit.date().toString("yyyyMMdd")
            if not video.upload_date or video.upload_date > to_str:
                return False

        mode = self.downloaded_combo.currentData()
        if mode in ("new", "downloaded"):
            is_downloaded = (video.video_id or "") in self._cached_history_ids
            if mode == "new" and is_downloaded:
                return False
            if mode == "downloaded" and not is_downloaded:
                return False

        return True

    def _apply_filters(self) -> None:
        """Re-evaluate every row's visibility against current filters."""
        # Snapshot history ids once per pass so per-row predicate is O(1).
        self._cached_history_ids = (
            self.history_ids_resolver() if self.history_ids_resolver else set()
        )
        # Disable sort while toggling visibility — minor perf, also avoids any
        # cosmetic flicker if Qt re-runs the comparator mid-toggle.
        self.table.setSortingEnabled(False)
        visible = 0
        for row in range(self.table.rowCount()):
            title_item = self.table.item(row, _COL_TITLE)
            video = (
                title_item.data(Qt.ItemDataRole.UserRole) if title_item else None
            )
            ok = isinstance(video, VideoInfo) and self._matches(video)
            self.table.setRowHidden(row, not ok)
            if ok:
                visible += 1
        self.table.setSortingEnabled(True)

        total = len(self._videos)
        if total == 0:
            return
        if visible == total:
            self.status_label.setText(f"Found {total} videos")
        else:
            downloaded_total = sum(
                1
                for v in self._videos
                if (v.video_id or "") in self._cached_history_ids
            )
            self.status_label.setText(
                f"Found {total} videos — showing {visible} "
                f"({downloaded_total} already downloaded)"
            )

    @staticmethod
    def _format_duration(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"

    @staticmethod
    def _format_date(date_str: str) -> str:
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str

    # --- persistence --------------------------------------------------------------

    def snapshot(self) -> BrowserPanelState:
        """Return serializable panel state (URL + currently shown videos).

        Subclasses may override to capture extra fields (e.g. Facebook's
        max-scrolls spinbox) by calling ``super().snapshot()`` and mutating
        the returned dataclass.
        """
        videos = [
            VideoInfoState(
                url=v.url,
                title=v.title or "",
                duration=v.duration,
                view_count=v.view_count,
                upload_date=v.upload_date,
                video_id=v.video_id or "",
                quality=v.quality,
            )
            for v in self._videos
        ]
        return BrowserPanelState(
            url=self.url_input.text().strip(),
            videos=videos,
        )

    def load_from_state(self, state: BrowserPanelState) -> None:
        """Restore URL field and rebuild the video table from ``state``.

        Does NOT trigger a new fetch — fetches are slow and may be unwanted
        on launch. The user can hit Browse manually if they want fresh data.
        """
        self.url_input.setText(state.url or "")
        self._videos.clear()
        self.table.setRowCount(0)
        for v in state.videos:
            video = VideoInfo(
                url=v.url,
                title=v.title or "Untitled",
                duration=v.duration,
                view_count=v.view_count,
                upload_date=v.upload_date,
                video_id=v.video_id or "",
                quality=v.quality,
            )
            self._on_video_found(video)
        if self._videos:
            self._rebuild_quality_combo()
            self._apply_filters()
            self.status_label.setText(f"Restored {len(self._videos)} videos")

    # --- Downloaded filter / live refresh ----------------------------------------

    def set_downloaded_filter(self, mode: str) -> None:
        """Programmatic combo restore — signal-blocked so it doesn't double-fire filters."""
        idx = self.downloaded_combo.findData(mode)
        if idx < 0:
            return
        self.downloaded_combo.blockSignals(True)
        self.downloaded_combo.setCurrentIndex(idx)
        self.downloaded_combo.blockSignals(False)
        self._apply_filters()

    @Slot()
    def on_history_changed(self) -> None:
        """Coalesce bursts of engine signal — fire one refresh after 100 ms idle."""
        self._history_refresh_timer.start()

    def _refresh_downloaded_state(self) -> None:
        """Re-render every ✓ cell + re-apply filter (e.g. New only hides newly-downloaded rows)."""
        # Refresh resolver snapshot before per-row render so cells use the new ids.
        self._cached_history_ids = (
            self.history_ids_resolver() if self.history_ids_resolver else set()
        )
        self.table.setSortingEnabled(False)
        for row in range(self.table.rowCount()):
            title_item = self.table.item(row, _COL_TITLE)
            video = (
                title_item.data(Qt.ItemDataRole.UserRole) if title_item else None
            )
            if isinstance(video, VideoInfo):
                self.table.setItem(
                    row, _COL_DOWNLOADED, self._make_downloaded_item(video)
                )
        self.table.setSortingEnabled(True)
        self._apply_filters()
