"""Platform tab — composite widget hosting Channels / Queue / Library sub-tabs.

One instance per platform ('tiktok' or 'facebook'). Receives the platform's
browser panel (TikTok/Facebook) and a shared `SavedChannelsStore`. The Library
sub-tab starts as a placeholder; Phase 04 swaps in `LibraryPanel`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.download_table import DownloadTableWidget
from gui.saved_channels_panel import SavedChannelsPanel
from saved_channels_store import SavedChannelsStore
from url_parser import detect_platform, read_batch_file, validate_url

_SUB_TAB_LABELS = ("Channels", "Queue", "Library")


class PlatformTab(QWidget):
    """Composite per-platform widget with three sub-tabs.

    Public attributes:
      - `channels_panel` : `SavedChannelsPanel`
      - `queue_panel`    : `DownloadTableWidget` (filtered to this platform)
      - `library_panel`  : placeholder this phase; replaced in Phase 04
      - `browser_panel`  : ref to the injected browser panel (also embedded in
                           channels_panel)
    """

    # Already-validated URLs to add to the platform's queue.
    urls_dropped = Signal(list)

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
        self.browser_panel = browser_panel
        self.store = store
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)

        # Channels — saved list + browser-below.
        self.channels_panel = SavedChannelsPanel(
            platform=platform,
            browser_panel=browser_panel,
            store=store,
            store_path=store_path,
        )
        self.sub_tabs.addTab(self.channels_panel, _SUB_TAB_LABELS[0])

        # Queue — per-platform DownloadTableWidget.
        self.queue_panel = DownloadTableWidget()
        self.sub_tabs.addTab(self.queue_panel, _SUB_TAB_LABELS[1])

        # Library — placeholder until Phase 04.
        self.library_panel: QWidget = QLabel(
            "Library coming in Phase 04.\n\nUploader sidebar + filtered history table.",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.sub_tabs.addTab(self.library_panel, _SUB_TAB_LABELS[2])

    # ── sub-tab control ───────────────────────────────────────────────────

    def set_active_sub_tab(self, index: int) -> None:
        if 0 <= index < self.sub_tabs.count():
            self.sub_tabs.setCurrentIndex(index)

    def current_sub_tab_index(self) -> int:
        return self.sub_tabs.currentIndex()

    def replace_library_panel(self, widget: QWidget) -> None:
        """Swap the placeholder for the real `LibraryPanel` (Phase 04 hook)."""
        idx = self.sub_tabs.indexOf(self.library_panel)
        self.sub_tabs.removeTab(idx)
        self.library_panel = widget
        self.sub_tabs.insertTab(idx, widget, _SUB_TAB_LABELS[2])

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

        # Filter to validated URLs of this platform only.
        valid = [u for u in urls if validate_url(u) and detect_platform(u) == self.platform]
        if valid:
            self.urls_dropped.emit(valid)
            event.acceptProposedAction()
        else:
            event.ignore()
