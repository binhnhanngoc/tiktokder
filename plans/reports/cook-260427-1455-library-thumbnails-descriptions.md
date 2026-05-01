# Cook Report — Library Thumbnails + Descriptions

**Plan:** `plans/260427-1320-library-thumbnails-descriptions/`
**Mode:** code (executing existing plan, --auto-style)
**Status:** DONE
**Tests:** 387 passed (was 379 pre-change; +8 new tests, 0 failures)

## Phases

| # | Phase | Files Changed |
|---|-------|----------------|
| 1 | Schema v3 | `history_store.py` |
| 2 | Capture thumb + description | `download_engine.py`, `downloader.py` |
| 3 | Table thumbnail column | `gui/library_panel.py`, **new** `gui/library_thumbnail_delegate.py` |
| 4 | Preview pane (3-way splitter) | `gui/library_panel.py`, **new** `gui/library_preview_pane.py` |
| 5 | Description search | `gui/library_panel.py` (1-line haystack + placeholder) |
| 6 | Settings cleanup + README | `gui/settings_panel.py`, `README.md` |
| 7 | Tests | `test_history_records.py`, `test_download_engine.py`, `test_library_panel.py`, `test_config.py`, `test_tiktokder.py` |

## Key Decisions

- `_read_history_file` now returns the **on-disk** schema version (2 or 3) instead of always `SCHEMA_VERSION`. v2 files are promoted to v3 at write time only.
- `write_thumb` parameter on `downloader.get_ydl_opts` kept for call-site compat; `writethumbnail=True` is forced regardless. `AppConfig.write_thumbnail` field also kept (one phase of grace, per plan).
- Delegate split into its own module (`library_thumbnail_delegate.py`) and preview pane into another (`library_preview_pane.py`) — keeps `library_panel.py` under 250 LOC.
- `QPixmapCache` budget bumped to 20 MB at module import time. Large preview pixmaps cached under `large:{path}` so they don't collide with the small table thumbs.

## Test Updates Beyond New Coverage

- `test_history_records.py` — assertions about `data["schema"] == 2` updated to `SCHEMA_VERSION == 3`; new v2→v3 round-trip + v3 read tests added.
- `test_library_panel.py` — hardcoded column indices (`0`, `2`) replaced with `_COL_TITLE` / `_COL_SIZE` imports because columns reshuffled by 1 after Phase 3.
- `test_tiktokder.py` — flipped "thumb default off" → "thumb always on" to match the always-on behavior.
- `test_config.py` — `data["schema"] == 2` → `SCHEMA_VERSION` import.
- `test_settings_split.py` — passed unchanged after `thumb_check.stateChanged` wiring removal in `gui/settings_panel.py:70`.

## Smoke Verification

- `python -c "import history_store; print(history_store.SCHEMA_VERSION)"` → `3`
- `python -c "from download_engine import _resolve_thumbnail_sidecar; ..."` → returns `None` for missing/None inputs without raising.
- All Library + settings + history modules import cleanly.

## Out of Scope (per plan)

- Backfill of pre-v3 rows (no automatic re-fetch of thumbnails for old history).
- Right-click "Refresh metadata" action.
- Removing `AppConfig.write_thumbnail` from the dataclass (deferred to a future cleanup pass).

## Follow-ups Worth Tracking

- **`AppConfig.write_thumbnail` is now dead code.** Drop it in a future config-cleanup phase along with the unused `write_thumb` keyword on `downloader.get_ydl_opts` and its call sites.
- `pytest.mark.slow` marker emits an `PytestUnknownMarkWarning` — register the mark in `pytest.ini` / `pyproject.toml` if the warning bothers CI (cosmetic only).
- Real-world thumbnail rendering (webp + jpg) could not be exercised in this run — no GUI launch was performed. Visual smoke test is recommended next time the user starts the app.

## Unresolved Questions

None.
