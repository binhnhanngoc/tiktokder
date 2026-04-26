"""Tests for saved_channels_store.py — round-trip, cap, filter logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from saved_channels_store import (
    DEFAULT_MAX_PER_PLATFORM,
    SCHEMA_VERSION,
    SavedChannel,
    SavedChannelsStore,
    add_channel,
    load_saved_channels,
    mark_fetched,
    remove_channel,
    save_saved_channels,
    select_new_videos,
    update_channel,
)


@dataclass
class _FakeVideo:
    """Lightweight stand-in for channel_fetcher.VideoInfo (no Qt dep)."""

    video_id: str
    url: str = ""
    upload_date: str | None = None


# ─── Load / save ───────────────────────────────────────────────────────────

def test_load_missing_file_returns_empty_store(tmp_path: Path) -> None:
    store = load_saved_channels(tmp_path / "nope.json")
    assert store.tiktok == []
    assert store.facebook == []


def test_load_malformed_json_returns_empty_store(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    p.write_text("{not valid json", encoding="utf-8")
    store = load_saved_channels(p)
    assert store.tiktok == []
    assert store.facebook == []


def test_load_unrecognised_shape_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    store = load_saved_channels(p)
    assert store.tiktok == []
    assert store.facebook == []


def test_round_trip_add_save_load(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://www.tiktok.com/@a", nickname="A"))
    add_channel(store, "facebook", SavedChannel(url="https://www.facebook.com/b"))
    save_saved_channels(p, store)

    loaded = load_saved_channels(p)
    assert [c.url for c in loaded.tiktok] == ["https://www.tiktok.com/@a"]
    assert loaded.tiktok[0].nickname == "A"
    assert [c.url for c in loaded.facebook] == ["https://www.facebook.com/b"]


def test_persisted_schema_version(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    save_saved_channels(p, SavedChannelsStore())
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["schema"] == SCHEMA_VERSION


def test_load_ignores_unknown_keys_on_channel(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    p.write_text(
        json.dumps(
            {
                "schema": 1,
                "tiktok": [
                    {"url": "https://www.tiktok.com/@a", "rogue_field": 42, "nickname": "A"}
                ],
                "facebook": [],
            }
        ),
        encoding="utf-8",
    )
    store = load_saved_channels(p)
    assert len(store.tiktok) == 1
    assert store.tiktok[0].nickname == "A"


def test_load_skips_entries_missing_url(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    p.write_text(
        json.dumps(
            {
                "schema": 1,
                "tiktok": [{"nickname": "no url"}, {"url": "https://www.tiktok.com/@a"}],
                "facebook": [],
            }
        ),
        encoding="utf-8",
    )
    store = load_saved_channels(p)
    assert len(store.tiktok) == 1
    assert store.tiktok[0].url == "https://www.tiktok.com/@a"


# ─── CRUD ──────────────────────────────────────────────────────────────────

def test_add_duplicate_url_returns_false() -> None:
    store = SavedChannelsStore()
    ch = SavedChannel(url="https://www.tiktok.com/@a")
    assert add_channel(store, "tiktok", ch) is True
    assert add_channel(store, "tiktok", ch) is False
    assert len(store.tiktok) == 1


def test_remove_channel_returns_false_when_missing() -> None:
    store = SavedChannelsStore()
    assert remove_channel(store, "tiktok", "https://nope") is False


def test_remove_channel_removes_existing() -> None:
    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://x"))
    assert remove_channel(store, "tiktok", "https://x") is True
    assert store.tiktok == []


def test_update_channel_mutates_fields() -> None:
    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://x"))
    assert update_channel(store, "tiktok", "https://x", nickname="renamed", starred=True) is True
    ch = store.find_by_url("tiktok", "https://x")
    assert ch.nickname == "renamed"
    assert ch.starred is True


def test_mark_fetched_updates_fetch_state() -> None:
    store = SavedChannelsStore()
    add_channel(store, "tiktok", SavedChannel(url="https://x"))
    ok = mark_fetched(store, "tiktok", "https://x", ["v1", "v2"], "2026-04-26T10:00:00+07:00")
    assert ok is True
    ch = store.find_by_url("tiktok", "https://x")
    assert ch.last_fetched_video_ids == ["v1", "v2"]
    assert ch.last_fetched_at == "2026-04-26T10:00:00+07:00"


# ─── Cap / FIFO ────────────────────────────────────────────────────────────

def test_cap_enforced_drops_oldest_by_last_fetched_at() -> None:
    store = SavedChannelsStore()
    cap = 3
    # Add 3 channels with progressively newer fetch times.
    for i, iso in enumerate(["2026-01-01T00:00:00+00:00",
                             "2026-02-01T00:00:00+00:00",
                             "2026-03-01T00:00:00+00:00"]):
        add_channel(
            store,
            "tiktok",
            SavedChannel(url=f"https://x{i}", last_fetched_at=iso),
            cap=cap,
        )
    # Fourth add over cap → oldest (x0, Jan) drops.
    add_channel(
        store,
        "tiktok",
        SavedChannel(url="https://x3", last_fetched_at="2026-04-01T00:00:00+00:00"),
        cap=cap,
    )
    urls = {c.url for c in store.tiktok}
    assert "https://x0" not in urls
    assert urls == {"https://x1", "https://x2", "https://x3"}


def test_cap_treats_none_last_fetched_as_oldest() -> None:
    store = SavedChannelsStore()
    cap = 2
    add_channel(store, "tiktok", SavedChannel(url="https://has-date",
                                              last_fetched_at="2026-01-01T00:00:00+00:00"),
                cap=cap)
    add_channel(store, "tiktok", SavedChannel(url="https://no-date"), cap=cap)
    add_channel(store, "tiktok", SavedChannel(url="https://newest",
                                              last_fetched_at="2026-03-01T00:00:00+00:00"),
                cap=cap)
    urls = {c.url for c in store.tiktok}
    # None sorts oldest → no-date drops first.
    assert urls == {"https://has-date", "https://newest"}


# ─── select_new_videos ─────────────────────────────────────────────────────

def test_select_new_videos_id_only_when_no_upload_date() -> None:
    channel = SavedChannel(url="https://x", last_fetched_at=None)
    fetched = [
        _FakeVideo(video_id="v1", upload_date=None),
        _FakeVideo(video_id="v2", upload_date=None),
    ]
    result = select_new_videos(channel, fetched, history_ids={"v1"})
    assert [v.video_id for v in result] == ["v2"]


def test_select_new_videos_date_aware_path() -> None:
    channel = SavedChannel(url="https://x", last_fetched_at="2026-04-20T00:00:00+00:00")
    fetched = [
        _FakeVideo(video_id="old1", upload_date="20260415"),  # before cutoff
        _FakeVideo(video_id="new1", upload_date="20260425"),  # after cutoff
        _FakeVideo(video_id="dup1", upload_date="20260426"),  # in history
        _FakeVideo(video_id="undated", upload_date=None),     # missing date → kept (id-only)
    ]
    result = select_new_videos(channel, fetched, history_ids={"dup1"})
    ids = [v.video_id for v in result]
    assert ids == ["new1", "undated"]


def test_select_new_videos_when_last_fetched_at_none() -> None:
    channel = SavedChannel(url="https://x", last_fetched_at=None)
    fetched = [
        _FakeVideo(video_id="v1", upload_date="20260101"),  # date irrelevant w/o cutoff
        _FakeVideo(video_id="v2", upload_date="20260201"),
    ]
    result = select_new_videos(channel, fetched, history_ids={"v1"})
    assert [v.video_id for v in result] == ["v2"]


def test_select_new_videos_excludes_videos_without_id() -> None:
    channel = SavedChannel(url="https://x")
    fetched = [_FakeVideo(video_id="", upload_date=None), _FakeVideo(video_id="v")]
    result = select_new_videos(channel, fetched, history_ids=set())
    assert [v.video_id for v in result] == ["v"]


# ─── Atomic write ──────────────────────────────────────────────────────────

def test_save_overwrites_existing_file_atomically(tmp_path: Path) -> None:
    p = tmp_path / "saved.json"
    save_saved_channels(p, SavedChannelsStore(tiktok=[SavedChannel(url="https://a")]))
    save_saved_channels(p, SavedChannelsStore(tiktok=[SavedChannel(url="https://b")]))
    loaded = load_saved_channels(p)
    assert [c.url for c in loaded.tiktok] == ["https://b"]
