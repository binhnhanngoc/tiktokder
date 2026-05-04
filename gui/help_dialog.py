"""HelpDialog &mdash; tabbed in-app manual.

Open from the Help menu (or F1). Non-modal so users can keep it on screen
while exporting cookies in their browser. Each tab is a ``QTextBrowser``
hosting HTML; external ``https://`` links are routed to the system browser
via ``QDesktopServices`` so the dialog itself never tries to render web
pages.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from gui.help_content import help_tabs


class HelpDialog(QDialog):
    """Tabbed help dialog with HTML content per tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TikTokDer — Help")
        self.setModal(False)
        self.resize(760, 580)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self._tab_index_by_id: dict[str, int] = {}

        for tab_id, label, html in help_tabs():
            browser = QTextBrowser()
            # We route links ourselves so external URLs open in the user's
            # default browser instead of QTextBrowser trying to fetch them.
            browser.setOpenExternalLinks(False)
            browser.setOpenLinks(False)
            browser.anchorClicked.connect(self._on_anchor_clicked)
            browser.setHtml(html)
            idx = self.tabs.addTab(browser, label)
            self._tab_index_by_id[tab_id] = idx

        layout.addWidget(self.tabs, stretch=1)

        # Close button — bottom-right, matches platform conventions.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_at_tab(self, tab_id: str) -> None:
        """Show + raise + jump to a known tab id. Unknown id falls back to tab 0."""
        idx = self._tab_index_by_id.get(tab_id, 0)
        self.tabs.setCurrentIndex(idx)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_anchor_clicked(self, url: QUrl) -> None:
        """Route ``http(s)://`` links to the system browser; ignore others."""
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
