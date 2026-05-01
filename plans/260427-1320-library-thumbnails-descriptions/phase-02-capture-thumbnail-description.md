# Phase 2 — Capture Thumbnail Path + Description

**Status:** pending · **Priority:** P1 · **Effort:** M (~1h) · **Risk:** Low

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Files: `download_engine.py:291-323` (`_build_record`), `downloader.py:253` (`writethumbnail` opt).
- Depends on: Phase 1 (schema v3).

## Goal

Force yt-dlp to always write a thumbnail sidecar. After each successful download, populate `HistoryRecord.description` from `info["description"]` and `HistoryRecord.thumbnail_path` by resolving the sidecar file beside the downloaded video.

## Key Insights

- `downloader.py:253` currently sets `writethumbnail` only when caller passes `write_thumb=True`. Since brainstorm decided "always-on", we hardcode it to `True` regardless of caller.
- yt-dlp returns final filenames in `info["requested_downloads"][0]["filepath"]`. The thumbnail sidecar lives next to that path with a different extension. yt-dlp may write `.jpg`, `.webp`, or rarely `.png`.
- yt-dlp also exposes `info["thumbnails"]` (list with chosen URL) but **not** the local sidecar path directly in a stable way. Glob is the cheapest reliable resolver.
- Description is short on TikTok (~caption), longer on Facebook. May be `None` or empty string — treat both as "no description".

## Requirements

- All downloads write a thumbnail sidecar.
- `_build_record` resolves the sidecar path post-download.
- `_build_record` extracts `info["description"]` (None-safe).
- Empty / whitespace-only descriptions stored as `None`, not `""`.
- Missing sidecar (rare race / extraction failure) stored as `None`, not raised.

## Architecture

```
DownloadWorker
   └─ downloader.download_video(...)        ← writethumbnail forced on
            ↓ yt-dlp writes video + sidecar.jpg|webp
   └─ _build_record(url, result, info)      ← reads info dict
            ├─ description    = info.get("description") (whitespace-stripped, None if empty)
            └─ thumbnail_path = _resolve_thumbnail_sidecar(file_path)
                    ↓ glob {basename}.{jpg,webp,png} returns first match or None
```

## Related Code Files

**Modify:**
- `download_engine.py` — `_build_record` extends to populate two new fields; add `_resolve_thumbnail_sidecar` helper (private module-level fn).
- `downloader.py` — force `writethumbnail = True` (drop the `if write_thumb:` guard or make it unconditional).

**Read for context:**
- `path_builder.py` — confirms no normalization that could move the sidecar.
- `history_store.py` (post Phase 1) — for `HistoryRecord` field names.

## Implementation Steps

1. **`downloader.py:253`** — change
   ```python
   if write_thumb:
       opts["writethumbnail"] = True
   ```
   to
   ```python
   opts["writethumbnail"] = True  # always-on; sidecar referenced by HistoryRecord.thumbnail_path
   ```
   The `write_thumb` parameter becomes unused but **keep the parameter for now** to avoid touching every caller. Add a comment that it's deprecated and ignored.

2. **`download_engine.py`** — add a helper near the top (after imports):
   ```python
   _THUMB_EXTS = (".jpg", ".jpeg", ".webp", ".png")

   def _resolve_thumbnail_sidecar(video_path: str | None) -> str | None:
       """Return absolute path to a sidecar thumbnail next to ``video_path``, else None.

       yt-dlp's ``writethumbnail`` lands beside the video as ``{basename}.{jpg|webp|png}``.
       We probe each extension; first match wins. No globbing — direct os.path.exists()
       to avoid the cost of os.listdir() on uploader folders that may hold thousands.
       """
       if not video_path:
           return None
       base, _ = os.path.splitext(video_path)
       for ext in _THUMB_EXTS:
           candidate = base + ext
           if os.path.exists(candidate):
               return candidate
       return None
   ```

3. **`download_engine.py:313`** — extend `_build_record` return:
   ```python
   description = info.get("description")
   if isinstance(description, str):
       description = description.strip() or None
   else:
       description = None
   thumbnail_path = _resolve_thumbnail_sidecar(file_path)
   return HistoryRecord(
       ...,
       downloaded_at=datetime.now(...).isoformat(timespec="seconds"),
       description=description,
       thumbnail_path=thumbnail_path,
   )
   ```

4. Confirm `os` is already imported in `download_engine.py` (it is).

5. Manual smoke test:
   - Delete `data/history.json` (back it up first).
   - Download one TikTok URL via the GUI.
   - Cat the resulting `history.json` → expect `description` and `thumbnail_path` populated.
   - Download one Facebook URL → same.

## Todo List

- [ ] Force `writethumbnail = True` in `downloader.py`.
- [ ] Add `_resolve_thumbnail_sidecar` helper in `download_engine.py`.
- [ ] Extend `_build_record` to populate description + thumbnail_path.
- [ ] Sanity-strip empty descriptions to `None`.
- [ ] Run app, download one TT + one FB video, inspect `history.json`.
- [ ] Existing tests still green.

## Success Criteria

- After downloading a TikTok video, the new `HistoryRecord` row has:
  - `description` = the caption text (or None if blank).
  - `thumbnail_path` = absolute path to a `.jpg` or `.webp` next to the video file, and that file exists.
- Same for a Facebook page video.
- A run with `writethumbnail` already on (no behavior regression) → still produces matching record.

## Risks

| Risk | Mitigation |
|---|---|
| Sidecar extension we missed (e.g. `.jpe`) | Probe order matches yt-dlp defaults; `_THUMB_EXTS` is easy to extend. Log debug if `None` returned for >0 attempts. |
| Race: thumbnail file not flushed before `_build_record` runs | yt-dlp finishes thumbnail write before returning info dict — verified by code path; if seen empirically, add a 100ms retry. |
| Description embedding non-text (TikTok hashtags + emojis) | All UTF-8; no special handling required. JSON dumps with `ensure_ascii=False` (already the case in `save_history_records`). |
| `write_thumb` param now dead code | Phase 6 will remove the call sites + setting; keep param as no-op for one phase to avoid touching call sites prematurely. |

## Security Considerations

None — local file resolution only; no path traversal possible since `video_path` originates from yt-dlp's own filename builder.

## Next Steps

→ Phase 3 (table thumbnail column) consumes `HistoryRecord.thumbnail_path` for rendering.
→ Phase 4 (preview pane) consumes both fields.
