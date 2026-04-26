---
type: brainstorm
date: 2026-04-26
slug: app-enhancements
status: approved-design
---

# TikTokDer App Enhancements — Design Summary

## Problem

User-requested feature batch:
1. Separate TikTok/Facebook in Channel/Page tab.
2. User-facing **History** view (current `history.json` is internal dedup `set[str]` only).
3. **Video quality** column in browse table.
4. Per-profile **folder organization** for downloads.
5. Plus "more professional" extras.

## Approved Decisions

| # | Area | Decision |
|---|------|----------|
| 1 | Channel UX | Inner sub-tabs `TikTok` / `Facebook` inside existing Channel/Page tab |
| 2 | History UI | New 4th top-level **History** tab, rich columns, search + platform filter, right-click menu |
| 3 | Quality column | **Cheap-only** — populated from yt-dlp flat-listing metadata; rows without data show `—` |
| 4 | Quality selector | **Adopt** — Settings default + per-batch override `Best / 1080p / 720p / 480p / Audio-only` |
| 5 | Folder layout | `downloads/{platform}/{uploader}/{id}_{title}.mp4` |
| 6 | Migration | **Leave-as-is** — dedup scans BOTH flat root and tree |
| 7 | Polish | Right-click on history rows, subs+thumb toggles, drag-and-drop URLs, stats in History, import/export URL list |

Top tabs after enhancements: `Download | Channel/Page | History | Settings`.

## Architecture Sketch

### History persistence (breaking schema change, internal)

`data/history.json` — upgrade `list[str]` → `list[record]`:

```json
{
  "schema": 2,
  "entries": [
    {
      "video_id": "7234567890",
      "platform": "tiktok",
      "uploader": "@user1",
      "title": "...",
      "url": "https://www.tiktok.com/@user1/video/7234567890",
      "quality": "1080p",
      "file_path": "downloads/tiktok/@user1/7234567890_clip.mp4",
      "size_bytes": 12582912,
      "downloaded_at": "2026-04-26T14:30:00+07:00"
    }
  ]
}
```

- `load_history()` returns `set[str]` for back-compat dedup callers; add `load_history_records()` for the History tab.
- One-time auto-migration on first load: schema 1 (`list[str]`) → schema 2 (records with `video_id` only, other fields `null`). No data loss; new fields fill in as new downloads happen.

### Download path generation

- New helper `build_output_path(url, info, base_dir) -> str` — slugifies `uploader`, picks `tiktok` or `facebook` from `detect_platform`, falls back to `unknown_uploader/` if metadata missing.
- yt-dlp `outtmpl` switched to template form: `{base}/{platform}/{uploader_slug}/%(id)s_%(title).50s.%(ext)s`. Use `%(uploader)s` directly when safe; fall back to per-call template injection for FB pages where `uploader` is absent (use page slug from URL).

### Dedup scan upgrade

`get_downloaded_ids(output_dir)` — switch from `os.listdir` (flat) to `os.walk` (recursive). Same regex match. Idempotent across both old and new layouts. ~5-line change.

### Quality selector → yt-dlp `format`

| Selection | yt-dlp `format` |
|-----------|------------------|
| Best | `b` (current) |
| 1080p | `bv*[height<=1080]+ba/b[height<=1080]` |
| 720p | `bv*[height<=720]+ba/b[height<=720]` |
| 480p | `bv*[height<=480]+ba/b[height<=480]` |
| Audio-only | `ba/b` + postprocess to m4a |

Note: stream-merging formats (`bv+ba`) require ffmpeg. Existing `_warn_ffmpeg_missing()` already handles the warn-once case; document in tooltip.

### Polish features — wiring

- **Right-click history rows:** Qt `customContextMenuRequested` → QMenu with `Open file` / `Open containing folder` / `Re-download` / `Copy URL` / `Remove from history`. `os.startfile` (Windows), `subprocess.Popen(["open"|"xdg-open", ...])` cross-platform.
- **Subs + thumbs:** two checkboxes in Settings → `writesubtitles`, `writeautomaticsub`, `writethumbnail`, `subtitleslangs=["en"]` flags into `get_ydl_opts()`.
- **Drag-and-drop:** override `dragEnterEvent` / `dropEvent` on `DownloadTab` widget. Accept `text/uri-list` and `text/plain`. If dropped item is `.txt`, read via existing `read_batch_file()`. URLs go straight to `engine.add_urls()`.
- **Stats summary:** computed in-memory from history records on tab show. Labels at top of History tab: total count, total size, per-platform count, top-5 uploaders. Refresh on history change signal.
- **Import/Export URL list:** two buttons in Download tab. Export = current queue + recent history URLs to `.txt` (one per line, with `# platform: uploader` comments). Import = QFileDialog → `read_batch_file()` → engine.

## File-Level Impact Map

| File | Change |
|------|--------|
| `config.py` | `AppConfig`: add `quality_default`, `write_subtitles`, `write_thumbnail`. History schema v2 + migrator. New `load_history_records()`. |
| `downloader.py` | `get_ydl_opts()`: accept `quality`, `write_subs`, `write_thumb`. `outtmpl` template builder. `get_downloaded_ids()`: recursive walk. Persist `DownloadResult` enriched with uploader/quality/size/path. |
| `download_engine.py` | Pass quality/subs/thumb through. After successful download, append history record (not just ID). |
| `gui/channel_browser.py` | Split into `TikTokBrowserPanel` + `FacebookBrowserPanel`; parent `ChannelBrowser` wraps a `QTabWidget`. Add `Quality` column. Each panel persists its last URL. |
| `gui/history_tab.py` *(new)* | Table widget, search line, platform combo, stats labels, right-click menu, signal `history_action_requested`. |
| `gui/main_window.py` | Add History tab, drag-and-drop on download tab, import/export buttons, wire quality selector to engine. |
| `gui/settings_panel.py` | Quality default combo, subs checkbox, thumbnail checkbox. |
| `tests/` | New `test_history_records.py`, `test_path_builder.py`, expand `test_downloader.py` for recursive dedup + format strings. |

Estimated new code: ~600–800 LOC; touched code: ~300 LOC. Most files stay <200 LOC limit; `gui/channel_browser.py` will need to split (currently ~180 LOC, would exceed).

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `%(uploader)s` empty for some FB pages | Path builder falls back to URL slug; never produces empty segment. |
| Recursive `os.walk` on huge `downloads/` slow | Cache result in `DownloadEngine`; only rescan on first run + after each completed download. |
| `format` selector breaks on platforms without 1080p | yt-dlp `format` syntax already includes graceful fallback (`/b`); user sees "best available". |
| History schema v1→v2 migration race | Atomic write (write-temp + rename); reject malformed v1 by falling back to empty. |
| Existing flat downloads invisible after layout switch | Recursive dedup covers it; History tab won't show pre-feature files (acceptable — no metadata to back-fill). |
| Slugified uploader collides across platforms | Platform-first layout already prevents it (`tiktok/foo` ≠ `facebook/foo`). |

## Success Metrics

- Channel/Page tab visibly separates platforms; switching tabs preserves each panel's state.
- Download a TikTok video → file at `downloads/tiktok/@user/{id}_*.mp4`; History tab shows it within 1s of completion.
- Dedup correctly skips a previously-downloaded video whether the file is in flat root or `tiktok/<user>/`.
- All 104 existing tests pass; ~20 new tests cover new modules.
- No regression in single-URL or batch-CLI flows.

## Out of Scope (deferred)

- Migrating old flat files into new tree (user picked leave-as-is).
- Auto-probe for quality column (rate-limit risk).
- Pause/resume per download, bandwidth limit, dark mode, scheduling, REST API.

## Open Questions

1. **History retention cap?** Unbounded list will grow forever. Suggest soft cap (e.g., 5,000 entries) with "older entries pruned, files untouched" — confirm or pick a number.
2. **Audio-only output extension?** `.m4a` (default) or `.mp3` (requires ffmpeg postprocessor)?
3. **Subtitle languages for the toggle** — English-only, or auto-detect/all?
4. **Import format** — accept the existing batch-file format only (URLs + `#` comments), or also support a `.csv` export round-trip?
