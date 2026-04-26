# Phase 07 — Svelte tab content (Download, Channel/Page, History, Settings)

## Context Links
- Plan: [plan.md](plan.md)
- Source: `gui/download_tab.py`, `gui/url_input_panel.py`, `gui/download_table.py`, `gui/channel_browser.py` (+ tiktok/facebook sub-panels), `gui/history_tab.py`, `gui/settings_panel.py`
- Phases 03-06 deliverables: engine commands, history commands, channel listing commands, UI shell + IPC wrappers

## Overview
- **Priority:** High
- **Status:** pending
- **Effort:** 4d
- Implement all four tabs to feature parity with v1.2.0. Largest phase. Each tab is one Svelte route with components from `src/lib/components/`.

## Key Insights
- Download table: keep PySide6 column order (URL, Status, Progress, Size, Action). Store rows by URL key.
- Retry/Force/Clear All semantics in `download_engine.py` are complex — port them line for line via the IPC wrappers.
- Channel browser has a sub-tab nesting (TikTok / Facebook) — replicate with a small inner switcher; URL state preserved per sub-tab when switching.
- History tab supports right-click context menu — Tauri 2 supports custom context menus via the menu plugin, but a simpler in-app dropdown is sufficient.
- Settings panel propagates live changes to engine — `setEngineConfig` after each change.

## Requirements (per tab)

### Download tab
- URL input bar with single-URL submission button.
- Drag-and-drop (URL strings + `.txt` batch files anywhere on the tab).
- Import/Export buttons (Import opens `.txt`, Export writes queue + history URLs).
- Queue table:
  - Columns: URL, Status (Queued/Downloading/Done/Failed/Cancelled/Skipped), Progress (%), Size, Action (Cancel/Retry/Force/Open folder).
  - Per-row context menu mirrors PySide6 actions.
  - Header bar: "Cancel All", "Clear All".
- Status footer pulls from store.

### Channel/Page tab
- Inner sub-tabs: TikTok / Facebook (each preserves URL + result state).
- URL input + Browse button per sub-tab.
- Results table: thumbnail (lazy-loaded if any), Title, Quality, Duration, Date, checkbox.
- "Download Selected" button submits selected rows to the engine.

### History tab
- Search field (live), Platform filter (All/TikTok/Facebook), stats footer.
- Table: Title, Platform, Uploader, Quality, Size, Downloaded At, Action.
- Right-click (or Action button): Open file, Open folder, Re-download (force), Copy URL, Remove from history.
- Auto-refresh on `history:changed`.

### Settings tab
- Output Directory (folder picker via Tauri dialog).
- Concurrent Workers (1-10).
- Delay seconds (0.0-10.0, step 0.1).
- Cookie Browser (None/Chrome/Firefox/Edge).
- Default Quality (Best/1080p/720p/480p/Audio).
- Write subtitles (en) toggle.
- Write thumbnail toggle.
- Theme mode (System/Light/Dark — already wired phase 06).
- All changes auto-save + propagate live to engine.

## Architecture

### Components
```
src/lib/components/
├── Download/
│   ├── UrlInputBar.svelte        url input + submit
│   ├── DownloadTable.svelte      queue table
│   ├── DownloadRow.svelte        one row + per-row actions
│   └── DropZone.svelte           drag-drop wrapper
├── Channel/
│   ├── PlatformSubTabs.svelte    TikTok / Facebook switcher
│   ├── ChannelInputBar.svelte    url input + browse + cancel
│   └── VideoListTable.svelte     results table with checkboxes
├── History/
│   ├── SearchFilterBar.svelte    search + platform filter
│   ├── HistoryTable.svelte       paged list
│   └── HistoryRowMenu.svelte     dropdown per row
└── Settings/
    ├── SettingsForm.svelte       sectioned form
    ├── PathPickerRow.svelte      folder picker via dialog plugin
    └── ThemeRadio.svelte         already in phase 06
```

### Stores (`src/lib/stores/`)
- `downloads.ts`:
  ```ts
  type DownloadRow = { url: string; status: 'queued'|'downloading'|'done'|'failed'|'cancelled'|'skipped';
                       percent: number; bytesDone: number; bytesTotal: number|null;
                       title: string|null; filePath: string|null; error: string|null };
  export const rows = writable<Map<string, DownloadRow>>(new Map());
  export const counters = derived(rows, $r => ({ queued: ..., active: ..., done: ..., total: $r.size }));
  ```
- `history.ts`:
  ```ts
  export const items = writable<HistoryRecord[]>([]);
  export const filter = writable<HistoryFilter>({ platform: null, search: '' });
  export async function refresh() { items.set(await historyList(get(filter))); }
  ```
- `channel.ts`:
  ```ts
  type ListingState = { url: string; results: VideoInfo[]; busy: boolean; error: string|null };
  export const tiktok = writable<ListingState>({ url:'', results:[], busy:false, error:null });
  export const facebook = writable<ListingState>(...);
  ```
- `settings.ts`:
  ```ts
  export const cfg = writable<AppConfig>(/* loaded in onMount of layout */);
  export async function setField<K extends keyof AppConfig>(k: K, v: AppConfig[K]) { ... }
  ```

## Related Code Files

### Create
- `src/lib/components/Download/{UrlInputBar,DownloadTable,DownloadRow,DropZone}.svelte`
- `src/lib/components/Channel/{PlatformSubTabs,ChannelInputBar,VideoListTable}.svelte`
- `src/lib/components/History/{SearchFilterBar,HistoryTable,HistoryRowMenu}.svelte`
- `src/lib/components/Settings/{SettingsForm,PathPickerRow}.svelte`
- `src/routes/+page.svelte` (Download tab — wire components)
- `src/routes/channel/+page.svelte`
- `src/routes/history/+page.svelte`
- `src/routes/settings/+page.svelte`
- `tests/unit/*.test.ts` (Vitest, headless): store reducers, IPC wrapper mocks

### Read for context
- All `gui/*.py` files (parity reference)
- `download_engine.py` (retry/force/clear semantics)

### Update
- `src/lib/ipc.ts` — add helpers for batch import (`readBatchFile` via fs plugin), file-drop hook (`getCurrent().onDragDropEvent`).
- `src-tauri/src/commands.rs` — add `read_text_file_lines` (with size cap) and `write_text_file` for import/export, OR use `tauri-plugin-fs` directly from FE (preferred).

## Implementation Steps

### Step 1 — Download tab
1. `UrlInputBar`: input + Enter/click → validate via Rust `validate_url` exposed as `#[tauri::command]` OR client-side regex (cheaper).
2. `DropZone`: wraps the tab; subscribes to `getCurrent().onDragDropEvent`. On drop:
   - URL text → push to `rows` store + `addUrls([url])`.
   - `.txt` files → `readTextFile(path)` (fs plugin), parse line-by-line (skip `#`, dedup), `addUrls(parsed)`.
3. `DownloadTable`: virtualized list with `svelte-virtual-list` if rows > 200; otherwise plain `each`.
4. `DownloadRow`: subscribes to per-URL slice of store. Actions:
   - Cancel → `cancelUrl(row.url)`.
   - Retry → `addUrls([row.url], false)`.
   - Force → `addUrls([row.url], true)`.
   - Open file / folder → `tauri-plugin-shell::open` with `row.filePath` parent dir.
5. Header buttons: Cancel All → `cancelAll()`. Clear All → clear store rows + `cancel_all` on backend, then call `clear_dedup` (new BE command).
6. Import button → dialog `open({ filters: [{name:'Batch URLs', extensions:['txt']}] })` → readTextFile → split + filter via `validate_url` → push.
7. Export button → dialog `save({ defaultPath:'urls.txt' })` → assemble queue + history sections → `writeTextFile`.

### Step 2 — Channel/Page tab
1. `PlatformSubTabs`: two inner buttons; routes are `tiktok` / `facebook` in URL hash so refresh preserves.
2. Each sub-panel:
   - URL input + Browse button → `listChannel(url, onEvent)` with cancel button.
   - Results table populates from store.
   - "Select All" checkbox + per-row checkboxes.
   - "Download Selected" → builds URL list, calls `addUrls(urls, false)`, navigates to Download tab.
3. State preservation when switching sub-tabs: stores `tiktok` / `facebook` keep their state independent.

### Step 3 — History tab
1. `SearchFilterBar`: debounced search (300 ms) + platform select. On change → `historyList(filter)` → store.
2. `HistoryTable`: shows `items`. Paged in chunks of 100; load more on scroll.
3. `HistoryRowMenu` (right-click or "..." button):
   - Open file → `shell.open(row.file_path)`.
   - Open folder → `shell.open(parentDir(row.file_path))`.
   - Re-download (force) → `addUrls([row.url], true)`.
   - Copy URL → `clipboard.writeText(row.url)`.
   - Remove → `historyRemove(row.video_id)`.
4. Stats footer: total count from `historyCount`.
5. Auto-refresh: `listen('history:changed', refresh)`.

### Step 4 — Settings tab
1. `SettingsForm` sections: Downloads, Quality, Cookies, Theme.
2. Each control 2-way bound to `cfg` store; on change → `setField(...)` → `setEngineConfig({...cfg})` (debounced 200 ms for spinbox-y fields).
3. `PathPickerRow`: text + Browse button → `dialog.open({ directory: true })`.
4. After save, settings persist via BE; engine picks up live.

### Step 5 — Vitest unit tests
1. `downloads` store reducers: started → progress → finished transitions, retry, cancel.
2. URL validation matches Rust validator (parity smoke).
3. Import parser: comments, blanks, dedup.
4. Filter logic for history.

## Todo
- [ ] Download tab: URL submit, drag-drop URL, drag-drop .txt, queue table populates, all per-row actions, Cancel/Clear All
- [ ] Channel tab: sub-tabs, listing streams, select-and-download, cancel listing
- [ ] History tab: search, filter, context menu actions, auto-refresh
- [ ] Settings tab: all 8 fields wired live; restart preserves
- [ ] Vitest: 80%+ store coverage
- [ ] Visual parity check against PySide6 screenshots

## Success Criteria
- Manual smoke: queue 5 mixed URLs → all complete with progress visible → History shows all 5.
- Drag a `.txt` file with 10 URLs onto the Download tab → 10 rows queued.
- Channel/Page: search a TikTok profile → results stream in → select 3 → download → switch to Download tab → see them queued.
- History → right-click → Open folder → opens correct directory.
- Settings: change Quality to 720p; subsequent download writes a 720p file.

## Risk Assessment
- **Drag-drop on Tauri 2 Windows.** `fileDropEnabled: true` is required (set in phase 01). URL-string drag from browser tabs uses HTML5 dataTransfer (not Tauri's file-drop) — handle both: `window.addEventListener('drop', ...)` for text/uri-list and Tauri event for files.
- **Per-row store updates re-render entire table.** Use Svelte `key` on `each` + `derived` slice to keep updates O(1). For >500 rows enable virtualization.
- **Live settings cascade race.** Debounce write; engine reads via shared `Arc<RwLock<EngineConfig>>` — atomic swap ensures consistency.
- **Tauri context menu API.** Skip the OS-native menu; use a Svelte dropdown that opens at the right-click coordinates. Simpler and more portable.

## Security
- All URLs validated client-side AND server-side (defense in depth).
- Import file size cap 5 MB at command boundary (`read_text_file` cap).
- Clipboard write content limited to URL strings (regex-validated).

## Next Steps
- Phase 08 polishes remaining UX gaps (toasts, empty states, keyboard shortcuts).
