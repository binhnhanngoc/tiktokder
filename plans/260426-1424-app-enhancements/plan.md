---
title: "TikTokDer App Enhancements — Sub-Tabs, History UI, Quality, Folder Layout"
description: "Phased implementation of separated TikTok/Facebook sub-tabs, History tab with rich records, quality selector, per-uploader folder layout, plus polish: drag-and-drop, subs/thumb toggles, import/export."
status: completed
priority: P1
effort: 7-9h
branch: main
tags: [gui, history, quality, folders, ux, schema-migration]
created: 2026-04-26
completed: 2026-04-26
blockedBy: []
blocks: []
---

# App Enhancements — Implementation Plan

## Goal
Implement the seven user-requested features defined in `plans/reports/brainstorm-260426-1417-app-enhancements.md` with minimum disruption: GUI gains a `History` tab and TikTok/Facebook sub-tabs, downloads land in `downloads/{platform}/{uploader}/{id}_{title}.ext`, a quality selector and subs/thumb toggles flow into yt-dlp, and history persists rich records (schema v2). Dedup remains correct across both old flat files and the new tree.

## Out of Scope
- Migrating old flat downloads into the new tree (left-as-is per brainstorm decision #6).
- Auto-probe of stream quality (rate-limit risk).
- Pause/resume, bandwidth limit, dark mode, scheduling, REST API (deferred).

## Source Reports
- `plans/reports/brainstorm-260426-1417-app-enhancements.md` (approved design)
- `plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` (background — informs UX choices, not implementation specifics)

## Locked Decisions (open questions in brainstorm)
| # | Question | Decision |
|---|----------|----------|
| 1 | History retention cap | Soft cap **10000 entries**, FIFO prune metadata only; files untouched. Configurable via `AppConfig.history_max_entries`. |
| 2 | Audio-only output ext | **`.m4a`** (no ffmpeg postprocess required for AAC). Keep `.mp3` opt-in via future setting if user requests. |
| 3 | Subtitle languages | Hardcoded **`["en"]`** initially when subs toggle on. UI exposure deferred. |
| 4 | Import format | **`.txt` only** (existing batch-file format with `# platform: uploader` comment lines for export). |

## Phases

| # | Phase | Priority | Effort | Status | Depends |
|---|---|---|---|---|---|
| 01 | [History schema v2 + AppConfig extensions](phase-01-history-schema-and-config.md) | P0 | 50m | completed | — |
| 02 | [Path builder + recursive dedup](phase-02-path-builder-and-recursive-dedup.md) | P0 | 45m | completed | — |
| 03 | [Quality + subs/thumb in downloader](phase-03-quality-and-extras-in-downloader.md) | P0 | 45m | completed | 01, 02 |
| 04 | [Channel/Page sub-tab split](phase-04-channel-page-sub-tabs.md) | P0 | 1h | completed | — |
| 05 | [History tab](phase-05-history-tab.md) | P0 | 1h 15m | completed | 01 |
| 06 | [Settings panel extensions](phase-06-settings-panel-extensions.md) | P0 | 25m | completed | 01 |
| 07 | [Engine wiring + polish (drag-drop, import/export)](phase-07-engine-wiring-and-polish.md) | P1 | 1h | completed | 03, 04, 05, 06 |
| 08 | [Tests + docs](phase-08-tests-and-docs.md) | P1 | 1h 15m | completed | 01–07 |

## Dependency Graph
```
01 ──┬──> 03 ──┐
     ├──> 05 ──┤
     └──> 06 ──┤
              ├──> 07 ──> 08
02 ──> 03 ────┤
04 ───────────┘
```

## High-Level Acceptance Criteria
- Channel/Page tab shows inner `TikTok` / `Facebook` sub-tabs; switching preserves each panel's URL + table state.
- New top-level `History` tab lists all downloaded videos with columns: Title, Platform, Uploader, Quality, Size, Date, Path. Search box filters live; platform combo filters by `tiktok|facebook|all`.
- Right-click on a history row opens: `Open file`, `Open containing folder`, `Re-download`, `Copy URL`, `Remove from history`.
- Stats labels at top of History tab: total count, total size (human-readable), per-platform count, top-5 uploaders.
- Settings has `Default Quality` combo (`Best / 1080p / 720p / 480p / Audio-only`), `Write subtitles (en)` checkbox, `Write thumbnail` checkbox.
- A downloaded TikTok video lands at `downloads/tiktok/{slugified_uploader}/{id}_{title}.mp4`; a Facebook video at `downloads/facebook/{slug}/...`.
- Dedup correctly skips a previously-downloaded video whether the file is in the flat root or `tiktok/<user>/`.
- History schema auto-migrates from v1 (`list[str]`) → v2 (records) on first load with no data loss.
- Drag-and-drop URLs onto the Download tab adds them to the queue; dropping a `.txt` file imports it.
- Import/Export buttons in Download tab work with `.txt` round-trip.
- All existing 104 tests pass; ~20 new tests cover new modules.

## Backwards Compatibility
- `load_history()` keeps `set[str]` return type for existing dedup callers; new `load_history_records()` powers the History tab.
- `AppConfig` gets new fields with defaults; old configs load unchanged (unknown-field filter already exists).
- `download_video()` keeps positional signature; new `quality`/`write_subs`/`write_thumb`/`base_dir` are optional kwargs.
- `get_downloaded_ids()` becomes recursive but still returns `set[str]`; behaviour is a strict superset.
- yt-dlp `outtmpl` template change is internal — old files in flat root remain valid (recursive dedup covers them).

## Rollback Strategy
Each phase is a separate commit. Reverting phase N restores prior behaviour without touching later phases. Schema v1→v2 migration is one-way but lossless; rolling back to v1 code reads v2 file as malformed → falls back to empty (acceptable: dedup re-builds from filesystem on next run).

## Risk Summary
- **Med:** `outtmpl` template change with empty `%(uploader)s` could write to `downloads/tiktok//...`. Mitigation: pre-extract metadata via `extract_info(download=False)` and compute path in Python; pass full path to yt-dlp via `outtmpl` per-call; fallback slug `unknown_uploader` when missing.
- **Med:** Recursive `os.walk` on huge `downloads/` slow on first run. Mitigation: cache in `DownloadEngine`; rescan only on first run + after each completed download (incremental add).
- **Med:** `gui/channel_browser.py` is currently 182 LOC; splitting into TikTok/FB panels will exceed 200-LOC limit if naive. Mitigation: extract shared base `_BaseBrowserPanel` (~80 LOC) + thin per-platform subclasses (~40 LOC each), parent wraps `QTabWidget`.
- **Low:** History file growth — soft cap at 10000 entries with FIFO prune (metadata only).
- **Low:** History v1→v2 migration race on concurrent writes. Mitigation: atomic write (temp + os.replace), already used in repo idiom.
- **Low:** Quality selector breaks on platforms without 1080p. Mitigation: yt-dlp `format` syntax `bv*[height<=N]+ba/b[height<=N]` already includes graceful fallback to best available.

## Success Metrics (manual)
- TikTok 5-URL batch with quality=720p: every file ≤720p height, lands in `downloads/tiktok/<user>/`, History tab populates within 1s of completion.
- FB page browse → 3 video download: lands in `downloads/facebook/<page>/`, History tab populates.
- Dedup test: drop a previously-downloaded video URL into queue → row marks `Skipped` whether the existing file is at flat root or in tree.
- 104 existing tests pass; new tests pass.
- No regression in single-URL CLI or batch-CLI flows.
