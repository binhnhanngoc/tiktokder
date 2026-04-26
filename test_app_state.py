"""Tests for app_state — load/save/migrate/empty/malformed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app_state import (
    AppState,
    BrowserPanelState,
    QueueItemState,
    VideoInfoState,
    clear_state_section,
    load_state,
    save_state,
)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "state.json"


def test_load_missing_file_returns_defaults(state_path: Path) -> None:
    state = load_state(state_path)
    assert state == AppState()
    assert state.download_queue == []
    assert state.tiktok_browser.url == ""
    assert state.facebook_browser.max_scrolls is None


def test_load_malformed_json_returns_defaults(state_path: Path) -> None:
    state_path.write_text("not json {{", encoding="utf-8")
    assert load_state(state_path) == AppState()


def test_load_non_dict_top_level_returns_defaults(state_path: Path) -> None:
    state_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_state(state_path) == AppState()


def test_load_empty_file_returns_defaults(state_path: Path) -> None:
    state_path.write_text("", encoding="utf-8")
    assert load_state(state_path) == AppState()


def test_save_and_load_roundtrip(state_path: Path) -> None:
    original = AppState(
        active_tab_index=2,
        channel_active_sub_tab=1,
        download_queue=[
            QueueItemState(url="https://www.tiktok.com/@u/video/1", status="Complete", title="hi"),
            QueueItemState(url="https://www.facebook.com/v/2", status="Failed"),
        ],
        tiktok_browser=BrowserPanelState(
            url="https://www.tiktok.com/@u",
            videos=[
                VideoInfoState(url="https://x/1", title="t1", video_id="1", quality="720p"),
            ],
        ),
        facebook_browser=BrowserPanelState(
            url="https://www.facebook.com/p",
            videos=[VideoInfoState(url="https://y/2", title="t2", video_id="2")],
            max_scrolls=15,
        ),
    )
    save_state(state_path, original)

    loaded = load_state(state_path)
    assert loaded == original


def test_save_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "sub" / "nested" / "state.json"
    save_state(nested, AppState(active_tab_index=1))
    assert nested.exists()
    assert load_state(nested).active_tab_index == 1


def test_load_drops_invalid_queue_entries(state_path: Path) -> None:
    state_path.write_text(
        json.dumps(
            {
                "download_queue": [
                    {"url": "https://ok/1", "status": "Queued"},
                    {"url": ""},                    # empty url -> dropped
                    {"status": "Failed"},           # missing url -> dropped
                    "not a dict",                   # wrong type -> dropped
                    {"url": "https://ok/2", "title": "t"},
                ],
            }
        ),
        encoding="utf-8",
    )
    state = load_state(state_path)
    assert [q.url for q in state.download_queue] == ["https://ok/1", "https://ok/2"]


def test_load_ignores_unknown_fields(state_path: Path) -> None:
    state_path.write_text(
        json.dumps(
            {
                "active_tab_index": 1,
                "download_queue": [
                    {"url": "https://x", "status": "Queued", "extra_garbage": True},
                ],
                "tiktok_browser": {
                    "url": "u",
                    "videos": [{"url": "https://v", "future_field": 123}],
                },
                "future_top_level_field": {"anything": True},
            }
        ),
        encoding="utf-8",
    )
    state = load_state(state_path)
    assert state.active_tab_index == 1
    assert state.download_queue[0].url == "https://x"
    assert state.tiktok_browser.videos[0].url == "https://v"


def test_load_handles_videos_list_not_a_list(state_path: Path) -> None:
    state_path.write_text(
        json.dumps({"tiktok_browser": {"url": "u", "videos": "oops"}}),
        encoding="utf-8",
    )
    state = load_state(state_path)
    assert state.tiktok_browser.url == "u"
    assert state.tiktok_browser.videos == []


def test_load_coerces_bad_max_scrolls(state_path: Path) -> None:
    state_path.write_text(
        json.dumps({"facebook_browser": {"url": "u", "max_scrolls": "not-a-number"}}),
        encoding="utf-8",
    )
    state = load_state(state_path)
    assert state.facebook_browser.max_scrolls is None


def test_load_coerces_int_active_tab(state_path: Path) -> None:
    state_path.write_text(
        json.dumps({"active_tab_index": "garbage"}),
        encoding="utf-8",
    )
    state = load_state(state_path)
    assert state.active_tab_index == 0


def test_clear_state_section_wipes_queue_only(state_path: Path) -> None:
    save_state(
        state_path,
        AppState(
            active_tab_index=1,
            download_queue=[QueueItemState(url="https://x")],
            tiktok_browser=BrowserPanelState(url="kept"),
        ),
    )
    clear_state_section(state_path, clear_queue=True)
    state = load_state(state_path)
    assert state.download_queue == []
    assert state.active_tab_index == 1
    assert state.tiktok_browser.url == "kept"


def test_clear_state_section_noop_when_file_missing(state_path: Path) -> None:
    # Should not create the file or raise.
    clear_state_section(state_path, clear_queue=True)
    assert not state_path.exists()


def test_load_preserves_queue_order(state_path: Path) -> None:
    urls = [f"https://x/{i}" for i in range(5)]
    save_state(
        state_path,
        AppState(download_queue=[QueueItemState(url=u) for u in urls]),
    )
    state = load_state(state_path)
    assert [q.url for q in state.download_queue] == urls
