---
title: "Channel browse filters + Date column + drop ID prefix from filenames"
description: "Add filter/sort/search to TikTok+Facebook browse tables, populate Date column from yt-dlp timestamp, remove video-ID prefix from saved filenames while keeping legacy dedup intact."
status: completed
priority: P2
effort: 6h
branch: main
tags: [gui, downloader, dedup, ux]
created: 2026-05-04
---

# Plan — Channel filters & filename cleanup

## Goals

1. **Browse panel filters** — search + Quality dropdown + From/To date toggles + sortable headers on `BaseBrowserPanel`. Mirror `LibraryPanel` idioms (200ms debounce, single timer, `_NumericItem` for numeric sort).
2. **Date column populated** — read `entry["timestamp"]` (epoch) in `channel_fetcher.py`, format as `YYYYMMDD`. Document Facebook gap (Playwright scrape has no per-video metadata).
3. **Filename cleanup** — drop `{id}_` prefix from saved filenames; keep dedup working for legacy ID-prefixed files AND new title-only files.

## Recommendation: inline column filters vs. top filter row

**Recommendation: top filter row, NOT inline column filters.**

Reasons:
- Library already uses a top filter row. Reusing the idiom keeps the GUI coherent and removes a discoverability tax.
- Inline column filters require either a custom header widget or a `QSortFilterProxyModel` migration — `BaseBrowserPanel` uses raw `QTableWidget` with `setCellWidget` checkboxes, which doesn't compose cleanly with a proxy model. Cost > benefit.
- Top row works fine even on a tall, narrow column like Quality where an inline dropdown would feel cramped.
- Sortable headers (`setSortingEnabled(True)`) cover the "click to sort" need without inline UI.

## Phases

| # | Phase | Status | File |
|---|-------|--------|------|
| 1 | Browse panel filter + sort row | completed | [phase-01-browse-filter-row.md](phase-01-browse-filter-row.md) |
| 2 | Populate Date column (TikTok timestamp) | completed | [phase-02-populate-date-column.md](phase-02-populate-date-column.md) |
| 3 | Filename refactor + dual-path dedup | completed | [phase-03-filename-cleanup-and-dedup.md](phase-03-filename-cleanup-and-dedup.md) |
| 4 | Tests + docs sync | completed | [phase-04-tests-and-docs.md](phase-04-tests-and-docs.md) |

**Title-collision strategy chosen:** Option B — `%(title).80s [%(id).6s].%(ext)s`. Six-char bracketed ID suffix uniquifies same-title videos with minimal visual noise.

## Dependencies

- Phase 1 → independent of Phase 2/3; can ship alone.
- Phase 2 → independent; useful even if Phase 1 ships first (filters become more useful when Date is populated).
- Phase 3 → independent of Phase 1/2 but riskiest. Recommend shipping last after thorough tests.
- Phase 4 → blocks final commit; depends on 1–3.

## Risk callout — filename change (Phase 3)

Removing the `{id}_` prefix loses the regex anchor that `get_downloaded_ids()` uses to recognize already-downloaded files on disk. Mitigations baked into Phase 3:

1. **Two-source dedup**: keep regex scan for legacy `{id}_*.ext` files; ADD a history.json-driven set so files saved under the new template are recognized via `HistoryRecord.video_id`.
2. **Title collision**: yt-dlp `outtmpl` does not auto-uniquify same-title files in the same uploader folder. Recommended approach: `%(title).80s [%(id).6s].%(ext)s` — keeps a short 6-char ID suffix in brackets ONLY when needed for uniqueness. **Decision deferred**: see Phase 3 "Title-collision strategy" — the planner-recommended option is **(b-modified)** with a short bracketed ID, since pure-title overwrites would be silent data loss.
3. **Migration path**: no rename of existing files. Old files keep their `{id}_*` shape; new downloads use the new shape; both detected by Phase 3's `get_downloaded_ids()` rewrite.

## Constraints

- YAGNI/KISS/DRY — reuse `LibraryPanel._build_filter_row` idioms (signal wiring pattern, debounce timer).
- Update files in place. No `*_v2.py`.
- `BaseBrowserPanel._videos` list is consumed by `SavedChannelsPanel` for "Download new only" — filtering must affect the table view only, never mutate `_videos`.
- Facebook fetcher stays metadata-poor; the plan documents this gap and does not add per-video Playwright scrapes (out of scope, expensive).

## Unresolved questions

- None for Phase 1, 2, 4.
- Phase 3: confirm chosen title-collision strategy. Plan recommends bracketed short-ID suffix; user said "no ID in name" which strictly rules this out — fallback option is `%(title).80s.%(ext)s` with yt-dlp's `nooverwrites=True` (skips silently on collision). Phase 3 documents both; pick one before merging.
