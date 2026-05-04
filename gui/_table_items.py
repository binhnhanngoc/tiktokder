"""Shared QTableWidget item helpers.

Kept private (``_table_items``) — these are GUI-internal building blocks,
not part of any public API. Used by both ``library_panel`` and
``base_browser_panel`` so size/duration/view-count cells sort numerically
rather than as their human-readable text.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidgetItem


class NumericItem(QTableWidgetItem):
    """Table item that sorts by a stored numeric value, displays an arbitrary string.

    Lets cells like "1.5 MB" / "2:30" / "1,234,567" compare by their backing
    integer rather than alphabetically.
    """

    def __init__(self, value: int, display: str) -> None:
        super().__init__(display)
        self._sort_value = value

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)  # type: ignore[arg-type]
