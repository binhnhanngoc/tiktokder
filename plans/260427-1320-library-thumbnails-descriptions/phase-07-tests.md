# Phase 7 — Tests: Migration, Capture, Search, Perf Smoke

**Status:** pending · **Priority:** P1 · **Effort:** M (~1.5h) · **Risk:** Low

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Test directory: `tests/`. Existing pytest layout already covers history, downloader, URL parser.
- Depends on: Phases 1–5 (6 is doc/UI only).

## Goal

Lock in the new behavior with focused unit + smoke tests:
1. **Schema migration** — v2 file loads, gets the new fields populated as `None`, re-saves as v3.
2. **Capture** — `_resolve_thumbnail_sidecar` finds the right extension and returns `None` when missing.
3. **Search** — description text matches via the search box predicate.
4. **Perf smoke** — synthetic 10k-row history loads and renders without crashing.

## Key Insights

- All test files use Python's `tmp_path` fixture for filesystem isolation.
- GUI tests should use `pytest-qt`'s `qtbot` fixture (already a dev dep — confirm in `requirements.txt`). If unavailable, fall back to non-GUI assertion of the predicate function.
- Perf smoke does **not** need to assert FPS; just constructs the panel with 10k records and exits cleanly without exception.

## Requirements

- All new tests pass.
- All existing tests still pass.
- Coverage for `_resolve_thumbnail_sidecar`, schema v2 → v3 round-trip, and the search-includes-description predicate.

## Architecture

```
tests/
├── test_history_store.py             ← extend: v2 → v3 round-trip
├── test_download_engine.py           ← extend (or new): _resolve_thumbnail_sidecar
├── test_library_panel.py             ← new (or extend): search includes description
└── test_library_panel_perf_smoke.py  ← new: 10k-row render smoke
```

## Related Code Files

**Modify or create:**
- `tests/test_history_store.py`
- `tests/test_download_engine.py`
- `tests/test_library_panel.py` (may already exist; extend)
- `tests/test_library_panel_perf_smoke.py` (new — kebab-case Python module name)

## Implementation Steps

### 1. Schema migration round-trip

```python
# tests/test_history_store.py — append:
def test_v2_file_loads_and_round_trips_to_v3(tmp_path):
    p = tmp_path / "history.json"
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
    p.write_text(json.dumps(v2_payload), encoding="utf-8")

    records = load_history_records(p)
    assert len(records) == 1
    r = records[0]
    assert r.video_id == "123"
    assert r.description is None
    assert r.thumbnail_path is None

    save_history_records(p, records)
    reread = json.loads(p.read_text(encoding="utf-8"))
    assert reread["schema"] == 3
    entry = reread["entries"][0]
    assert "description" in entry and entry["description"] is None
    assert "thumbnail_path" in entry and entry["thumbnail_path"] is None


def test_v3_file_loads(tmp_path):
    p = tmp_path / "history.json"
    p.write_text(json.dumps({
        "schema": 3,
        "entries": [{
            "video_id": "x",
            "description": "hello world",
            "thumbnail_path": "/tmp/x.jpg",
        }],
    }), encoding="utf-8")
    [r] = load_history_records(p)
    assert r.description == "hello world"
    assert r.thumbnail_path == "/tmp/x.jpg"
```

### 2. `_resolve_thumbnail_sidecar`

```python
# tests/test_download_engine.py — new test (import _resolve_thumbnail_sidecar):
def test_resolve_thumbnail_sidecar_finds_jpg(tmp_path):
    video = tmp_path / "abc_title.mp4"
    video.write_bytes(b"\x00")
    thumb = tmp_path / "abc_title.jpg"
    thumb.write_bytes(b"\xFF\xD8\xFF")  # JPEG magic — content irrelevant
    assert _resolve_thumbnail_sidecar(str(video)) == str(thumb)


def test_resolve_thumbnail_sidecar_finds_webp(tmp_path):
    video = tmp_path / "abc.mp4"
    video.write_bytes(b"\x00")
    (tmp_path / "abc.webp").write_bytes(b"RIFF")
    assert _resolve_thumbnail_sidecar(str(video)).endswith(".webp")


def test_resolve_thumbnail_sidecar_missing_returns_none(tmp_path):
    assert _resolve_thumbnail_sidecar(str(tmp_path / "nope.mp4")) is None


def test_resolve_thumbnail_sidecar_none_input():
    assert _resolve_thumbnail_sidecar(None) is None
```

### 3. Search includes description

If a unit test of the predicate is hard (it's inline in `_apply_filters`), refactor minimally to extract the haystack build into a private function `_search_haystack(rec)` and unit-test that. Otherwise use `qtbot`:

```python
# tests/test_library_panel.py — qtbot variant:
def test_search_matches_description(qtbot, tmp_path, monkeypatch):
    # Inject 2 records, one with a unique description token.
    records = [
        HistoryRecord(video_id="1", platform="tiktok", title="x", description="winter sunset"),
        HistoryRecord(video_id="2", platform="tiktok", title="y", description="cooking pasta"),
    ]
    monkeypatch.setattr("gui.library_panel.load_history_records", lambda: records)

    panel = LibraryPanel("tiktok", saved_store=DummySavedStore())
    qtbot.addWidget(panel)
    panel.refresh()

    panel.search_input.setText("sunset")
    qtbot.wait(300)   # past the 200 ms debounce
    assert panel.table.rowCount() == 1
```

### 4. Perf smoke — 10k rows

```python
# tests/test_library_panel_perf_smoke.py — new file:
def test_library_renders_10k_rows_without_crash(qtbot, monkeypatch):
    records = [
        HistoryRecord(
            video_id=str(i),
            platform="tiktok",
            uploader=f"@u{i % 50}",
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
    panel = LibraryPanel("tiktok", saved_store=DummySavedStore())
    qtbot.addWidget(panel)
    panel.refresh()
    assert panel.table.rowCount() == 10_000
```

(Tests like this can run for a few seconds; mark `@pytest.mark.slow` and gate behind `-m slow` if CI minutes matter.)

## Todo List

- [ ] Add v2 → v3 round-trip test in `test_history_store.py`.
- [ ] Add v3 load test.
- [ ] Add 4 tests for `_resolve_thumbnail_sidecar`.
- [ ] Add description-search test (unit or qtbot).
- [ ] Add 10k-row perf smoke test.
- [ ] Mark perf test `@pytest.mark.slow` if needed.
- [ ] `pytest -v` — all green.

## Success Criteria

- New tests cover the migration, sidecar resolver, search behavior, and perf smoke.
- Existing test suite still passes.
- Total runtime impact < 5s in regular runs (10k-row test gated behind a marker if slower).

## Risks

| Risk | Mitigation |
|---|---|
| pytest-qt not in `requirements.txt` for tests | Add to `requirements.txt` dev deps if missing; or fall back to predicate-only tests. |
| Headless CI lacks Qt platform plugin | Set `QT_QPA_PLATFORM=offscreen` in pytest conftest or env. |
| 10k-row test flaky on slow runners | Mark slow; allow up to 30s timeout. |

## Security Considerations

Tests use `tmp_path` only — no real network, no real downloads.

## Next Steps

After Phase 7, the feature is shippable. Optional follow-ups (out of scope):
- Right-click "Refresh metadata" to backfill old rows.
- Drop `AppConfig.write_thumbnails` from the dataclass once nothing reads it.
- Tauri-migration plan must re-implement Library UI in SvelteKit when it resumes.
