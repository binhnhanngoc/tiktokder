# Phase 02 — Platform tab shells (Channels / Queue / Library)

**Status:** pending
**Effort:** 1d
**Depends on:** Phase 01

## Context Links
- Plan: `plan.md`
- Brainstorm: §3.2
- Phase 01 output: `saved_channels_store.py` API.
- Reuse: `gui/base_browser_panel.py`, `gui/download_table.py`, `gui/tiktok_browser_panel.py`, `gui/facebook_browser_panel.py`.

## Overview
Build the per-platform composite widget — three sub-tabs (Channels / Queue / Library) — and the saved-channels panel UI. Library and Settings split land in their own phases (04, 05). Library shows a placeholder this phase.

## Key Insights
- One generic `PlatformTab` parameterised on `platform: str` ("tiktok"/"facebook") reduces duplication. Inject the right browser panel + saved-channels store slice.
- `DownloadTableWidget` is shared but **filtered per-platform at the consumer** — easier than per-instance filter state. Consumer = `PlatformTab.queue_panel`.
- `BaseBrowserPanel` already does video table + Browse + Download Selected — reuse inside Channels sub-section as the videos panel below the saved list.
- Right-click on saved channel row drives all CRUD; no toolbar buttons except `+ Add` and `Refresh all`.

## Requirements
**Functional**
- `PlatformTab(platform)` exposes:
  - `channels_panel` — saved-channels list + browser-below.
  - `queue_panel` — `DownloadTableWidget` filtered to this platform.
  - `library_panel` — placeholder this phase; replaced in Phase 04.
- `SavedChannelsPanel`:
  - List rows: ★ + nickname + url + N videos · Xd ago.
  - Row actions (right-click): Browse/Refresh · Download all new · Rename + notes · Edit URL · Star/Unstar · Remove.
  - `+ Add channel/page` opens dialog (URL + optional nickname/note).
  - `Refresh all` triggers Browse on each saved row sequentially (status bar update only — no UI freeze).
  - "Download all new" emits `urls_to_queue: list[str]` after confirm dialog (>10 videos).
- Browser-below panel = the existing `TikTokBrowserPanel` / `FacebookBrowserPanel` instance, controlled by selecting a saved row.

**Non-functional**
- All new files <200 LOC each.
- No regression in browse/download flows.

## Architecture
```
gui/platform_tab.py             (NEW, ~150 LOC)
  class PlatformTab(QWidget):
    def __init__(self, platform: str, browser_panel, store, parent=None)
    sub-tab QTabWidget: [Channels | Queue | Library]

gui/saved_channels_panel.py     (NEW, ~180 LOC)
  class SavedChannelsPanel(QWidget):
    signals: download_requested(list[str])  # already-validated URLs to queue
             channel_selected(str url)      # tells PlatformTab to load into browser
    Top: QTableView (rows = SavedChannel)
    Bottom: hosts injected browser_panel (TikTok or Facebook)
```

### Wiring inside PlatformTab
```
PlatformTab(platform=tiktok)
├── sub_tabs[0] Channels:
│   └── SavedChannelsPanel(store_slice=tiktok, browser=TikTokBrowserPanel(...))
├── sub_tabs[1] Queue:
│   └── DownloadTableWidget   (filtered by platform)
└── sub_tabs[2] Library:
    └── QLabel("Library coming in phase 04")  (placeholder)
```

### Per-platform queue filter
`DownloadTableWidget` is one widget instance per `PlatformTab`. Engine signals (`download_started`, `download_progress`, `download_finished`) are routed by `MainWindow` to the matching `PlatformTab.queue_panel` based on `detect_platform(url)`. **Each tab owns its own table** — no row sharing.

## Related Code Files
**Create**
- `gui/platform_tab.py`
- `gui/saved_channels_panel.py`
- `test_saved_channels_panel.py` (basic smoke + signal emission tests)

**Modify**
- `gui/main_window.py` — replace 4-tab construction with 3 platform tabs (still uses old global URL bar via `DownloadTab` for now; full bar in Phase 03). Route engine signals per-platform. **Do NOT delete legacy widgets yet** (Phase 06).

**Read for context**
- `gui/channel_browser.py` — current 2-sub-tab pattern (informative only).
- `gui/main_window.py:104-145` — current signal wiring.

## Implementation Steps
1. **`gui/platform_tab.py`**:
   - `class PlatformTab(QWidget)`.
   - QVBoxLayout → inner QTabWidget with 3 tabs.
   - `__init__(platform, browser_panel, store, parent)`.
   - Public attrs: `channels_panel`, `queue_panel`, `library_panel`, `browser_panel` (delegate ref).
   - `set_active_sub_tab(index)` / `current_sub_tab_index()`.
2. **`gui/saved_channels_panel.py`**:
   - QTableView (5 cols: ★ / Nickname / URL / Videos / Last fetched).
   - "+ Add" dialog → `QInputDialog.getText` for URL, optional nickname.
   - Right-click menu wired to `SavedChannelsStore` mutations + `save_saved_channels`.
   - `download_all_new(channel)`:
     - `fetched = browser_panel._videos` (already-cached list).
     - `history_ids = engine._history` (set of vid IDs).
     - `new = saved_channels_store.select_new_videos(channel, fetched, history_ids)`.
     - If `len(new) > 10`: `QMessageBox.question` with count.
     - Emit `download_requested.emit([v.url for v in new])`.
   - On row-click: emit `channel_selected(url)` → `PlatformTab` sets `browser_panel.url_input` + triggers `_on_browse()`.
3. **`gui/main_window.py` rewrite**:
   - Replace `self.download_tab`, `self.channel_browser`, `self.history_tab` with:
     ```python
     self.tiktok_tab = PlatformTab("tiktok", TikTokBrowserPanel(...), self._saved_store)
     self.facebook_tab = PlatformTab("facebook", FacebookBrowserPanel(...), self._saved_store)
     self.tabs.addTab(self.tiktok_tab, icon("mdi6.music-note"), "TikTok")
     self.tabs.addTab(self.facebook_tab, icon("mdi6.facebook"), "Facebook")
     self.tabs.addTab(self.settings_panel, "Settings")
     ```
   - Engine signal routing:
     ```python
     def _route(url, *args, slot_name):
         tab = self.tiktok_tab if detect_platform(url) == "tiktok" else self.facebook_tab
         getattr(tab.queue_panel, slot_name)(url, *args)
     ```
   - Keep back-compat aliases: `self.url_input`, `self.download_table` → point at `self.tiktok_tab.queue_panel` and a dummy URL input (Phase 03 replaces with global bar).
   - Saved channels store loaded once in `MainWindow.__init__` from `SAVED_CHANNELS_PATH`; persisted on every mutation by panels.
4. Drag-drop on each `PlatformTab` accepts `.txt` and routes per-line by platform (existing `read_batch_file` + `detect_platform`).
5. Phase-02 tests:
   - `PlatformTab` constructs with both browser-panel types.
   - `SavedChannelsPanel.download_all_new` emits `download_requested` with filtered URLs.
   - `MainWindow` routes a TikTok `download_started` signal to TikTok tab's queue only.
6. Compile-check + run `pytest -v`; expect existing tests still passing (back-compat aliases preserve `url_input` / `download_table`).

## Todo List
- [ ] `gui/platform-tab.py` created
- [ ] `gui/saved-channels-panel.py` created (CRUD + Download all new + confirm dialog)
- [ ] `MainWindow` rebuilt with 3 platform tabs
- [ ] Engine signal routing per-platform working
- [ ] Back-compat handles preserved (`self.url_input`, `self.download_table`)
- [ ] `test_saved_channels_panel.py` smoke tests passing
- [ ] All existing tests still green
- [ ] Drag-drop works on each platform tab; cross-platform `.txt` splits correctly

## Success Criteria
- App launches; can add a saved channel; click row → browser fetches videos; Download all new queues only un-downloaded post-cutoff videos.
- Each platform tab's queue table shows only its platform's downloads.
- No GUI test regressions.

## Risk Assessment
- **Engine signal routing** — `download_finished` carries the URL, so detection is straightforward. Verify `download_progress` signature includes URL for routing (yes — `engine.download_progress.emit(url, percent)`).
- **`_history` access** — `engine._history` is a `set[str]`. Reading from UI thread is safe (Python GIL); but document that it's a snapshot.

## Security Considerations
- "Download all new" confirm dialog mitigates accidental queue floods.
- Saved-channels JSON written via `_atomic_write`; no race on concurrent writes (single-threaded UI).

## Next Steps
Phase 03 adds the global URL bar + status bar.
