"""Tests for BaseBrowserPanel filter row + sort + hide-aware select.

Covers Phase 1 of the channel-filters plan: search predicate, quality combo,
date range, hidden-row select-all, hidden-row download-selected, and the
no-mutation invariant on `_videos`.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from channel_fetcher import VideoInfo
from gui.base_browser_panel import BaseBrowserPanel


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


class _Panel(BaseBrowserPanel):
    """Concrete subclass with a no-op fetcher — we drive `_on_video_found` directly."""

    def _create_fetcher(self, url: str):
        return None


def _push(panel: BaseBrowserPanel, **kwargs) -> VideoInfo:
    """Build + insert one VideoInfo into the panel's table."""
    defaults = dict(
        url="https://example.com/v",
        title="Untitled",
        duration=30,
        view_count=100,
        upload_date="20240101",
        video_id="x",
        quality="720p",
    )
    defaults.update(kwargs)
    v = VideoInfo(**defaults)
    panel._on_video_found(v)
    return v


def test_search_filter_hides_non_matching_titles(qapp):
    panel = _Panel(placeholder="…")
    _push(panel, title="Funny cat compilation", video_id="1", url="u1")
    _push(panel, title="Dog tricks", video_id="2", url="u2")
    _push(panel, title="cat in box", video_id="3", url="u3")

    panel.search_input.setText("cat")
    panel._apply_filters()

    assert not panel.table.isRowHidden(0)
    assert panel.table.isRowHidden(1)
    assert not panel.table.isRowHidden(2)


def test_quality_filter(qapp):
    panel = _Panel(placeholder="…")
    _push(panel, title="A", video_id="1", url="u1", quality="720p")
    _push(panel, title="B", video_id="2", url="u2", quality="1080p")
    panel._rebuild_quality_combo()
    idx = panel.quality_combo.findData("1080p")
    panel.quality_combo.setCurrentIndex(idx)
    panel._apply_filters()

    assert panel.table.isRowHidden(0)
    assert not panel.table.isRowHidden(1)


def test_date_from_to_range(qapp):
    panel = _Panel(placeholder="…")
    _push(panel, title="old", video_id="1", url="u1", upload_date="20230101")
    _push(panel, title="mid", video_id="2", url="u2", upload_date="20240601")
    _push(panel, title="new", video_id="3", url="u3", upload_date="20250101")

    panel.from_date_check.setChecked(True)
    panel.from_date_edit.setDate(QDate(2024, 1, 1))
    panel.to_date_check.setChecked(True)
    panel.to_date_edit.setDate(QDate(2024, 12, 31))
    panel._apply_filters()

    assert panel.table.isRowHidden(0)        # 2023 — before
    assert not panel.table.isRowHidden(1)    # 2024 — within
    assert panel.table.isRowHidden(2)        # 2025 — after


def test_select_all_skips_hidden_rows(qapp):
    panel = _Panel(placeholder="…")
    _push(panel, title="cat", video_id="1", url="u1")
    _push(panel, title="dog", video_id="2", url="u2")
    # Both rows visible; deselect everything as a clean baseline.
    panel._deselect_all()
    cb_visible = panel.table.cellWidget(0, 0)
    cb_hidden = panel.table.cellWidget(1, 0)
    assert cb_visible.isChecked() is False
    assert cb_hidden.isChecked() is False

    # Hide the dog row, then Select All — must not flip the hidden checkbox.
    panel.search_input.setText("cat")
    panel._apply_filters()
    panel._select_all()

    assert cb_visible.isChecked() is True
    assert cb_hidden.isChecked() is False


def test_download_selected_emits_only_visible_urls(qapp):
    panel = _Panel(placeholder="…")
    _push(panel, title="cat", video_id="1", url="https://e/cat")
    _push(panel, title="dog", video_id="2", url="https://e/dog")
    panel.search_input.setText("cat")
    panel._apply_filters()

    received: list[tuple[list[str], str]] = []
    panel.download_requested.connect(lambda urls, hint: received.append((urls, hint)))
    panel._on_download()

    assert len(received) == 1
    urls, _ = received[0]
    assert urls == ["https://e/cat"]


def test_videos_list_never_mutated_by_filter(qapp):
    panel = _Panel(placeholder="…")
    for i in range(3):
        _push(panel, title=f"t{i}", video_id=str(i), url=f"u{i}")
    panel.search_input.setText("nomatch")
    panel._apply_filters()

    assert len(panel._videos) == 3


def test_table_sorting_enabled_default_date_desc(qapp):
    panel = _Panel(placeholder="…")
    assert panel.table.isSortingEnabled() is True
    # Default sort indicator on Date column — use sortColumn() check.
    header = panel.table.horizontalHeader()
    assert header.sortIndicatorSection() == 5  # _COL_DATE


def test_live_insert_with_active_filter_and_sort_keeps_visibility_correct(qapp):
    """Regression: re-enabling sort after insert can reorder rows; the predicate
    must apply by current row index, not by the captured pre-sort index.

    Without the fix: pushing a 2025 video while a `from=2024-01-01` filter is
    active would un-hide the older 2020 video that should remain hidden,
    because Date-DESC sort moves the new row to position 0 and the old row
    inherits the captured `row=1` setRowHidden(False) call.
    """
    panel = _Panel(placeholder="…")
    panel.from_date_check.setChecked(True)
    panel.from_date_edit.setDate(QDate(2024, 1, 1))

    _push(panel, title="old", video_id="1", url="u1", upload_date="20200101")
    _push(panel, title="new", video_id="2", url="u2", upload_date="20250101")

    # Find each video's current row by scanning UserRole — sort may have
    # reordered them. Then assert hidden state matches the predicate.
    for r in range(panel.table.rowCount()):
        item = panel.table.item(r, 1)
        v = item.data(0x100)  # Qt.ItemDataRole.UserRole
        if v.video_id == "1":
            assert panel.table.isRowHidden(r) is True   # 2020 — outside filter
        elif v.video_id == "2":
            assert panel.table.isRowHidden(r) is False  # 2025 — within filter
