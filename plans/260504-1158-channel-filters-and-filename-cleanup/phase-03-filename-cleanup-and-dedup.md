# Phase 3 — Filename refactor (drop ID prefix) + dual-path dedup

## Context Links

- Target: `path_builder.py::_FILENAME_TEMPLATE`, `downloader.py::get_downloaded_ids`, `downloader.py::get_ydl_opts` (line 218 hardcoded duplicate template)
- Dedup oracle: `history_store.py::HistoryRecord` (schema v4 has `video_id` + `file_path`)
- Tests: `test_path_builder.py`, `test_tiktokder.py::TestGetDownloadedIds`, `test_engine_history_integration.py`
- Docs: `README.md`, `docs/codebase-summary.md`, `docs/system-architecture.md`

## Overview

- **Priority:** P2 (high risk if dedup regresses)
- **Status:** pending
- **Description:** Change saved filename from `{id}_{title}.ext` → `{title}.ext` (with collision strategy below). Keep dedup recognizing both legacy and new layouts.

## Key Insights

- Two places hardcode the template: `path_builder.py:27` (`_FILENAME_TEMPLATE`) AND `downloader.py:218` (`get_ydl_opts` default). The default in `get_ydl_opts` is overwritten per-call by `_do_download` (line 335) but still active for any caller bypassing `_do_download`. **Both must change** — DRY.
- `get_downloaded_ids()` regex `^(\d{15,25})_` requires the ID prefix. Removing the prefix breaks dedup for new files. Fix: keep the regex for legacy files, ADD a history.json-based set, return the union.
- `HistoryRecord.video_id` is the safer dedup oracle — it's stamped at download success time and survives filesystem rename/move. Use it as the primary signal; filesystem walk becomes a legacy bootstrap.
- Title collisions are real (e.g. two TikToks both titled "Untitled" or default platform title). yt-dlp's `outtmpl` does NOT auto-uniquify; second download silently overwrites the first **unless** `nooverwrites=True`. Current engine sometimes sets `overwrites=True` for retries (`force_overwrite=True`) — collision behavior depends on caller flag.
- `test_engine_history_integration.py:37` references `/tmp/1234567890123456789_hello.mp4` — needs to update to new shape.

## Title-collision strategy — recommended approach

Plan recommends **option (b-modified): `%(title).80s [%(id).6s].%(ext)s`** — a short 6-char ID suffix in brackets. Rationale: silent overwrites are data loss; users searching/sorting by title still see the title up front; bracketed short ID is visually unobtrusive and shell-glob-friendly.

User said "no ID in name". If strictly enforced, fallback is **option (e-modified): `%(title).80s.%(ext)s` + `nooverwrites=True`** — second-write skips silently, preserving the first download. Lose: identically-titled distinct videos can't both be saved (only the first survives). Document this tradeoff in README.

**Decision required before implementation.** Plan implements (b-modified) by default; reviewer toggles to (e-modified) by changing the template constant + adding `nooverwrites=True` to `get_ydl_opts`.

## Requirements

### Functional
- New downloads land at `<base>/<platform>/<uploader>/<title>[ <id6>].<ext>` (or `<title>.<ext>` if (e) chosen).
- `get_downloaded_ids(output_dir)` returns the union of:
  - IDs found via legacy regex `^(\d{15,25})_` on filenames in the tree.
  - IDs read from `HistoryRecord.video_id` for records whose `file_path` exists on disk under `output_dir`.
- No file on disk is renamed by this change. Old files keep their old names; new files use the new shape.
- `force_overwrite=True` retry path still overwrites the SAME file (yt-dlp invariant — same outtmpl + same id → same path).

### Non-functional
- Dedup query must remain O(N_files + N_history) — no per-file network or expensive ops.
- README + `docs/codebase-summary.md` + `docs/system-architecture.md` updated to match.

## Architecture

```
path_builder._FILENAME_TEMPLATE = "%(title).80s [%(id).6s].%(ext)s"
                                  # OR "%(title).80s.%(ext)s" if option (e)

downloader.get_ydl_opts(...)   # remove hardcoded outtmpl entirely
                               # _do_download builds it per-call already
                               # (line 335) — defensive: drop the duplicate

downloader.get_downloaded_ids(output_dir):
    ids = set()
    # 1. Legacy filesystem walk
    for root, _, files in os.walk(output_dir):
        for fn in files:
            if m := LEGACY_ID_RE.match(fn):
                ids.add(m.group(1))
    # 2. History oracle — pulls in new-shape files
    for rec in load_history_records():
        if rec.video_id and rec.file_path and _path_under(rec.file_path, output_dir):
            if os.path.exists(rec.file_path):
                ids.add(rec.video_id)
    return ids
```

`_path_under` uses `os.path.commonpath` after `os.path.realpath` on both — handles symlinks safely; rejects on platform mismatch (different drive on Windows raises `ValueError`).

## Related Code Files

**Modify:**
- `path_builder.py` — change `_FILENAME_TEMPLATE`. Update docstring (`build_output_template`, module header).
- `downloader.py`:
  - Remove hardcoded `outtmpl` from `get_ydl_opts` defaults (use `path_builder._FILENAME_TEMPLATE` or just drop, since `_do_download` overwrites it). Defensive: import the constant for any standalone caller.
  - Rewrite `get_downloaded_ids` per architecture above.
  - Add `LEGACY_ID_RE` module constant.
- `README.md` — update filename layout docs.
- `docs/codebase-summary.md` — update `path_builder` and `get_downloaded_ids` descriptions.
- `docs/system-architecture.md` — update both references.

**Read (no edits):**
- `history_store.py::load_history_records` — already returns `list[HistoryRecord]`.
- `download_engine.py::_resolve_thumbnail_sidecar` — confirms thumbnail naming follows the video basename, so changing the video template auto-changes thumbnail names. No code change needed there.

**Create:** none.

## Implementation Steps

1. Edit `path_builder.py`:
   - Change `_FILENAME_TEMPLATE` to chosen template.
   - Update docstrings (module header, `build_output_template`).
2. Edit `downloader.py`:
   - Add `from path_builder import _FILENAME_TEMPLATE` (or inline the same string + comment "must match path_builder").
   - In `get_ydl_opts`, change `"outtmpl": os.path.join(output_dir, _FILENAME_TEMPLATE)` (so any standalone caller still gets a sane default — but the constant is now in one place).
   - Add `LEGACY_ID_RE = re.compile(r"^(\d{15,25})_")` near the top.
   - Rewrite `get_downloaded_ids(output_dir)`:
     - Walk filesystem for legacy IDs (existing code).
     - Read `load_history_records()` and union in `video_id`s whose `file_path` is under `output_dir` AND exists on disk.
     - Add helper `_path_under(child, parent) -> bool` using `os.path.realpath` + `commonpath`, returns False on `ValueError`.
   - If option (e) chosen: add `opts["nooverwrites"] = True` in `get_ydl_opts` (skip after `force_overwrite` check so retry path still overrides).
3. Update tests (covered in Phase 4).
4. Update docs:
   - `README.md`: any reference to `{video_id}_{title}.ext` → new shape; explain dedup uses history.json + legacy regex.
   - `docs/codebase-summary.md::path_builder` and `get_downloaded_ids` lines.
   - `docs/system-architecture.md` lines 179 and 421 (per Grep).

## Todo List

- [ ] Decide title-collision strategy ((b-modified) bracketed short id vs (e-modified) title-only + nooverwrites).
- [ ] Update `path_builder._FILENAME_TEMPLATE` + docstrings.
- [ ] Update `downloader.get_ydl_opts` outtmpl reference (use shared constant).
- [ ] Add `LEGACY_ID_RE` constant.
- [ ] Rewrite `get_downloaded_ids` with history+filesystem union.
- [ ] Add `_path_under` helper.
- [ ] If option (e): set `nooverwrites=True` (respecting `force_overwrite`).
- [ ] Update README filename layout section.
- [ ] Update `docs/codebase-summary.md`.
- [ ] Update `docs/system-architecture.md`.

## Success Criteria

- New downloads produce `<title>[<short_id>].<ext>` (or `<title>.<ext>`) under the platform/uploader folder.
- Re-running on a folder mixing legacy `123_x.mp4` and new `mytitle [abc123].mp4` files produces a `set` containing IDs of BOTH.
- A file deleted from disk after history was written is NOT in the dedup set (the `os.path.exists` check filters it out — user explicitly removed it).
- Force-redownload (`force_overwrite=True`) still overwrites in place.
- README + docs match new layout.

## Risks

- **Probability High / Impact High — Title collision data loss** (option e). Mitigation: docstring + README warning, or pick option (b-modified).
- **Probability Med / Impact Med — Stale history points to nonexistent file**. Mitigation: `os.path.exists` check before adding to dedup set.
- **Probability Low / Impact High — Path-traversal in `file_path`**. Mitigation: `_path_under` uses `realpath` + `commonpath`.
- **Probability Low / Impact Low — `output_dir` arg to `get_downloaded_ids` does NOT match the per-platform subfolder structure**. Confirmed: callers (`main.py`, engine) pass the base `downloads/` dir; `_path_under` works because the platform/uploader folders are children.
- **Probability Med / Impact Med — Chars in title that yt-dlp's `outtmpl` doesn't sanitize**. yt-dlp already sanitizes for filesystem (it has its own restrict logic via `--restrict-filenames`-style defaults). No extra step needed; verify with a manual download containing emoji/CJK.
- **Probability Low / Impact High — Large title overflow on Windows MAX_PATH**. yt-dlp truncates `%(title).80s` to 80 chars; combined path stays well under 260 in typical layouts. Mitigation: 80 is conservative; reduce to 60 if reports come in.

## Security Considerations

- `_path_under` must reject paths outside `output_dir` to prevent a poisoned `history.json` from causing `os.path.exists` probes on arbitrary paths. Using `realpath` defeats `..` traversal; `commonpath` on Windows raises on cross-drive comparison (caught and treated as "not under").

## Next Steps

- Phase 4 (tests) verifies dedup union and template change.
- After merge, watch for user reports of title collisions; if frequent, switch from (e) to (b) (or reduce title length cap).
