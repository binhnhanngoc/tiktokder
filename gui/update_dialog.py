"""UpdateAvailableDialog &mdash; modal "newer version available" dialog.

Pure UI: emits signals, never touches config or network. ``MainWindow``
constructs and shows this dialog from a ``ReleaseInfo`` payload, then
applies the user's choices (skip / opt-out) to ``AppConfig`` itself.

Constructor contract:
    - ``release`` &mdash; the parsed remote release.
    - ``current_version_str`` &mdash; e.g. ``"1.9.0"`` (display only).
    - ``opt_out_currently`` &mdash; pass ``not config.update_check_enabled``;
      checkbox initial state mirrors this. If the user toggles the box,
      caller flips the config bit on close (read via ``opt_out_chosen()``).

Signals:
    - ``skip_requested(version_str: str)`` &mdash; caller writes
      ``config.skipped_update_version`` and saves.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from update_checker import ReleaseInfo


_TAG_FALLBACK_PLACEHOLDER = (
    "No release notes available — see GitHub for details."
)


class UpdateAvailableDialog(QDialog):
    """Modal dialog announcing a newer release. UI-pure: caller persists state."""

    skip_requested = Signal(str)

    def __init__(
        self,
        release: ReleaseInfo,
        current_version_str: str,
        opt_out_currently: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._release_url = release.html_url
        self._version_str = release.version_str
        self.setWindowTitle("Update available — TikTokDer")
        self.setModal(True)
        self.resize(560, 420)
        self._build_ui(release, current_version_str, opt_out_currently)

    def _build_ui(
        self,
        release: ReleaseInfo,
        current_version_str: str,
        opt_out_currently: bool,
    ) -> None:
        layout = QVBoxLayout(self)

        header = QLabel(
            f"<b>Version {release.version_str}</b> is available "
            f"(you have <b>{current_version_str}</b>)"
        )
        header.setTextFormat(header.textFormat())
        header.setWordWrap(True)
        layout.addWidget(header)

        body = QTextBrowser()
        body.setOpenLinks(False)
        body.setOpenExternalLinks(False)
        body.anchorClicked.connect(self._on_anchor_clicked)
        if release.is_tag_fallback or not release.body:
            body.setPlainText(_TAG_FALLBACK_PLACEHOLDER)
        else:
            body.setMarkdown(release.body)
        layout.addWidget(body, stretch=1)

        self._optout_checkbox = QCheckBox("Don't check for updates automatically")
        self._optout_checkbox.setChecked(bool(opt_out_currently))
        layout.addWidget(self._optout_checkbox)

        button_row = QHBoxLayout()
        open_btn = QPushButton("Open Release Page")
        open_btn.setDefault(True)
        skip_btn = QPushButton("Skip This Version")
        later_btn = QPushButton("Remind Me Later")
        button_row.addWidget(open_btn)
        button_row.addWidget(skip_btn)
        button_row.addStretch(1)
        button_row.addWidget(later_btn)
        layout.addLayout(button_row)

        open_btn.clicked.connect(self._on_open_release)
        skip_btn.clicked.connect(self._on_skip)
        later_btn.clicked.connect(self.accept)

    def opt_out_chosen(self) -> bool:
        """Final checkbox state at close — caller decides to flip the config."""
        return self._optout_checkbox.isChecked()

    @Slot()
    def _on_open_release(self) -> None:
        QDesktopServices.openUrl(QUrl(self._release_url))
        self.accept()

    @Slot()
    def _on_skip(self) -> None:
        self.skip_requested.emit(self._version_str)
        self.accept()

    @Slot(QUrl)
    def _on_anchor_clicked(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
