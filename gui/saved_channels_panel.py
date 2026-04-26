"""Saved-channels panel — list + CRUD + Download all new + Browser-below.

Top of the Channels sub-tab. Owns a saved-channel table and routes selections
into the injected `BaseBrowserPanel` (TikTok or Facebook). Mutations persist
through `saved_channels_store` on every action.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_state import BrowserPanelState, VideoInfoState
from gui.icons import icon
from saved_channels_store import (
    CachedVideo,
    SavedChannel,
    SavedChannelsStore,
    add_channel,
    mark_fetched,
    remove_channel,
    save_saved_channels,
    select_new_videos,
    update_cached_videos,
    update_channel,
)
from url_parser import detect_platform, validate_url

_HEADERS = ("★", "Nickname", "URL", "Videos", "Last fetched")
_DOWNLOAD_CONFIRM_THRESHOLD = 10


def _relative_age(iso: str | None) -> str:
    """`2026-04-26T10:00:00+07:00` → `2d ago`. Returns `—` when None."""
    if not iso:
        return "—"
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    now = datetime.now(when.tzinfo or timezone.utc)
    delta = now - when
    if delta.days >= 1:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours >= 1:
        return f"{hours}h ago"
    mins = (delta.seconds % 3600) // 60
    if mins >= 1:
        return f"{mins}m ago"
    return "just now"


class SavedChannelsPanel(QWidget):
    """Saved-channel list + browse-below for one platform.

    The panel reads/writes the platform slice of a shared `SavedChannelsStore`.
    `browser_panel` is the platform's `BaseBrowserPanel` instance — the same
    object the existing channel browser uses, embedded below the saved list.
    """

    # Already-validated URLs to add to the platform queue, with the source
    # page URL as hint so downloads land in `<platform>/<page>/`.
    download_requested = Signal(list, str)

    def __init__(
        self,
        platform: str,
        browser_panel: QWidget,
        store: SavedChannelsStore,
        store_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.platform = platform
        self.store = store
        self.store_path = store_path
        self.browser_panel = browser_panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar — only Add and Refresh-all (CRUD lives on right-click menu).
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("+ Add")
        self.add_btn.setIcon(icon("mdi6.plus"))
        self.add_btn.clicked.connect(self._on_add_clicked)
        toolbar.addWidget(self.add_btn)

        self.refresh_btn = QPushButton("Refresh all")
        self.refresh_btn.setIcon(icon("mdi6.refresh"))
        self.refresh_btn.setToolTip("Browse each saved channel sequentially")
        self.refresh_btn.clicked.connect(self._on_refresh_all)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter — saved list (top), browser (bottom).
        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, stretch=1)

        # Saved-channels table.
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.itemDoubleClicked.connect(self._on_row_activated)
        splitter.addWidget(self.table)

        # Browser-below — re-uses the existing platform browser panel.
        splitter.addWidget(browser_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # When the browser finishes a fetch, snapshot its videos onto the
        # matching saved channel so the next click can show them instantly.
        self.browser_panel.fetch_completed.connect(self._on_browser_fetch_completed)

        self.refresh_table()

    # ── public API ────────────────────────────────────────────────────────

    def refresh_table(self) -> None:
        """Repopulate the table from the current store slice."""
        channels = self.store.list_all(self.platform)
        self.table.setRowCount(0)
        for ch in channels:
            row = self.table.rowCount()
            self.table.insertRow(row)
            star_item = QTableWidgetItem("★" if ch.starred else "")
            star_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, star_item)
            self.table.setItem(row, 1, QTableWidgetItem(ch.nickname or ""))
            self.table.setItem(row, 2, QTableWidgetItem(ch.url))
            # Prefer cache size — that's the actual row count the user will
            # see when re-opening the channel. Falls back to the cutoff IDs
            # for channels saved before the cache existed.
            video_count = len(ch.cached_videos) or len(ch.last_fetched_video_ids)
            self.table.setItem(row, 3, QTableWidgetItem(str(video_count)))
            self.table.setItem(row, 4, QTableWidgetItem(_relative_age(ch.last_fetched_at)))
            # Stash channel object on first cell for menu lookup.
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, ch)

    def _persist(self) -> None:
        """Write the store to disk after a mutation."""
        save_saved_channels(self.store_path, self.store)

    def _selected_channel(self) -> SavedChannel | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── add / row activation ──────────────────────────────────────────────

    @Slot()
    def _on_add_clicked(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            "Add saved channel",
            f"{self.platform.title()} URL:",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        if not validate_url(url) or detect_platform(url) != self.platform:
            QMessageBox.warning(
                self,
                "Invalid URL",
                f"URL must be a valid {self.platform.title()} channel/page.",
            )
            return
        nickname, _ = QInputDialog.getText(
            self,
            "Nickname (optional)",
            "Nickname for this channel:",
            QLineEdit.EchoMode.Normal,
            "",
        )
        ch = SavedChannel(url=url, nickname=nickname.strip())
        if not add_channel(self.store, self.platform, ch):
            QMessageBox.information(self, "Already saved", "This URL is already in the list.")
            return
        self._persist()
        self.refresh_table()

    def _on_row_activated(self, _item) -> None:
        """Double-click → show cached videos when present, otherwise fetch."""
        ch = self._selected_channel()
        if ch is None:
            return
        self._show_channel(ch)

    # ── show / refresh helpers ────────────────────────────────────────────

    def _show_channel(self, ch: SavedChannel) -> None:
        """Restore the channel's cached videos into the browser panel.

        Falls back to a fresh fetch when the channel has no cache yet.
        """
        if not ch.cached_videos:
            self._refresh_channel(ch)
            return
        state = BrowserPanelState(
            url=ch.url,
            videos=[
                VideoInfoState(
                    url=v.url,
                    title=v.title,
                    duration=v.duration,
                    view_count=v.view_count,
                    upload_date=v.upload_date,
                    video_id=v.video_id,
                    quality=v.quality,
                )
                for v in ch.cached_videos
            ],
        )
        self.browser_panel.load_from_state(state)

    def _refresh_channel(self, ch: SavedChannel) -> None:
        """Force a fresh fetch for the channel — bypasses the cache."""
        self.browser_panel.url_input.setText(ch.url)
        self.browser_panel._on_browse()

    @Slot(int)
    def _on_browser_fetch_completed(self, _total: int) -> None:
        """Persist the freshly-fetched videos onto the matching saved channel.

        No-op when the URL in the browser panel doesn't match a saved channel
        for this platform — keeps ad-hoc Browse from leaking into the store.
        """
        url = self.browser_panel.url_input.text().strip()
        if not url:
            return
        if self.store.find_by_url(self.platform, url) is None:
            return
        cached = [
            CachedVideo(
                url=v.url,
                title=v.title or "",
                duration=v.duration,
                view_count=v.view_count,
                upload_date=v.upload_date,
                video_id=v.video_id or "",
                quality=v.quality,
            )
            for v in self.browser_panel._videos
        ]
        if not update_cached_videos(self.store, self.platform, url, cached):
            return
        self._persist()
        self.refresh_table()

    # ── refresh-all ───────────────────────────────────────────────────────

    @Slot()
    def _on_refresh_all(self) -> None:
        """Sequentially browse each saved channel.

        Lightweight implementation: iterate, set URL, call Browse. The
        underlying QThread fetcher serialises on each call (the panel
        cancels any in-flight fetch before starting a new one). For now we
        just trigger the first; user can step through manually via
        double-click. A fully sequential auto-refresh is left as a follow-up.
        """
        channels = self.store.list_all(self.platform)
        if not channels:
            return
        # Trigger a Browse on the first; user can step through the rest.
        self._refresh_channel(channels[0])

    # ── context menu ──────────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        ch = self._selected_channel()
        if ch is None:
            return

        menu = QMenu(self)
        show_label = "Show (cached)" if ch.cached_videos else "Browse"
        show_act = menu.addAction(show_label)
        refresh_act = menu.addAction("Refresh (fetch)")
        download_all_act = menu.addAction("Download all new")
        menu.addSeparator()
        rename_act = menu.addAction("Rename + notes...")
        edit_url_act = menu.addAction("Edit URL...")
        star_act = menu.addAction("Unstar" if ch.starred else "Star")
        menu.addSeparator()
        remove_act = menu.addAction("Remove")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action is None:
            return
        if action is show_act:
            self._show_channel(ch)
        elif action is refresh_act:
            self._refresh_channel(ch)
        elif action is download_all_act:
            self._download_all_new(ch)
        elif action is rename_act:
            self._rename_channel(ch)
        elif action is edit_url_act:
            self._edit_url(ch)
        elif action is star_act:
            update_channel(self.store, self.platform, ch.url, starred=not ch.starred)
            self._persist()
            self.refresh_table()
        elif action is remove_act:
            confirm = QMessageBox.question(
                self,
                "Remove channel",
                f"Remove '{ch.nickname or ch.url}' from saved list?",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                remove_channel(self.store, self.platform, ch.url)
                self._persist()
                self.refresh_table()

    def _rename_channel(self, ch: SavedChannel) -> None:
        nickname, ok = QInputDialog.getText(
            self,
            "Rename channel",
            "Nickname:",
            QLineEdit.EchoMode.Normal,
            ch.nickname,
        )
        if not ok:
            return
        note, ok2 = QInputDialog.getMultiLineText(self, "Notes", "Notes:", ch.note)
        if not ok2:
            return
        update_channel(self.store, self.platform, ch.url, nickname=nickname.strip(), note=note)
        self._persist()
        self.refresh_table()

    def _edit_url(self, ch: SavedChannel) -> None:
        new_url, ok = QInputDialog.getText(
            self,
            "Edit URL",
            "URL:",
            QLineEdit.EchoMode.Normal,
            ch.url,
        )
        if not ok or not new_url.strip():
            return
        new_url = new_url.strip()
        if detect_platform(new_url) != self.platform:
            QMessageBox.warning(
                self, "Invalid URL", f"URL must be a {self.platform.title()} URL."
            )
            return
        # Replace by remove + add to keep cap behaviour consistent.
        remove_channel(self.store, self.platform, ch.url)
        add_channel(
            self.store,
            self.platform,
            SavedChannel(
                url=new_url,
                nickname=ch.nickname,
                note=ch.note,
                starred=ch.starred,
                last_fetched_at=ch.last_fetched_at,
                last_fetched_video_ids=list(ch.last_fetched_video_ids),
            ),
        )
        self._persist()
        self.refresh_table()

    # ── download all new ──────────────────────────────────────────────────

    def _download_all_new(self, ch: SavedChannel) -> None:
        """Filter `browser_panel._videos` to "new" and emit `download_requested`.

        Cached `_videos` from the last Browse drives the filter — no new fetch.
        Call Browse first if the cache is stale.
        """
        fetched = list(getattr(self.browser_panel, "_videos", []))
        if not fetched:
            QMessageBox.information(
                self,
                "Nothing to filter",
                "Browse this channel first — no fetched videos in cache.",
            )
            return
        history_ids = self._gather_history_ids()
        new_videos = select_new_videos(ch, fetched, history_ids)
        if not new_videos:
            QMessageBox.information(self, "No new videos", "Already up to date.")
            return
        if len(new_videos) > _DOWNLOAD_CONFIRM_THRESHOLD:
            confirm = QMessageBox.question(
                self,
                "Download all new",
                f"Queue {len(new_videos)} new videos from {ch.nickname or ch.url}?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        urls = [v.url for v in new_videos if v.url]
        if not urls:
            return
        # Record this fetch's ids + cutoff so subsequent runs scope correctly.
        all_ids = [v.video_id for v in fetched if getattr(v, "video_id", None)]
        now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        mark_fetched(self.store, self.platform, ch.url, all_ids, now_iso)
        self._persist()
        self.refresh_table()
        self.download_requested.emit(urls, ch.url)

    def _gather_history_ids(self) -> set[str]:
        """Snapshot of engine dedup set — uses the resolver passed by parent.

        Falls back to an empty set when MainWindow hasn't wired a resolver yet
        (keeps unit tests instantiable in isolation).
        """
        getter: Callable[[], set[str]] | None = getattr(self, "history_ids_resolver", None)
        return getter() if getter else set()
