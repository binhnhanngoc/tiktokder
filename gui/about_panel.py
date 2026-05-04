"""About-tab panel widget — version + update-status pill + Check now.

Replaces the static HTML About tab with a live widget that shows one of
four pill states (`unknown`, `stale`, `up_to_date`, `available`) derived
from ``MainWindow._latest_release_cache`` plus the persisted last-check
timestamp. Reuses ``MainWindow._on_check_updates_manual`` for the button
and ``MainWindow._show_update_dialog`` for the clickable amber pill so
the entire update flow stays in one place.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from update_checker import is_newer
from version import __version__, __version_info__

if TYPE_CHECKING:  # pragma: no cover
    from gui.main_window import MainWindow


_PILL_STYLE_BASE = "padding: 2px 10px; border-radius: 9px; font-weight: 600;"
_PILL_STYLE_GREEN = f"background: #1f7a1f; color: white; {_PILL_STYLE_BASE}"
_PILL_STYLE_AMBER = f"background: #c47b00; color: white; {_PILL_STYLE_BASE}"
_PILL_STYLE_GREY = f"background: #666; color: white; {_PILL_STYLE_BASE}"


_POWERED_BY_HTML = """
<p>Batch video downloader for TikTok and Facebook.</p>
<h3>Powered by</h3>
<ul>
  <li><a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> &mdash; extraction</li>
  <li><a href="https://www.qt.io/qt-for-python">PySide6</a> &mdash; GUI</li>
  <li><a href="https://playwright.dev/python/">Playwright</a> &mdash; Facebook scrape</li>
  <li><a href="https://rich.readthedocs.io/">Rich</a> &mdash; CLI progress UI</li>
</ul>
<p><b>License:</b> MIT.</p>
<p><small>No watermarks, no API keys, no telemetry. Use responsibly and
respect each platform's terms of service.</small></p>
"""


def _human_delta(epoch: float) -> str:
    """Render an epoch-seconds delta as human-readable English. Returns ``"—"``
    for the never-checked sentinel ``0.0``.
    """
    if epoch <= 0.0:
        return "—"
    delta = max(0.0, time.time() - epoch)
    if delta < 60:
        return "just now"
    if delta < 3600:
        m = int(delta // 60)
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if delta < 86400:
        h = int(delta // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    d = int(delta // 86400)
    return f"{d} day{'s' if d != 1 else ''} ago"


class AboutPanel(QWidget):
    """Live About-tab body: version title + status pill + Check now + credits.

    Tolerates ``main_window=None`` for unit-tests of HelpDialog: pill drops
    to ``unknown`` and the Check now button becomes a no-op.
    """

    def __init__(
        self,
        main_window: Optional["MainWindow"] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._build_ui()
        self._refresh_pill()
        if main_window is not None and hasattr(main_window, "update_check_finished"):
            try:
                main_window.update_check_finished.connect(self._refresh_pill)
            except Exception:
                pass

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(f"<h2>TikTokDer v{__version__}</h2>")
        title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title)

        pill_row = QHBoxLayout()
        self._pill = QLabel()
        self._pill.setTextFormat(Qt.TextFormat.RichText)
        self._pill.setOpenExternalLinks(False)
        self._pill.linkActivated.connect(self._on_pill_link_activated)
        pill_row.addWidget(self._pill)
        pill_row.addSpacing(8)
        self._check_now_btn = QPushButton("Check now")
        self._check_now_btn.clicked.connect(self._on_check_now_clicked)
        pill_row.addWidget(self._check_now_btn)
        pill_row.addStretch(1)
        layout.addLayout(pill_row)

        body = QTextBrowser()
        body.setOpenLinks(False)
        body.setOpenExternalLinks(False)
        body.anchorClicked.connect(self._on_anchor_clicked)
        body.setHtml(_POWERED_BY_HTML)
        layout.addWidget(body, stretch=1)

    @Slot()
    def _refresh_pill(self) -> None:
        """Re-derive pill state from MainWindow snapshot and re-style."""
        mw = self._main_window
        cached = getattr(mw, "_latest_release_cache", None) if mw is not None else None
        last_check = (
            getattr(mw.config, "last_update_check_at", 0.0) if mw is not None else 0.0
        )

        if cached is not None and is_newer(cached.version, __version_info__):
            text = f"▲ <a href='open' style='color: white; text-decoration: none;'>v{cached.version_str} available</a>"
            style = _PILL_STYLE_AMBER
        elif cached is not None:
            text = "● Up to date"
            style = _PILL_STYLE_GREEN
        elif last_check > 0.0:
            text = f"○ Last checked: {_human_delta(last_check)}"
            style = _PILL_STYLE_GREY
        else:
            text = "○ Never checked"
            style = _PILL_STYLE_GREY

        self._pill.setText(text)
        self._pill.setStyleSheet(style)

    @Slot()
    def _on_check_now_clicked(self) -> None:
        mw = self._main_window
        if mw is not None and hasattr(mw, "_on_check_updates_manual"):
            mw._on_check_updates_manual()

    @Slot(str)
    def _on_pill_link_activated(self, _href: str) -> None:
        mw = self._main_window
        cached = getattr(mw, "_latest_release_cache", None) if mw is not None else None
        if mw is not None and cached is not None and hasattr(mw, "_show_update_dialog"):
            mw._show_update_dialog(cached)

    def _on_anchor_clicked(self, url) -> None:
        from PySide6.QtGui import QDesktopServices

        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
