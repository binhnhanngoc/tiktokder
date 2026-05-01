"""Tests for history_store.py — HistoryRecord schema v3 and v1/v2 migration."""

import json

import pytest

from history_store import (
    HistoryRecord,
    SCHEMA_VERSION,
    _read_history_file,
    add_history_record,
    load_history_ids,
    load_history_records,
    save_history_ids,
    save_history_records,
)


def _record(vid: str, **kwargs) -> HistoryRecord:
    return HistoryRecord(video_id=vid, **kwargs)


class TestReadHistoryFile:
    def test_missing_file_returns_empty(self, tmp_path):
        path = tmp_path / "history.json"
        version, records = _read_history_file(path)
        assert version == 0
        assert records == []

    def test_v1_list_returns_bare_records(self, tmp_path):
        path = tmp_path / "history.json"
        path.write_text(json.dumps(["111", "222", "333"]), encoding="utf-8")
        version, records = _read_history_file(path)
        assert version == 1
        assert len(records) == 3
        assert {r.video_id for r in records} == {"111", "222", "333"}
        assert all(r.platform is None and r.title is None for r in records)

    def test_v2_dict_returns_full_records(self, tmp_path):
        path = tmp_path / "history.json"
        payload = {
            "schema": 2,
            "entries": [
                {"video_id": "1", "platform": "tiktok", "uploader": "@u", "title": "t"},
                {"video_id": "2", "platform": "facebook"},
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        version, records = _read_history_file(path)
        # On-disk shape is preserved on read; v2 → v3 promotion only happens
        # at write time, so the version reflects what was found on disk.
        assert version == 2
        assert len(records) == 2
        assert records[0].uploader == "@u"
        assert records[1].platform == "facebook"

    def test_v3_dict_returns_full_records_with_new_fields(self, tmp_path):
        path = tmp_path / "history.json"
        payload = {
            "schema": 3,
            "entries": [
                {
                    "video_id": "1",
                    "platform": "tiktok",
                    "description": "hello world",
                    "thumbnail_path": "/tmp/1.jpg",
                },
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        version, records = _read_history_file(path)
        assert version == SCHEMA_VERSION == 3
        assert records[0].description == "hello world"
        assert records[0].thumbnail_path == "/tmp/1.jpg"

    def test_malformed_json_returns_empty(self, tmp_path):
        path = tmp_path / "history.json"
        path.write_text("{{{not json", encoding="utf-8")
        version, records = _read_history_file(path)
        assert version == 0
        assert records == []

    def test_unrecognized_shape_returns_empty(self, tmp_path):
        path = tmp_path / "history.json"
        path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        version, records = _read_history_file(path)
        assert version == 0
        assert records == []

    def test_v2_skips_invalid_entries(self, tmp_path):
        path = tmp_path / "history.json"
        payload = {
            "schema": 2,
            "entries": [
                {"video_id": "1"},
                {"no_id": True},        # missing video_id — dropped
                "not a dict",           # wrong type — dropped
                {"video_id": "2", "extra_unknown": "x"},  # extra keys filtered
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        _, records = _read_history_file(path)
        assert {r.video_id for r in records} == {"1", "2"}


class TestLoadHistoryIds:
    def test_v1_and_v2_yield_same_ids(self, tmp_path):
        v1_path = tmp_path / "v1.json"
        v2_path = tmp_path / "v2.json"
        v1_path.write_text(json.dumps(["a", "b", "c"]), encoding="utf-8")
        v2_path.write_text(
            json.dumps({"schema": 2, "entries": [
                {"video_id": "a"}, {"video_id": "b"}, {"video_id": "c"},
            ]}),
            encoding="utf-8",
        )
        assert load_history_ids(v1_path) == load_history_ids(v2_path) == {"a", "b", "c"}


class TestSaveLoadRoundTrip:
    def test_v2_round_trip_preserves_fields(self, tmp_path):
        path = tmp_path / "history.json"
        records = [
            _record("1", platform="tiktok", uploader="@u", title="hello",
                    url="https://www.tiktok.com/@u/video/1", quality="720p",
                    file_path="/tmp/1.mp4", size_bytes=1024,
                    downloaded_at="2026-04-26T14:33:00+07:00"),
        ]
        save_history_records(path, records)
        loaded = load_history_records(path)
        assert loaded == records

    def test_save_writes_latest_schema(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_records(path, [_record("xyz")])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == SCHEMA_VERSION == 3
        assert data["entries"][0]["video_id"] == "xyz"
        # New v3 fields are present (as None) for records that don't set them.
        assert data["entries"][0]["description"] is None
        assert data["entries"][0]["thumbnail_path"] is None

    def test_save_history_ids_writes_latest_schema(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_ids(path, {"3", "1", "2"})
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == SCHEMA_VERSION == 3
        ids = sorted(e["video_id"] for e in data["entries"])
        assert ids == ["1", "2", "3"]

    def test_v2_file_round_trips_to_v3(self, tmp_path):
        path = tmp_path / "history.json"
        v2_payload = {
            "schema": 2,
            "entries": [{
                "video_id": "123",
                "platform": "tiktok",
                "uploader": "@alice",
                "title": "Hello",
                "url": "https://www.tiktok.com/@alice/video/123",
                "quality": "1080p",
                "file_path": "/tmp/x.mp4",
                "size_bytes": 1024,
                "downloaded_at": "2026-04-26T10:00:00+07:00",
            }],
        }
        path.write_text(json.dumps(v2_payload), encoding="utf-8")
        records = load_history_records(path)
        assert len(records) == 1
        assert records[0].video_id == "123"
        # New v3 fields default to None when reading a v2 file.
        assert records[0].description is None
        assert records[0].thumbnail_path is None
        # Re-saving promotes the file shape to v3 with the new fields present.
        save_history_records(path, records)
        reread = json.loads(path.read_text(encoding="utf-8"))
        assert reread["schema"] == 3
        entry = reread["entries"][0]
        assert entry["description"] is None
        assert entry["thumbnail_path"] is None
        # Old fields preserved verbatim.
        assert entry["uploader"] == "@alice"
        assert entry["size_bytes"] == 1024


class TestAddHistoryRecord:
    def test_appends_to_existing(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_records(path, [_record("a")])
        add_history_record(path, _record("b"))
        loaded = load_history_records(path)
        assert [r.video_id for r in loaded] == ["a", "b"]

    def test_fifo_cap_drops_oldest(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_records(path, [_record(str(i)) for i in range(5)])
        add_history_record(path, _record("new"), max_entries=3)
        loaded = load_history_records(path)
        # 5 existing + 1 new = 6 → trimmed to last 3.
        assert [r.video_id for r in loaded] == ["3", "4", "new"]

    def test_within_cap_no_trim(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_records(path, [_record("a")])
        add_history_record(path, _record("b"), max_entries=10)
        loaded = load_history_records(path)
        assert [r.video_id for r in loaded] == ["a", "b"]

    def test_lazy_v1_to_latest_migration_via_add(self, tmp_path):
        path = tmp_path / "history.json"
        # Seed v1 file.
        path.write_text(json.dumps(["old1", "old2"]), encoding="utf-8")
        add_history_record(path, _record("new", platform="tiktok"))
        # Should now be the latest schema.
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == SCHEMA_VERSION == 3
        ids = [e["video_id"] for e in data["entries"]]
        assert ids == ["old1", "old2", "new"]
