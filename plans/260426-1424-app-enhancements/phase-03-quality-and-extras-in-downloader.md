---
title: "Phase 03 — Quality + subs/thumb in downloader"
priority: P0
effort: 45m
status: planned
depends: [01, 02]
---

# Phase 03 — Quality Selector + Subs/Thumb Plumbing

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ Quality selector → yt-dlp `format`, § Polish features — wiring)
- Affected file: `downloader.py`
- Depends on Phase 01 (`AppConfig` fields) and Phase 02 (template builder).

## Overview
Extend `get_ydl_opts` and `download_video` to accept `quality`, `write_subs`, `write_thumb` arguments. Map quality string → yt-dlp `format` expression. Audio-only branch sets `.m4a` postprocessor. Subs default lang `["en"]`.

## Key Insights
- All quality presets except `Best` use `bv*[height<=N]+ba/b[height<=N]` — requires ffmpeg merge except where a single-stream form satisfies. yt-dlp falls back gracefully.
- Audio-only via `format="ba/b"` + `postprocessors=[FFmpegExtractAudio(preferredcodec="m4a")]`. If ffmpeg missing, document warning (existing `_warn_ffmpeg_missing` already fires).
- Subs: `writesubtitles=True`, `writeautomaticsub=True`, `subtitleslangs=["en"]`, `subtitlesformat="srt/best"` (sidecar SRT next to video).
- Thumbs: `writethumbnail=True`. Sidecar `.jpg` next to video.

## Requirements

### Functional
- `get_ydl_opts` accepts new kwargs:
  - `quality: str = "best"` — one of `best|1080p|720p|480p|audio`
  - `write_subs: bool = False`
  - `write_thumb: bool = False`
- Returns options dict with appropriate `format`, `postprocessors`, `writesubtitles`, etc.
- `download_video` exposes the same new kwargs (passes through to `_do_download` → `get_ydl_opts`).
- Quality `"audio"` overrides any video format selection and produces `.m4a` next to the would-be video path (yt-dlp picks ext based on postprocessor).

### Non-Functional
- `downloader.py` must not exceed 500 LOC (currently 403). Estimated additions ~50 LOC.
- All new options off by default — back-compat preserved.

## Architecture

### Quality Map
```python
QUALITY_FORMATS = {
    "best": "b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p":  "bv*[height<=720]+ba/b[height<=720]",
    "480p":  "bv*[height<=480]+ba/b[height<=480]",
    "audio": "ba/b",
}
```

### Audio Postprocessor
```python
if quality == "audio":
    opts["postprocessors"] = [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "m4a",
        "preferredquality": "0",  # best
    }]
```

### Subs Block
```python
if write_subs:
    opts["writesubtitles"] = True
    opts["writeautomaticsub"] = True
    opts["subtitleslangs"] = ["en"]
    opts["subtitlesformat"] = "srt/best"
```

### Thumbs Block
```python
if write_thumb:
    opts["writethumbnail"] = True
```

## Related Code Files

### To Modify
- `downloader.py` — `QUALITY_FORMATS` constant, extend `get_ydl_opts(... , quality, write_subs, write_thumb)`, propagate through `_do_download`, `download_video`, `download_batch`.
- `download_engine.py` — accept quality/subs/thumb in `__init__` (defaults from `AppConfig`); pass into `DownloadWorker` → `download_video`. *(This is light wiring done here so Phase 07 only handles Settings → engine signal.)*
- `test_tiktokder.py` — assert `get_ydl_opts(quality="720p")` produces expected `format`; `quality="audio"` includes the postprocessor.

### Not Touched This Phase
- `gui/settings_panel.py` — Phase 06.
- `path_builder.py` — already finalized in Phase 02.

## Implementation Steps
1. Add `QUALITY_FORMATS` constant near top of `downloader.py`.
2. Extend `get_ydl_opts` signature; map quality → format; conditionally add postprocessors / sub flags / thumb flags.
3. Extend `_do_download` and `download_video` to accept and forward the new kwargs.
4. Extend `download_batch` to forward kwargs (if exposed at CLI).
5. Update `download_engine.DownloadEngine.__init__` to accept `quality`, `write_subs`, `write_thumb`; pass them into `DownloadWorker` → `download_video`. Default to `"best"`, `False`, `False` (preserve current behaviour).
6. Add tests covering the format string for each quality preset, audio postprocessor presence, subs flag combination.
7. Compile + `pytest test_tiktokder.py test_download_engine.py -v`.

## Todo
- [ ] `QUALITY_FORMATS` constant.
- [ ] `get_ydl_opts(... , quality, write_subs, write_thumb)` plumbing.
- [ ] `_do_download` / `download_video` / `download_batch` forward kwargs.
- [ ] `DownloadEngine.__init__` accepts and forwards quality/subs/thumb.
- [ ] Tests for each quality preset + audio postprocessor + subs/thumb flag.
- [ ] Compile + pytest.

## Success Criteria
- `get_ydl_opts(... , quality="720p")["format"] == "bv*[height<=720]+ba/b[height<=720]"`.
- `get_ydl_opts(... , quality="audio")` includes `FFmpegExtractAudio` postprocessor with `preferredcodec="m4a"`.
- `get_ydl_opts(... , write_subs=True)` sets `writesubtitles`, `writeautomaticsub`, `subtitleslangs=["en"]`.
- `get_ydl_opts(... , write_thumb=True)["writethumbnail"] is True`.
- Default call (`get_ydl_opts(output_dir)`) is byte-identical to pre-phase output (back-compat).
- All existing tests pass.

## Risk & Mitigation
- **Audio postprocessor without ffmpeg** → `_warn_ffmpeg_missing` already fires; surface in tooltip later (Phase 06).
- **Quality format string too aggressive on audio-only platforms (no video stream)** → yt-dlp `b` fallback handles it; user sees best available.
- **Default-arg drift breaking old call sites** → all new args default to current behaviour.

## Security
- No string interpolation of user input into shell commands. Quality literal is validated against `QUALITY_FORMATS` keys; unknown keys fall back to `"b"`.

## Next Steps
- Phase 06: Settings UI emits new fields → engine.
- Phase 07: Engine receives Settings change signal, propagates quality/subs/thumb live (already plumbed in this phase, just needs the signal).
