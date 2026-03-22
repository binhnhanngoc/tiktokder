"""URL input widget with paste and add buttons."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QApplication,
)

from url_parser import validate_url, is_page_or_channel_url


class UrlInputPanel(QWidget):
    """URL input bar with Add and Paste buttons."""

    # Emitted when a valid video URL is submitted
    video_url_submitted = Signal(str)
    # Emitted when a channel/profile URL is submitted
    channel_url_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste TikTok or Facebook video/page URL...")
        self.url_input.returnPressed.connect(self._on_add)
        layout.addWidget(self.url_input, stretch=1)

        self.paste_btn = QPushButton("Paste")
        self.paste_btn.clicked.connect(self._on_paste)
        layout.addWidget(self.paste_btn)

        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._on_add)
        layout.addWidget(self.add_btn)

    def _on_paste(self) -> None:
        """Read clipboard text into the URL input."""
        clipboard = QApplication.clipboard()
        if clipboard:
            text = clipboard.text().strip()
            if text:
                self.url_input.setText(text)

    def _on_add(self) -> None:
        """Validate and emit the URL."""
        url = self.url_input.text().strip()
        if not url:
            return

        # Reset error styling on new attempt
        self.url_input.setStyleSheet("")
        self.url_input.setPlaceholderText("Paste TikTok or Facebook video/page URL...")

        if is_page_or_channel_url(url):
            self.channel_url_submitted.emit(url)
            self.url_input.clear()
        elif validate_url(url):
            self.video_url_submitted.emit(url)
            self.url_input.clear()
        else:
            self.url_input.setStyleSheet("border: 1px solid red;")
            self.url_input.setPlaceholderText("Invalid URL")
