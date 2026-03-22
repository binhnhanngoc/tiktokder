"""Channel/page browsing widget - list videos from a TikTok or Facebook profile."""

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QCheckBox,
)

from channel_fetcher import ChannelFetcher, VideoInfo
from facebook_fetcher import FacebookFetcher
from url_parser import detect_platform


class ChannelBrowser(QWidget):
    """Browse a TikTok channel and select videos for download."""

    download_requested = Signal(list)  # list[str] of URLs

    def __init__(self, cookie_browser: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cookie_browser = cookie_browser
        self._fetcher: ChannelFetcher | None = None
        self._videos: list[VideoInfo] = []

        layout = QVBoxLayout(self)

        # Top bar: URL input + Browse button
        top = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste TikTok channel or Facebook page URL...")
        self.url_input.returnPressed.connect(self._on_browse)
        top.addWidget(self.url_input, stretch=1)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._on_browse)
        top.addWidget(self.browse_btn)
        layout.addLayout(top)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Video table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["", "Title", "Duration", "Views", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Bottom buttons
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

    def _on_browse(self) -> None:
        """Start fetching videos from channel/page URL."""
        url = self.url_input.text().strip()
        if not url:
            return

        # Cancel any running fetch
        if self._fetcher and self._fetcher.isRunning():
            self._fetcher.cancel()
            self._fetcher.wait()

        self._videos.clear()
        self.table.setRowCount(0)
        self.browse_btn.setEnabled(False)

        # Use FacebookFetcher for Facebook URLs, ChannelFetcher for TikTok
        platform = detect_platform(url)
        if platform == "facebook":
            self.status_label.setText("Fetching Facebook videos (browser scraping)...")
            self._fetcher = FacebookFetcher(url, parent=self)
        else:
            self.status_label.setText("Fetching videos...")
            self._fetcher = ChannelFetcher(url, self.cookie_browser, parent=self)

        self._fetcher.video_found.connect(self._on_video_found)
        self._fetcher.error.connect(self._on_error)
        self._fetcher.finished_fetch.connect(self._on_fetch_done)
        self._fetcher.start()

    @Slot(object)
    def _on_video_found(self, video: VideoInfo) -> None:
        """Add a discovered video to the table."""
        self._videos.append(video)
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Checkbox
        cb = QCheckBox()
        cb.setChecked(True)
        self.table.setCellWidget(row, 0, cb)

        # Title
        self.table.setItem(row, 1, QTableWidgetItem(video.title))

        # Duration
        dur = self._format_duration(video.duration) if video.duration else "—"
        self.table.setItem(row, 2, QTableWidgetItem(dur))

        # Views
        views = f"{video.view_count:,}" if video.view_count else "—"
        self.table.setItem(row, 3, QTableWidgetItem(views))

        # Date
        date = self._format_date(video.upload_date) if video.upload_date else "—"
        self.table.setItem(row, 4, QTableWidgetItem(date))

        self.status_label.setText(f"Found {len(self._videos)} videos...")

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        self.status_label.setText(f"Error: {msg}")

    @Slot(int)
    def _on_fetch_done(self, total: int) -> None:
        self.browse_btn.setEnabled(True)
        self.status_label.setText(f"Found {total} videos")

    def _select_all(self) -> None:
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(True)

    def _deselect_all(self) -> None:
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if cb:
                cb.setChecked(False)

    def _on_download(self) -> None:
        """Emit selected video URLs for download."""
        urls = []
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
        """Convert YYYYMMDD to YYYY-MM-DD."""
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str
