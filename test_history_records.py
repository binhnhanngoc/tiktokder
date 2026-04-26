"""Tests for history_store.py — HistoryRecord schema v2 and v1 migration."""

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
        assert version == SCHEMA_VERSION
        assert len(records) == 2
        assert records[0].uploader == "@u"
        assert records[1].platform == "facebook"

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

    def test_save_writes_schema_v2(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_records(path, [_record("xyz")])
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == 2
        assert data["entries"][0]["video_id"] == "xyz"

    def test_save_history_ids_writes_v2(self, tmp_path):
        path = tmp_path / "history.json"
        save_history_ids(path, {"3", "1", "2"})
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == 2
        ids = sorted(e["video_id"] for e in data["entries"])
        assert ids == ["1", "2", "3"]


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

    def test_lazy_v1_to_v2_migration_via_add(self, tmp_path):
        path = tmp_path / "history.json"
        # Seed v1 file.
        path.write_text(json.dumps(["old1", "old2"]), encoding="utf-8")
        add_history_record(path, _record("new", platform="tiktok"))
        # Should now be v2.
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema"] == 2
        ids = [e["video_id"] for e in data["entries"]]
        assert ids == ["old1", "old2", "new"]
