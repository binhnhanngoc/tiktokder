# Brainstorm — Platform-First UI Restructure

**Date:** 2026-04-26
**Scope:** GUI reorganization for clearer platform separation, saved channels, and library browsing.
**Status:** Design agreed; ready for `/ck:plan` if user opts in.

## 1. Problem Statement

Current 4-tab layout (Download / Channel / History / Settings) mixes two paradigms:
- **Function-first** for Download + History (mixed-platform)
- **Platform-first** for Channel/Page (TikTok + Facebook sub-tabs)

Pain points reported:
- Channels/pages must be re-pasted every session — no persistence.
- History is one flat table; uploader-level browsing requires search.
- Mental whiplash from inconsistent platform separation.
- Filesystem already groups `downloads/{platform}/{uploader}/...` but UI doesn't reflect it.

User profile: uses **both platforms interleaved**; wants **strong visual separation** without losing mixed-batch ergonomics.

## 2. Evaluated Approaches

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Platform-first top tabs** | Clearest mental model; consistent everywhere | Mixed batches awkward without bridge | ✅ Chosen (with global URL bar bridge) |
| B. Sidebar + sections | Scales well; full hierarchy visible | Bigger UI shift; vertical space cost | Rejected (over-engineered for 2 platforms) |
| C. Tabs + filter chips | Cheapest refactor | Doesn't solve channel-organization | Rejected (insufficient) |
| D. Function tabs + per-platform sub-tabs | Consistent pattern | Still spreads platform logic across 3 tabs | Rejected (too much duplication) |

## 3. Final Design

### 3.1 Top-Level Layout

```
+----------------------------------------------------------+
| [ Paste URL or drop .txt here ]              [ Add ]     |  <- global URL/drop bar
+----------------------------------------------------------+
| TikTok | Facebook | Settings                             |  <- top tabs (platform-first)
+----------------------------------------------------------+
|                                                          |
|  ( active platform's content — see 3.2 )                 |
|                                                          |
+----------------------------------------------------------+
| TT queued: 12 · FB queued: 5 · done: 7 · Ready          |  <- status bar with badges
+----------------------------------------------------------+
```

- **Global URL bar (top):** persistent across all tabs. Auto-detects platform per URL via `url_parser.detect_platform`. Drag-drop `.txt` here splits URLs by platform and routes each to the correct tab's queue.
- **Top tabs:** `TikTok | Facebook | Settings` (3 tabs only, down from 4).
- **Status bar:** platform-aware badges (`TT: N · FB: N · done: N`) replace the single "Downloaded N/M" line.

### 3.2 Per-Platform Tab — Three Sub-Sections

Each platform tab uses an internal sub-tab bar:

```
[ Channels ]  [ Queue ]  [ Library ]
```

#### 3.2.1 Channels (saved list + browser)

```
+--------------------------------------------------------+
| [ + Add channel/page ]   [ Refresh all ]              |
+--------------------------------------------------------+
| ★ @user1     "main account"   28 vids · 2d ago  [...] |
|   @user2                      14 vids · 1w ago  [...] |
|   @user3                       8 vids · never  [...]  |
+--------------------------------------------------------+
| (videos panel — shows fetched video list for selected) |
| [select all] [download selected] [download all new]    |
+--------------------------------------------------------+
```

- **Saved list** persisted in `data/saved_channels.json`, schema:
  ```json
  {
    "tiktok": [
      {
        "url": "...",
        "nickname": "main account",
        "note": "",
        "last_fetched_at": "2026-04-24T...",
        "last_fetched_video_ids": ["...", "..."]
      }
    ],
    "facebook": [...]
  }
  ```
- **Row actions** (right-click): Browse/Refresh · Download all new · Rename + notes · Edit URL · Remove.
- **"Download all new"**: queue every fetched video whose `video_id` is **not in history** for that uploader. Definition leans on existing dedup logic — no new infra needed.
- **Videos panel** below the list = current `BaseBrowserPanel` reused (table + checkboxes + Download Selected). Just rewires data source.

#### 3.2.2 Queue (per-platform download table)

- Same widget as today's `DownloadTableWidget`, filtered to one platform.
- Each platform owns its own queue view; underlying `DownloadEngine` stays single (one thread pool, platform-tagged jobs).
- Toolbar buttons (Clear Completed / Clear All / Retry Failed / Cancel All) scoped to that platform.

#### 3.2.3 Library (two-pane history)

```
+-------------------+----------------------------------+
| All        (142)  | Title       Quality  Size  Date  |
| ★ @user1   (28)   | ...                              |
|   @user2   (14)   |                                  |
|   @user3    (8)   |                                  |
|   ...             |                                  |
| [search uploader] | [search title] [filter quality]  |
+-------------------+----------------------------------+
```

- **Left pane:** uploader list with video counts. Click "All" → unfiltered. Click an uploader → filter table.
- **Right pane:** existing history table (Title/Quality/Size/Date/Path), search + right-click actions preserved (Open file · Open folder · Re-download · Copy URL · Remove).
- Records live in same `history.json` — just a new view widget over existing store. No schema change.

### 3.3 Settings Split

- **Global Settings tab** keeps: output dir, workers, delay, default quality, write-subs, write-thumb, history cap, theme.
- **TikTok tab → Settings sub-section** (or inline panel): cookie browser dropdown.
- **Facebook tab → Settings sub-section**: `cookies.txt` path + max-scrolls + login-wall warnings.
- Live-propagation logic in `MainWindow._apply_settings` extends to per-platform panels via existing signal pattern.

### 3.4 Cross-Platform Bridges

Despite platform-first separation, three mechanisms keep mixed workflows smooth:

1. **Global URL bar** → auto-routes per URL.
2. **Status bar badges** → see both platforms' progress without tab-switching.
3. **Import .txt** lives on the global bar and splits by platform automatically.

## 4. Implementation Considerations

### 4.1 What Must Change

| File | Change |
|---|---|
| `gui/main_window.py` | Tab restructure, global URL bar widget, status bar with badges |
| `gui/tiktok_tab.py` *(new)* | Composite: Channels + Queue + Library sub-tabs |
| `gui/facebook_tab.py` *(new)* | Same composite for Facebook |
| `gui/saved_channels_panel.py` *(new)* | List view + CRUD + "Download all new" action |
| `gui/library_panel.py` *(new)* | Two-pane: uploader sidebar + filtered table |
| `gui/global_url_bar.py` *(new)* | URL input + drop zone above tabs |
| `gui/status_bar_widget.py` *(new)* | Platform-aware badge counters |
| `config.py` / new `saved_channels_store.py` | `saved_channels.json` persistence (load/save/append/remove) |
| `app_state.py` | Add `SavedChannelState` to snapshot for cross-session restore |
| `gui/history_tab.py` | Refactor → `library_panel.py`; old single-table mode kept as fallback |
| `gui/channel_browser.py`, `gui/download_tab.py` | Deprecated — logic absorbed into platform tabs |

### 4.2 What Stays Untouched

- `download_engine.py` — already platform-aware via URL detection. No change.
- `downloader.py`, `channel_fetcher.py`, `facebook_fetcher.py` — backend untouched.
- `history_store.py` — same schema; just new view consumer.
- `path_builder.py` — filesystem layout already platform-first; UI now matches it.

### 4.3 Persistence

New file: `data/saved_channels.json`. Atomic write via existing pattern in `history_store.py`. Versioned schema (`v1`) for future migration.

## 5. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Test suite churn (GUI tests in `test_tiktokder.py`) | High | Medium | Update tests in same PR; keep back-compat handles for `url_input` / `download_table` aliases on `MainWindow` like today. |
| Vertical space squeezed by global bar + status bar | Medium | Low | Slim 24px URL bar; status bar is already in `QMainWindow`. |
| "Download all new" semantics surprise users | Medium | Medium | Tooltip + confirm dialog showing count before queueing. |
| Saved-channels JSON corruption | Low | Medium | Atomic write + on-load validation; rebuild on parse error. |
| Snapshot/restore breaks on first launch after upgrade | Medium | Low | Migrate old snapshot in `app_state.load()`; default-empty saved-channels if absent. |
| User confusion during transition | Medium | Low | Keep keyboard shortcuts; preserve right-click menus 1:1. |

## 6. Success Metrics

- Re-paste-URL frequency drops to ~zero (saved channels handles it).
- Time-to-find-uploader-in-history < 3 seconds (two-pane filter).
- Zero regression in: download throughput, dedup, history persistence, drag-drop.
- All existing tests pass after update; new tests for saved-channels store + library panel.

## 7. Validation Criteria

- [ ] Global URL bar accepts a mixed `.txt`; URLs land in correct platform queues.
- [ ] Status bar reflects per-platform queue + done counts in real time.
- [ ] Saved channel: add → browse → "Download all new" queues only un-downloaded videos.
- [ ] Library: clicking uploader filters table; "All" unfilters; search still works.
- [ ] Per-platform settings (cookies) live-propagate without restart.
- [ ] Snapshot restore preserves: active platform tab, sub-tab, saved list, library scroll.
- [ ] Cross-platform mixed batch from import button still works end-to-end.

## 8. Next Steps

1. Run `/ck:plan` to break this into phases (suggested):
   - **Phase 1**: Saved-channels store + persistence (no UI change yet).
   - **Phase 2**: New `tiktok_tab.py` / `facebook_tab.py` composites; preserve old tabs in parallel for testing.
   - **Phase 3**: Global URL bar + status bar widget.
   - **Phase 4**: Library two-pane refactor.
   - **Phase 5**: Settings split + cross-platform bridges polish.
   - **Phase 6**: Remove deprecated `channel_browser.py` / `download_tab.py` / `history_tab.py`; update tests + docs.
2. Decide rollout: feature-flag (`AppConfig.layout_v2: bool`) or hard cutover.

## 9. Unresolved Questions

- **"New" definition for "Download all new"**: strictly *not in history* (current dedup), or also *upload_date > saved_channel.last_fetched_at*? First is simpler and reuses existing logic; second handles the edge case where a video was deleted from history but still on disk.
- **Saved-channels limit**: cap or unbounded? Suggest soft cap of 200 per platform (similar to history's 10k cap).
- **Theme support for new widgets**: confirm `gui/tokens.py` covers all new semantic states (e.g. `channel.starred`, `channel.unfetched`).
- **CLI parity**: should `main.py` gain `--saved-channel <nickname>` shortcut? Out of scope for this UI brainstorm but worth flagging.
- **Feature flag**: should we ship behind `layout_v2` toggle for one release, or do a clean cutover? Lean cutover given small user base and full test coverage.
