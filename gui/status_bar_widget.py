"""Permanent status-bar widget — per-platform queue badges + Done + status text.

Mounted via `QMainWindow.statusBar().addPermanentWidget(...)`. `set_counts`
is called whenever queue mutations happen so the badges stay live.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StatusBarWidget(QWidget):
    """Compact status display: TT badge · FB badge · Done · free-text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.tiktok_label = QLabel("TT: 0")
        layout.addWidget(self.tiktok_label)

        self.facebook_label = QLabel("FB: 0")
        layout.addWidget(self.facebook_label)

        self.done_label = QLabel("Done: 0")
        layout.addWidget(self.done_label)

    def set_counts(
        self,
        tiktok_queued: int,
        facebook_queued: int,
        done: int,
        status_text: str | None = None,
    ) -> None:
        """Update all four labels in one call."""
        self.tiktok_label.setText(f"TT: {tiktok_queued}")
        self.facebook_label.setText(f"FB: {facebook_queued}")
        self.done_label.setText(f"Done: {done}")
        if status_text is not None:
            self.status_label.setText(status_text)
