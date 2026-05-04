# Phase 4 — Tests + docs sync

## Context Links

- Targets: `test_path_builder.py`, `test_tiktokder.py::TestGetDownloadedIds`, `test_engine_history_integration.py`, `test_channel_fetcher.py`, `test_library_panel.py` (reference patterns)
- Docs: `README.md`, `docs/codebase-summary.md`, `docs/system-architecture.md`, `docs/project-changelog.md` (if present)

## Overview

- **Priority:** P2
- **Status:** pending
- **Description:** Update existing tests to match new template and dedup logic; add new tests for filter row, date conversion, and dual-source dedup. Sync docs.

## Key Insights

- `test_path_builder.py` asserts the literal string `"%(id)s_%(title).50s.%(ext)s"` in many places — every assertion needs a coordinated update OR replaced by a more resilient invariant ("filename portion ends with `.%(ext)s` and contains `%(title)`").
- `test_tiktokder.py::TestGetDownloadedIds` currently tests legacy regex only. Must add: (1) new-shape file detected via history oracle, (2) legacy + new union, (3) history with missing file_path is ignored, (4) history with file outside output_dir is ignored.
- `test_engine_history_integration.py:37` hardcodes a `/tmp/123..._hello.mp4` path — only used as the filepath returned in `requested_downloads`; updating to new shape is a one-line fix.
- Filter-row tests for `BaseBrowserPanel` should follow `test_library_panel.py` patterns: instantiate with `pytest-qt`'s `qtbot`, push a few `VideoInfo` rows via `_on_video_found`, set search text + tick filters, assert `table.isRowHidden(row)`.
- Date helper (`_upload_date_from_entry`) is pure → trivial unit test in `test_channel_fetcher.py`.

## Requirements

### Functional
- All existing tests pass against new code.
- New tests cover: filter predicate, date conversion, dual-source dedup.
- README + docs reflect new filename layout and dedup behavior.

### Non-functional
- No flaky timer-based tests — use `qtbot.waitUntil` or directly invoke `_apply_filters` to bypass the 200ms debounce.

## Architecture

```
test_path_builder.py        # update template assertions
test_tiktokder.py           # extend TestGetDownloadedIds
test_engine_history_integration.py  # update file_path string
test_channel_fetcher.py     # add date helper test
test_base_browser_panel.py  # NEW — filter row behavior
```

## Related Code Files

**Modify:**
- `test_path_builder.py` — update template string assertions; loosen to "ends with `.%(ext)s` and folder portion is correct" where exact match isn't load-bearing.
- `test_tiktokder.py` — update `TestGetDownloadedIds` for union behavior.
- `test_engine_history_integration.py` — update hardcoded filepath.
- `test_channel_fetcher.py` — add `TestUploadDateFromEntry`.
- `README.md`, `docs/codebase-summary.md`, `docs/system-architecture.md` — see Phase 3 list.

**Create:**
- `test_base_browser_panel.py` — new file. Tests filter row + sort + select-visible-only.

**Read (no edits):**
- `test_library_panel.py` — pytest-qt + filter pattern reference.

## Implementation Steps

1. `test_path_builder.py` — replace exact-string assertions with shape checks where possible:
   - Keep folder-portion assertions (`/tiktok/@user/`).
   - For filename portion, assert `tmpl.endswith(_FILENAME_TEMPLATE)` (importing the constant) — survives future template tweaks.
2. `test_tiktokder.py::TestGetDownloadedIds` — add cases:
   - `test_get_downloaded_ids_finds_new_template_via_history`: write a file `<tmpdir>/tiktok/@user/My Title [abc123].mp4`; build a history.json with one record pointing at that path; assert ID present.
   - `test_get_downloaded_ids_unions_legacy_and_history`: mix legacy `123_x.mp4` and a new-template file recorded in history; assert both IDs returned.
   - `test_get_downloaded_ids_history_skips_missing_file`: history record points at a nonexistent path; assert ID NOT in result.
   - `test_get_downloaded_ids_history_rejects_outside_output_dir`: history record `file_path` outside `output_dir`; assert ID NOT in result.
   - Use `monkeypatch` to point `load_history_records` at a temp file with the constructed records.
3. `test_engine_history_integration.py` — update line ~37 from `/tmp/123..._hello.mp4` to match new template (e.g. `/tmp/hello [abc123].mp4` for option b, or `/tmp/hello.mp4` for option e).
4. `test_channel_fetcher.py` — new `TestUploadDateFromEntry` class:
   - `test_returns_yyyymmdd_for_valid_epoch`: assert `_upload_date_from_entry({"timestamp": 1714867200}) == "20240505"` (or whatever UTC date that epoch maps to — use `datetime.fromtimestamp(..., tz=utc).strftime` to compute expected dynamically).
   - `test_returns_none_for_missing`, `_for_zero`, `_for_negative`, `_for_string`.
   - `test_returns_none_on_overflow` (e.g. `1e30`).
5. `test_base_browser_panel.py` (new):
   - Build via `qtbot.addWidget(panel)` where `panel` is a thin subclass providing a no-op fetcher (or instantiate `BaseBrowserPanel` directly with `_create_fetcher` patched).
   - Push 3 `VideoInfo`s via `panel._on_video_found(...)`.
   - Set search text → call `panel._apply_filters()` directly → assert `panel.table.isRowHidden(row)` for non-matching rows.
   - Toggle quality combo → assert hide.
   - Toggle from/to date → assert hide.
   - Verify `select_all` only checks visible; `_on_download` only emits visible URLs.
   - Verify `len(panel._videos) == 3` after every test (no mutation).
6. Run full suite: `pytest -q`. Fix any incidental failures (e.g. snapshot tests that capture the old template string).
7. Sync docs (Phase 3 already lists them).

## Todo List

- [ ] Update `test_path_builder.py` to import `_FILENAME_TEMPLATE` and assert shape, not literal string.
- [ ] Add 4 dedup-union tests in `test_tiktokder.py`.
- [ ] Update `test_engine_history_integration.py` filepath.
- [ ] Add `TestUploadDateFromEntry` in `test_channel_fetcher.py`.
- [ ] Create `test_base_browser_panel.py` with filter + sort + select-visible tests.
- [ ] Run `pytest -q`; fix incidental failures.
- [ ] Update README, `docs/codebase-summary.md`, `docs/system-architecture.md`.

## Success Criteria

- `pytest -q` green.
- Coverage on `path_builder.py`, `channel_fetcher.py`, `downloader.py::get_downloaded_ids`, `gui/base_browser_panel.py` does not regress.
- README reads consistently — no orphan reference to `{video_id}_{title}.ext`.

## Risks

- **GUI tests flaky on CI without display server**: PySide6 + offscreen needs `QT_QPA_PLATFORM=offscreen`. Existing `test_library_panel.py` already runs in CI — match its setup.
- **Hardcoded filename strings in other tests** beyond the listed ones — Grep before merge: `rg "[0-9]{15,}_"` and `rg "_FILENAME_TEMPLATE"` to catch stragglers.

## Security Considerations
None.

## Next Steps

- Merge requires: all phases complete, all tests green, docs sync'd, title-collision strategy decision recorded in commit message.
- Post-merge: smoke download a TikTok + Facebook video, confirm filenames + dedup on a second run.
