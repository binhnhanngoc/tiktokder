"""Permanent status-bar widget — health pill, per-platform queue badges, status text.

Mounted via `QMainWindow.statusBar().addPermanentWidget(...)`. `set_counts`
keeps badges live; `set_health_report` flips the pill color + repopulates
the click-popover with current issues.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QWidget

from gui import tokens
from health_check import HealthIssue, HealthReport, SEVERITY_RANK

_PILL_PX = 12
_POPOVER_CAP = 20  # cap menu items so a flood doesn't make it unscrollable
_DETAIL_TRIM = 60


def _pill_color(severity: str | None) -> str:
    """Map severity to a theme-aware token color."""
    if severity is None:
        return tokens.token("state.success")
    if severity == "error":
        return tokens.token("state.error")
    return tokens.token("state.warning")  # info + warn share amber


class _ClickableLabel(QLabel):
    """QLabel that emits ``clicked`` on left-mouse press."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class StatusBarWidget(QWidget):
    """Compact status display: health pill · status text · TT/FB/Done badges."""

    health_action_requested = Signal(object)  # HealthIssue

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Health pill — leftmost, clickable, pre-load gray.
        self.health_pill = _ClickableLabel()
        self.health_pill.setFixedSize(_PILL_PX, _PILL_PX)
        self.health_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.health_pill.setToolTip("Health status — click for details.")
        self.health_pill.clicked.connect(self._show_popover)
        self._apply_pill_color(None, pre_load=True)
        layout.addWidget(self.health_pill)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.tiktok_label = QLabel("TT: 0")
        layout.addWidget(self.tiktok_label)

        self.facebook_label = QLabel("FB: 0")
        layout.addWidget(self.facebook_label)

        self.done_label = QLabel("Done: 0")
        layout.addWidget(self.done_label)

        self._issues: list[HealthIssue] = []

    # ── public API ────────────────────────────────────────────────────────

    def set_counts(
        self,
        tiktok_queued: int,
        facebook_queued: int,
        done: int,
        status_text: str | None = None,
    ) -> None:
        """Update queue/done labels (and optional status text) in one call."""
        self.tiktok_label.setText(f"TT: {tiktok_queued}")
        self.facebook_label.setText(f"FB: {facebook_queued}")
        self.done_label.setText(f"Done: {done}")
        if status_text is not None:
            self.status_label.setText(status_text)

    def set_health_report(self, report: HealthReport) -> None:
        """Update pill color + cache issues for the popover."""
        self._issues = list(report.issues)
        sev = report.max_severity()
        self.health_pill.setProperty("severity", sev or "ok")
        self._apply_pill_color(sev)
        self.health_pill.setToolTip(self._tooltip_for(sev))

    # ── internals ─────────────────────────────────────────────────────────

    def _apply_pill_color(self, severity: str | None, *, pre_load: bool = False) -> None:
        color = "#9CA3AF" if pre_load else _pill_color(severity)
        radius = _PILL_PX // 2
        self.health_pill.setStyleSheet(
            f"QLabel {{ background: {color}; border-radius: {radius}px; }}"
        )

    def _tooltip_for(self, severity: str | None) -> str:
        if not self._issues:
            return "Health: all good."
        return f"Health: {severity or 'ok'} — {len(self._issues)} issue(s). Click for details."

    def _show_popover(self) -> None:
        menu = QMenu(self)
        if not self._issues:
            menu.addAction("All good — no issues.").setEnabled(False)
            menu.exec(self._popover_anchor())
            return

        # Sort error → warn → info, then bound the list.
        ordered = sorted(
            self._issues,
            key=lambda i: -SEVERITY_RANK.get(i.severity, 0),
        )
        for issue in ordered[:_POPOVER_CAP]:
            text = issue.title
            if issue.detail:
                snippet = issue.detail[:_DETAIL_TRIM]
                text = f"{text} — {snippet}"
            action = QAction(text, menu)
            action.setData(issue)
            action.triggered.connect(
                lambda _checked=False, i=issue: self.health_action_requested.emit(i)
            )
            menu.addAction(action)
        if len(ordered) > _POPOVER_CAP:
            overflow = QAction(
                f"… and {len(ordered) - _POPOVER_CAP} more — see Settings ▸ Health",
                menu,
            )
            overflow.setEnabled(False)
            menu.addAction(overflow)
        menu.exec(self._popover_anchor())

    def _popover_anchor(self) -> QPoint:
        """Open the menu just below the pill (cosmetic; KISS)."""
        return self.health_pill.mapToGlobal(QPoint(0, self.health_pill.height()))
