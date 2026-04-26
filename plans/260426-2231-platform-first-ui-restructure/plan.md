---
title: "Platform-first UI restructure (PySide6) — saved channels + library + global URL bar"
description: "Replace function-mixed 4-tab IA with TikTok | Facebook | Settings top tabs. Each platform tab gets Channels (saved list) / Queue / Library sub-sections. Adds saved_channels.json persistence and Download all new."
status: completed
priority: P1
effort: 3-5 days
branch: feat/platform-first-ui
tags: [gui, pyside6, ux, ia, saved-channels, library]
created: 2026-04-26
blockedBy: []
blocks: [260426-1518-tauri-migration]
---

# Platform-First UI Restructure — Implementation Plan

## Goal
Reorganize the PySide6 GUI from `Download | Channel/Page | History | Settings` (function-first, mixed paradigms) to `TikTok | Facebook | Settings` (platform-first). Each platform tab owns three sub-sections — **Channels** (saved list + browser), **Queue** (per-platform download table), **Library** (two-pane history). A persistent **global URL bar** above the tabs auto-routes URLs by platform. A **status bar** shows per-platform queue/done badges. No backend changes.

Brainstorm: `plans/reports/brainstorm-260426-2222-platform-first-ui-restructure.md`.

## Locked Decisions
| # | Question | Decision |
|---|----------|----------|
| 1 | Tauri overlap | **Pause Tauri**. Ship this on PySide6 first; Tauri (`260426-1518-tauri-migration`) absorbs the new IA when it resumes. This plan `blocks` the Tauri plan. |
| 2 | "Download all new" semantics | **Combined**: `video_id NOT in history(uploader) AND upload_date > saved.last_fetched_at`. Falls back to id-only when `upload_date` missing on the fetched VideoInfo. |
| 3 | Rollout | **Hard cutover.** Phase 6 deletes `gui/channel_browser.py`, `gui/download_tab.py`, `gui/history_tab.py`. No `layout_v2` flag. |
| 4 | Saved-channels cap | Soft cap **200/platform**, FIFO trim oldest by `last_fetched_at` when exceeded. |
| 5 | Persistence file | `data/saved_channels.json` (separate from `state.json`); atomic write via `_atomic_write` reused from `history_store.py`. |
| 6 | Schema versioning | `{"schema": 1, "tiktok": [...], "facebook": [...]}`. Tolerant loader — unknown shape → empty defaults. |

## Out of Scope
- `main.py` CLI parity for saved channels (flagged in brainstorm Q9; later plan).
- Auto-refresh of saved channels on launch (manual only — Refresh button).
- Theme additions in `gui/tokens.py` for new semantic states (existing tokens cover everything; add only if needed during phase 2).
- New backend logic in `download_engine.py` / fetchers / `history_store.py`.
- Keyboard-shortcut overhaul (preserve existing 1:1).

## Source Context
Current GUI (PySide6, ~2000 LOC under `gui/`):
- `gui/main_window.py` — 4 top-tabs wired here.
- `gui/download_tab.py` — URL input + queue table + drag-drop + import/export.
- `gui/channel_browser.py` — TikTok+Facebook sub-tabs (this is already platform-first internally).
- `gui/history_tab.py` — single flat table.
- `gui/settings_panel.py` — global settings.

Backend already platform-aware:
- `url_parser.detect_platform(url)` returns `"tiktok"` / `"facebook"` / `None`.
- `download_engine.DownloadEngine` tags every job with platform via `detect_platform`.
- `history_store.HistoryRecord.platform` set on save.
- Filesystem layout `downloads/{platform}/{uploader}/{id}_{title}.{ext}` already enforced by `path_builder.py`.

State persistence (`app_state.py`, completed in `260426-2218-state-persistence`):
- `AppState` already snapshots queue, channel-browser sub-tabs, browser panels.
- This plan extends `AppState` with `saved_channels` and `library` fields.

## Phases

| # | File | Status | Effort | Depends |
|---|------|--------|--------|---------|
| 01 | [phase-01-saved-channels-store.md](phase-01-saved-channels-store.md) | completed | 0.5d | — |
| 02 | [phase-02-platform-tab-shells.md](phase-02-platform-tab-shells.md) | completed | 1d | 01 |
| 03 | [phase-03-global-url-bar-and-status.md](phase-03-global-url-bar-and-status.md) | completed | 0.5d | 02 |
| 04 | [phase-04-library-two-pane.md](phase-04-library-two-pane.md) | completed | 0.5d | 02 |
| 05 | [phase-05-settings-split.md](phase-05-settings-split.md) | completed | 0.5d | 02 |
| 06 | [phase-06-cutover-and-tests.md](phase-06-cutover-and-tests.md) | completed | 1d | 02, 03, 04, 05 |

**Total: ~4 dev-days.**

## Architecture (target)

```
gui/
├── main_window.py                  3 tabs (TikTok|Facebook|Settings) + global URL bar + status bar
├── platform_tab.py        (NEW)   composite: Channels/Queue/Library sub-tabs (parameterised on platform)
├── saved_channels_panel.py(NEW)   list + CRUD + "Download all new"
├── library_panel.py       (NEW)   two-pane uploader sidebar + filtered history table
├── global_url_bar.py      (NEW)   QLineEdit + drop zone, platform-aware auto-routing
├── status_bar_widget.py   (NEW)   per-platform badges
├── download_table.py              unchanged widget; per-platform filter applied at consumer
├── base_browser_panel.py          unchanged (reused in saved_channels_panel.py for video listing)
├── tiktok_browser_panel.py        unchanged
├── facebook_browser_panel.py      unchanged
└── settings_panel.py              minor: split into Global / TikTok-specific / FB-specific sections

(deleted in phase 6)
gui/channel_browser.py
gui/download_tab.py
gui/history_tab.py

saved_channels_store.py (NEW, project root)
data/
├── config.json
├── history.json
├── state.json
└── saved_channels.json    (NEW)
```

### Data flow (download)
```
GlobalUrlBar.add_clicked
  └─ detect_platform(url)
      ├─ tiktok → TikTokTab.queue.add(url) + engine.add_urls([url])
      └─ facebook → FacebookTab.queue.add(url) + engine.add_urls([url])
engine.download_finished
  └─ MainWindow._on_download_finished → routes to correct platform's queue table
StatusBar polls / receives signal
  └─ shows TT: x / FB: y / Done: z
```

### Data flow (download all new)
```
SavedChannelsPanel.download_all_new(channel)
  └─ fetched_videos = current_panel._videos  (BaseBrowserPanel cache)
      └─ filter: vid_id ∉ history(uploader) AND (upload_date > last_fetched_at OR no date)
          └─ engine.add_urls([v.url for v in filtered])
              └─ saved_channels_store.update_after_fetch(channel, fetched_video_ids, now)
```

## Persistence Schema (`data/saved_channels.json`, schema v1)

```json
{
  "schema": 1,
  "tiktok": [
    {
      "url": "https://www.tiktok.com/@user1",
      "nickname": "main account",
      "note": "",
      "starred": true,
      "last_fetched_at": "2026-04-24T12:34:56+07:00",
      "last_fetched_video_ids": ["7361...", "7360..."]
    }
  ],
  "facebook": []
}
```

- **Cap:** 200 per platform; FIFO-trim oldest `last_fetched_at` (None sorts last) on insert overflow.
- **Loader:** tolerant — unknown shape, missing fields, malformed JSON → empty defaults (mirrors `history_store._read_history_file`).
- **Writer:** atomic via `_atomic_write` (reuse from `history_store.py`).

## State Persistence Extension (`app_state.py`)

Add to `AppState`:
- `library_active_uploader: str | None = None` — last-clicked uploader sidebar entry per platform tab.
- (Saved channels themselves live in `saved_channels.json`, not `state.json`. Active selection / scroll restored via `AppState`.)

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test churn — many tests reference legacy widget names | High | Medium | Phase 6 includes `MainWindow` back-compat aliases (`url_input`, `download_table`) for one release; bulk-update test suite in same PR; remove aliases next minor. |
| Vertical space squeezed by global URL bar | Medium | Low | Slim 24-px URL bar; status bar already in `QMainWindow`. |
| "Download all new" surprises users (queue floods) | Medium | Medium | Confirm dialog showing count + uploader before queueing (>10 videos). Tooltip on button. |
| Tauri plan integration drift | Low | Medium | Tauri plan is `blockedBy` this one — when it resumes, port new IA verbatim to SvelteKit (Phase 07 of Tauri plan). |
| Snapshot restore breaks on first launch after upgrade | Medium | Low | Tolerant loader; legacy `state.json` keys ignored cleanly. |
| User confusion during transition | Medium | Low | Right-click menus preserved 1:1. Status bar makes mixed-batch progress visible. |
| Saved-channels JSON corruption | Low | Medium | Atomic write + on-load validation; rebuild empty on parse error. |

## Success Criteria
- All existing tests pass after Phase 6 update; new tests cover: saved-channels store CRUD, library two-pane filter, global URL bar platform routing, status-bar badge math.
- Re-paste-URL frequency drops to ~0 in dogfooding (saved channels handles it).
- Time-to-find-uploader-in-history < 3s via two-pane filter.
- Zero regression: download throughput, dedup, history persistence, drag-drop.
- Bundle: no new heavy deps; LOC delta ≈ +600/-450 (net +150). New widgets each <200 LOC.
- `data/saved_channels.json` round-trips: add → close app → relaunch → channels restored.

## Validation Criteria (acceptance tests)
- [ ] Global URL bar accepts a mixed `.txt`; URLs land in correct platform queues; non-matching lines reported.
- [ ] Status bar reflects per-platform queue + done counts in real time.
- [ ] Saved channel: add → browse → "Download all new" queues only un-downloaded **and** post-`last_fetched_at` videos. Confirm dialog appears for >10.
- [ ] Library: clicking uploader filters table; "All" unfilters; right-click menu (open/folder/redownload/copy/remove) works on filtered rows.
- [ ] Per-platform settings (TikTok cookie browser, FB cookies.txt + max-scrolls) live-propagate without restart.
- [ ] Snapshot restore preserves: active platform tab, sub-tab, last-clicked library uploader, FB scrolls value.
- [ ] Cross-platform mixed batch from import button works end-to-end.
- [ ] Removed widgets (`channel_browser.py`, `download_tab.py`, `history_tab.py`) — no remaining imports.

## Cross-Plan Dependencies
- **Blocks** `260426-1518-tauri-migration`: Tauri waits for this restructure to land so SvelteKit IA can be ported verbatim.
- **Built on** `260426-2218-state-persistence` (completed): extends `AppState` with `library_active_uploader`.
- **Built on** `260426-1424-app-enhancements` (completed): reuses `BaseBrowserPanel`, `HistoryRecord`, per-platform sub-panels.

## Reference Files
- `plans/reports/brainstorm-260426-2222-platform-first-ui-restructure.md` — design rationale, evaluated approaches.
- `gui/main_window.py:42-329` — current 4-tab wiring; entire `__init__` restructured in Phase 02.
- `app_state.py:46-64` — `BrowserPanelState`, `AppState` (field extension in Phase 04).
- `history_store.py:86-99` — `_atomic_write` reused by `saved_channels_store.py`.
- `url_parser.py:75-82` — `detect_platform` (used by global URL bar router).

## Open Questions (deferred)
- CLI parity for saved channels (`main.py --saved-channel <nickname>`) — defer to follow-on plan.
- Theme tokens for `channel.starred` / `channel.unfetched` — Phase 02 will use existing tokens; add only if visual review demands.
