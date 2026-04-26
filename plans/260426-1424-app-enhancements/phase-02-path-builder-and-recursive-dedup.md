---
title: "Phase 02 — Path builder + recursive dedup"
priority: P0
effort: 45m
status: planned
depends: []
---

# Phase 02 — Path Builder + Recursive Dedup

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ Download path generation, § Dedup scan upgrade)
- Affected files: `downloader.py` (403 LOC), new `path_builder.py`
- Existing tests: `test_tiktokder.py`

## Overview
Switch download layout from flat `downloads/{id}_{title}.mp4` to `downloads/{platform}/{slug_uploader}/{id}_{title}.{ext}`. Provide a pure helper for path computation. Make dedup scan recursive so old flat files remain skippable.

## Key Insights
- yt-dlp `outtmpl` supports template fields (`%(uploader)s`, `%(id)s`, `%(title).50s`, `%(ext)s`) — **but** `uploader` is sometimes empty for FB pages. Solution: pre-resolve metadata via `extract_info(download=False)` and compute the full path in Python, then pass to yt-dlp as a fully-formed `outtmpl` per call. Falls back to URL-derived slug when metadata missing.
- Recursive dedup: replace `os.listdir` with `os.walk` in `get_downloaded_ids`. ~5-line change.
- Slugify must strip path-unsafe chars and emoji while preserving readable Unicode (NFKC normalize, then keep `[\w.-]`, replace others with `_`, collapse runs).

## Requirements

### Functional
- `path_builder.build_output_template(url, info, base_dir) -> str` returns the yt-dlp `outtmpl` string with platform/uploader segments already substituted, leaving `%(id)s_%(title).50s.%(ext)s` for yt-dlp to fill.
- `path_builder.slugify_uploader(name: str) -> str` returns a filesystem-safe slug; empty input → `"unknown_uploader"`.
- `path_builder.platform_slug_from_url(url: str) -> str` extracts a fallback slug from URL when metadata absent (e.g. `facebook.com/PageName` → `PageName`; `tiktok.com/@user/...` → `@user`).
- `downloader.get_downloaded_ids(output_dir)` walks recursively, returns same `set[str]`.

### Non-Functional
- `path_builder.py` ≤ 120 LOC.
- All path joins use `os.path.join`; never raw string concatenation.
- Pure functions — no I/O, no side effects, no logging beyond debug.

## Architecture

### Path Layout
```
downloads/
├── tiktok/
│   ├── @user1/
│   │   └── 7234567890_clip-title.mp4
│   └── unknown_uploader/
│       └── 7234567899_orphan.mp4
└── facebook/
    └── pagename/
        └── 12345678_video.mp4
```

### Slugify Algorithm
1. NFKC normalize.
2. Replace path separators (`/`, `\`) and reserved chars (`<>:"|?*`) with `_`.
3. Replace whitespace runs with single `_`.
4. Strip leading/trailing dots and underscores.
5. Truncate to 80 chars (filesystem-safe).
6. Empty result → `"unknown_uploader"`.

### Template Construction
```python
# pseudocode
def build_output_template(url, info, base_dir):
    platform = detect_platform(url) or "unknown"
    uploader = info.get("uploader") or info.get("channel") or info.get("uploader_id")
    if not uploader:
        uploader = platform_slug_from_url(url)
    slug = slugify_uploader(uploader)
    folder = os.path.join(base_dir, platform, slug)
    return os.path.join(folder, "%(id)s_%(title).50s.%(ext)s")
```

### Recursive Dedup
```python
def get_downloaded_ids(output_dir):
    ids = set()
    if not os.path.isdir(output_dir):
        return ids
    pattern = re.compile(r"^(\d{15,25})_")
    for root, _, files in os.walk(output_dir):
        for fn in files:
            m = pattern.match(fn)
            if m:
                ids.add(m.group(1))
    return ids
```

## Related Code Files

### To Create
- `path_builder.py` — `build_output_template`, `slugify_uploader`, `platform_slug_from_url`.
- `test_path_builder.py` — slugify edge cases (empty, emoji, all-separators, oversized), template construction for both platforms.

### To Modify
- `downloader.py` — recursive `get_downloaded_ids`; `get_ydl_opts` no longer hardcodes `outtmpl`. New helper `_resolve_outtmpl(url, opts, base_dir)` performs an `extract_info(download=False)` pass to fetch metadata, then `build_output_template(...)`. Wire into `_do_download` BEFORE the download call.
- `test_tiktokder.py` — extend `get_downloaded_ids` test to assert recursive walk.

### Performance Caveat
The pre-extract pass adds 1 metadata round-trip per download. Acceptable: yt-dlp caches metadata across the same `YoutubeDL` instance, but here we use one instance per video. Mitigation: pass `process=False` flag and reuse the result for the actual download via `ydl.process_ie_result(info, download=True)`. **Implementation note:** prefer this single-pass pattern over two separate `extract_info` calls.

## Implementation Steps
1. Create `path_builder.py` with the three pure functions.
2. Write `test_path_builder.py` covering slugify edges, template for tiktok/facebook URLs, fallback when uploader missing.
3. Modify `downloader.get_downloaded_ids` to recursive walk.
4. Modify `downloader._do_download` to run a metadata-only pass, compute outtmpl, then run download via `ydl.process_ie_result(info, download=True)` instead of `ydl.extract_info(url, download=True)`.
5. Move `outtmpl` out of `get_ydl_opts` defaults; pass per-call.
6. Add a `base_dir` parameter to `_do_download` and `download_video` (defaults to `output_dir`); future-proofs nested layout.
7. Compile check + run `pytest test_tiktokder.py test_path_builder.py -v`.

## Todo
- [ ] Create `path_builder.py` (slugify, platform_slug_from_url, build_output_template).
- [ ] Create `test_path_builder.py` with edge-case coverage.
- [ ] `downloader.get_downloaded_ids`: switch to `os.walk`.
- [ ] `downloader._do_download`: metadata pass → outtmpl → process_ie_result download.
- [ ] Remove hardcoded `outtmpl` from `get_ydl_opts`.
- [ ] Update `test_tiktokder.py` dedup test to cover nested files.
- [ ] Compile + pytest.

## Success Criteria
- `slugify_uploader("@user/with*emoji😀")` → `"@user_with_emoji"` (or similar safe).
- `slugify_uploader("")` → `"unknown_uploader"`.
- TikTok video downloads to `downloads/tiktok/@user/{id}_*.mp4`.
- Facebook video downloads to `downloads/facebook/{slug}/{id}_*.mp4`.
- `get_downloaded_ids` finds IDs in both flat root and nested subfolders.
- All existing `test_tiktokder.py` cases pass.
- New `test_path_builder.py` cases pass.

## Risk & Mitigation
- **Metadata pre-extract doubles latency** → use `process_ie_result` to reuse metadata for download (single network sequence in yt-dlp).
- **Empty `uploader` for FB pages** → `platform_slug_from_url` extracts page slug from URL path; never produces empty segment.
- **Slug collision across platforms** → platform-first layout (`tiktok/foo` ≠ `facebook/foo`) prevents it.
- **Long titles + nested path > Windows MAX_PATH (260)** → `%(title).50s` already truncates title to 50 chars; nested folder adds ~30 chars; user picks output_dir → mostly fine. Risk noted, no extra mitigation now (deferred unless hit).

## Security
- Slugify strips reserved/path-traversal chars; uploader-controlled strings cannot escape the intended folder.
- `os.walk` follows symlinks by default — set `followlinks=False` (default) to avoid loop attacks if user puts a symlink in `downloads/`.

## Next Steps
- Phase 03 plugs quality/subs/thumb into `get_ydl_opts` alongside the new template handling.
- Phase 07 records the resolved file path into `HistoryRecord.file_path` after each successful download.
