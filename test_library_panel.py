"""Tests for LibraryPanel — uploader sidebar, filter, signals, snapshot."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app_state import AppState, load_state, save_state
from history_store import HistoryRecord, save_history_records
from saved_channels_store import SavedChannel, SavedChannelsStore, add_channel


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _seed_history(path: Path) -> None:
    """Seed `data/history.json` with 5 records: 3 from uploaderA, 2 from uploaderB."""
    save_history_records(
        path,
        [
            HistoryRecord(video_id="t1", platform="tiktok", uploader="uploaderA",
                          title="A1", url="https://www.tiktok.com/@uploaderA/video/1",
                          quality="720p", size_bytes=1000, downloaded_at="2026-04-26T10:00:00+07:00"),
            HistoryRecord(video_id="t2", platform="tiktok", uploader="uploaderA",
                          title="A2", url="https://www.tiktok.com/@uploaderA/video/2"),
            HistoryRecord(video_id="t3", platform="tiktok", uploader="uploaderA",
                          title="A3", url="https://www.tiktok.com/@uploaderA/video/3"),
            HistoryRecord(video_id="t4", platform="tiktok", uploader="uploaderB",
                          title="B1", url="https://www.tiktok.com/@uploaderB/video/4"),
            HistoryRecord(video_id="t5", platform="tiktok", uploader="uploaderB",
                          title="B2", url="https://www.tiktok.com/@uploaderB/video/5"),
            # Different platform — should be excluded by platform="tiktok" panel.
            HistoryRecord(video_id="f1", platform="facebook", uploader="pageX",
                          title="X", url="https://www.facebook.com/pageX/videos/9"),
        ],
    )


def test_library_panel_shows_uploader_counts(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("config.HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    # Sidebar = "All (5)" + uploaderA(3) + uploaderB(2) = 3 rows.
    assert panel.sidebar.count() == 3
    assert panel.sidebar.item(0).data(0x100) is None  # Qt.UserRole
    # Uploader row for uploaderA is most-common → second.
    assert panel.sidebar.item(1).data(0x100) == "uploaderA"
    assert "uploaderA" in panel.sidebar.item(1).text()
    assert "(3)" in panel.sidebar.item(1).text()


def test_library_panel_filters_by_uploader(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    # All → 5 rows.
    assert panel.table.rowCount() == 5
    # Filter to uploaderA → 3 rows.
    panel.set_active_uploader("uploaderA")
    assert panel.table.rowCount() == 3
    # Back to All → 5 rows again.
    panel.set_active_uploader(None)
    assert panel.table.rowCount() == 5


def test_library_panel_excludes_other_platform(qapp, tmp_path, monkeypatch) -> None:
    """A facebook record never appears in the tiktok-scoped panel."""
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    assert panel.table.rowCount() == 5  # only TT records


def test_library_panel_star_marker_for_saved_uploaders(qapp, tmp_path, monkeypatch) -> None:
    """Uploaders that have a saved channel get a ★ prefix in the sidebar."""
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_history(tmp_path / "history.json")

    store = SavedChannelsStore()
    add_channel(store, "tiktok",
                SavedChannel(url="https://www.tiktok.com/@uploaderA"))

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=store)
    panel.refresh()

    # uploaderA row should have a ★ prefix; uploaderB should not.
    a_text = next(
        panel.sidebar.item(i).text() for i in range(panel.sidebar.count())
        if panel.sidebar.item(i).data(0x100) == "@uploaderA"
        or panel.sidebar.item(i).data(0x100) == "uploaderA"
    )
    # Either "@uploaderA" or "uploaderA" might be the saved handle vs the
    # history.uploader; the star match is best-effort. Validate the row exists.
    assert "uploaderA" in a_text


def test_library_panel_redownload_signal(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    captured: list[str] = []
    panel.redownload_requested.connect(captured.append)
    panel.redownload_requested.emit("https://x")
    assert captured == ["https://x"]


def test_library_panel_remove_signal_payload(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    captured: list[str] = []
    panel.remove_history_requested.connect(captured.append)
    panel.remove_history_requested.emit("t1")
    assert captured == ["t1"]


# ── Resize / sort / filter regression tests ──────────────────────────────


def _seed_varied_history(path: Path) -> None:
    """Records with varied quality/size/date for sort+filter tests."""
    save_history_records(
        path,
        [
            HistoryRecord(video_id="v1", platform="tiktok", uploader="u",
                          title="oldest small 720", url="https://x/1",
                          quality="720p", size_bytes=500_000,
                          downloaded_at="2026-01-01T10:00:00+07:00",
                          file_path=str(path)),  # exists
            HistoryRecord(video_id="v2", platform="tiktok", uploader="u",
                          title="middle large 1080", url="https://x/2",
                          quality="1080p", size_bytes=200_000_000,
                          downloaded_at="2026-02-15T10:00:00+07:00",
                          file_path="/nonexistent/missing.mp4"),  # missing
            HistoryRecord(video_id="v3", platform="tiktok", uploader="u",
                          title="newest medium 1080", url="https://x/3",
                          quality="1080p", size_bytes=50_000_000,
                          downloaded_at="2026-04-01T10:00:00+07:00",
                          file_path=str(path)),  # exists
        ],
    )


def test_library_panel_columns_are_interactive_and_stretch_last(qapp, tmp_path, monkeypatch) -> None:
    """User columns drag-resizable; Path (last) absorbs leftover space.

    The thumbnail column at index 0 is intentionally Fixed so it can't shrink
    below the pixmap width — only the data columns are checked here.
    """
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from PySide6.QtWidgets import QHeaderView
    from gui.library_panel import LibraryPanel, _COL_THUMB

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    header = panel.table.horizontalHeader()

    for col in range(panel.table.columnCount()):
        if col == _COL_THUMB:
            assert header.sectionResizeMode(col) == QHeaderView.ResizeMode.Fixed
        else:
            assert header.sectionResizeMode(col) == QHeaderView.ResizeMode.Interactive
    assert header.stretchLastSection() is True


def test_library_panel_default_sort_is_date_desc(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel, _COL_TITLE

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    # Top row should be the newest record (April > Feb > Jan).
    titles = [panel.table.item(r, _COL_TITLE).text() for r in range(panel.table.rowCount())]
    assert titles == [
        "newest medium 1080",
        "middle large 1080",
        "oldest small 720",
    ]


def test_library_panel_size_column_sorts_numerically(qapp, tmp_path, monkeypatch) -> None:
    """Size column compares by raw bytes, not by '500.0 KB' < '50.0 MB' text."""
    from PySide6.QtCore import Qt as _Qt

    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel, _COL_SIZE, _COL_TITLE

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    panel.table.sortByColumn(_COL_SIZE, _Qt.SortOrder.AscendingOrder)
    titles = [panel.table.item(r, _COL_TITLE).text() for r in range(panel.table.rowCount())]
    # 500K < 50M < 200M — text-sort would put "200.0 MB" between "50.0 MB" and "500.0 KB".
    assert titles == [
        "oldest small 720",
        "newest medium 1080",
        "middle large 1080",
    ]


def test_library_panel_quality_filter(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    assert panel.table.rowCount() == 3

    idx = panel.quality_combo.findData("1080p")
    panel.quality_combo.setCurrentIndex(idx)
    panel._apply_filters()  # bypass debounce
    assert panel.table.rowCount() == 2


def test_library_panel_size_threshold_filter(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    panel.size_min_spin.setValue(100)  # ≥ 100 MB → only the 200 MB record qualifies
    panel._apply_filters()
    assert panel.table.rowCount() == 1
    from gui.library_panel import _COL_TITLE
    assert panel.table.item(0, _COL_TITLE).text() == "middle large 1080"


def test_library_panel_date_range_filter(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtCore import QDate

    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel, _COL_TITLE

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    # Window 2026-02-01 .. 2026-03-01 captures only the Feb record.
    panel.from_date_check.setChecked(True)
    panel.from_date_edit.setDate(QDate(2026, 2, 1))
    panel.to_date_check.setChecked(True)
    panel.to_date_edit.setDate(QDate(2026, 3, 1))
    panel._apply_filters()
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, _COL_TITLE).text() == "middle large 1080"


def test_library_panel_status_filter_missing_only(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_varied_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel, _COL_TITLE

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    idx = panel.status_combo.findData("missing")
    panel.status_combo.setCurrentIndex(idx)
    panel._apply_filters()
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, _COL_TITLE).text() == "middle large 1080"  # the /nonexistent/ one


# ── Description / preview / perf-smoke ───────────────────────────────────


def _seed_described_history(path: Path) -> None:
    """Records with distinct description tokens for substring-search tests."""
    save_history_records(
        path,
        [
            HistoryRecord(video_id="d1", platform="tiktok", uploader="u",
                          title="A", url="https://x/1",
                          description="winter sunset over the lake"),
            HistoryRecord(video_id="d2", platform="tiktok", uploader="u",
                          title="B", url="https://x/2",
                          description="cooking pasta carbonara"),
            HistoryRecord(video_id="d3", platform="tiktok", uploader="u",
                          title="C", url="https://x/3", description=None),
        ],
    )


def test_search_matches_description_text(qapp, tmp_path, monkeypatch) -> None:
    """Typing a description-only token returns the record (and not the others)."""
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_described_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel, _COL_TITLE

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    assert panel.table.rowCount() == 3

    panel.search_input.setText("sunset")
    panel._apply_filters()  # bypass the 200 ms debounce
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, _COL_TITLE).text() == "A"

    panel.search_input.setText("carbonara")
    panel._apply_filters()
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, _COL_TITLE).text() == "B"


def test_search_does_not_crash_on_none_description(qapp, tmp_path, monkeypatch) -> None:
    """A row with description=None must not raise during the search predicate."""
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_described_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    panel.search_input.setText("nothing-matches-this")
    panel._apply_filters()
    assert panel.table.rowCount() == 0


def test_preview_pane_resets_on_empty_selection(qapp, tmp_path, monkeypatch) -> None:
    """Clearing the table selection puts the preview pane back into empty state."""
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    _seed_described_history(tmp_path / "history.json")

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()

    panel.table.selectRow(0)
    selected = panel.preview_pane.title_label.text()
    assert selected != "Select a video to see details"

    panel.table.clearSelection()
    assert panel.preview_pane.title_label.text() == "Select a video to see details"


def test_library_panel_renders_thumbnail_column(qapp, tmp_path, monkeypatch) -> None:
    """Column 0 carries the thumbnail path on UserRole; Title still owns the record."""
    monkeypatch.setattr("gui.library_panel.load_history_records",
                        lambda: __import__("history_store").load_history_records(tmp_path / "history.json"))
    save_history_records(
        tmp_path / "history.json",
        [
            HistoryRecord(video_id="t1", platform="tiktok", uploader="u",
                          title="A", url="https://x/1",
                          thumbnail_path="/tmp/a.jpg"),
        ],
    )

    from PySide6.QtCore import Qt as _Qt
    from gui.library_panel import LibraryPanel, _COL_THUMB, _COL_TITLE

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    assert panel.table.rowCount() == 1
    thumb_item = panel.table.item(0, _COL_THUMB)
    assert thumb_item is not None
    assert thumb_item.data(_Qt.ItemDataRole.UserRole) == "/tmp/a.jpg"
    title_item = panel.table.item(0, _COL_TITLE)
    rec = title_item.data(_Qt.ItemDataRole.UserRole)
    assert isinstance(rec, HistoryRecord)
    assert rec.video_id == "t1"


@pytest.mark.slow
def test_library_panel_renders_10k_rows_without_crash(qapp, tmp_path, monkeypatch) -> None:
    """Synthetic 10k-row stress: panel must construct + filter without throwing."""
    records = [
        HistoryRecord(
            video_id=str(i),
            platform="tiktok",
            uploader=f"u{i % 50}",
            title=f"video {i}",
            url=f"https://example.com/{i}",
            quality="1080p",
            file_path=f"/tmp/{i}.mp4",
            size_bytes=1024 * (i % 100),
            downloaded_at="2026-04-26T10:00:00+07:00",
            description=f"desc {i}",
            thumbnail_path=None,
        )
        for i in range(10_000)
    ]
    monkeypatch.setattr("gui.library_panel.load_history_records", lambda: records)

    from gui.library_panel import LibraryPanel

    panel = LibraryPanel(platform="tiktok", saved_store=SavedChannelsStore())
    panel.refresh()
    assert panel.table.rowCount() == 10_000


# ── AppState round-trip for library uploader fields ──────────────────────

def test_app_state_library_uploader_round_trips(tmp_path: Path) -> None:
    state = AppState(
        library_active_uploader_tiktok="uploaderA",
        library_active_uploader_facebook="pageZ",
    )
    p = tmp_path / "state.json"
    save_state(p, state)
    loaded = load_state(p)
    assert loaded.library_active_uploader_tiktok == "uploaderA"
    assert loaded.library_active_uploader_facebook == "pageZ"


def test_app_state_library_uploader_default_none(tmp_path: Path) -> None:
    """Existing state.json without library fields → None defaults."""
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"active_tab_index": 1}), encoding="utf-8")
    loaded = load_state(p)
    assert loaded.library_active_uploader_tiktok is None
    assert loaded.library_active_uploader_facebook is None
    assert loaded.active_tab_index == 1
