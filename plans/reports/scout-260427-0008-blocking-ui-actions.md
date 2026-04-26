# Scout: Blocking UI Actions in TikTokDer GUI

**Goal:** Identify why rapid profile switching hangs the app. Audit all other actions for similar issues.

## Root cause (P0 — confirmed)

**`gui/base_browser_panel.py:111-113`** — blocking `fetcher.wait()` on the GUI thread:

```python
if self._fetcher is not None and self._fetcher.isRunning():
    self._fetcher.cancel()        # sets _cancelled flag
    self._fetcher.wait()          # ← BLOCKS GUI thread until worker exits
```

`cancel()` only sets a flag; the worker checks it between iterations. For:
- **TikTok (yt-dlp)** — typically <1s
- **Facebook (Playwright)** — sits inside `page.wait_for_timeout(2500)` or `page.goto(timeout=30_000)`. Cancel can take 3–30s; meanwhile the GUI is frozen.

The Browse button is disabled during fetch (line 129/164), but **double-click on a saved channel row bypasses that guard** by calling `_on_browse()` directly via `_refresh_channel()` (saved_channels_panel.py:248).

## Trigger paths into the blocking wait

| # | Trigger | File:line |
|---|---|---|
| 1 | Saved-channel double-click | `saved_channels_panel.py:211` → `_show_channel` → `_refresh_channel` → `_on_browse` |
| 2 | Context menu "Refresh (fetch)" | `saved_channels_panel.py:325-326` |
| 3 | Browse button / Enter | `base_browser_panel.py:53,58` (button disabled — but only after first click registered) |
| 4 | "Refresh all" toolbar | `saved_channels_panel.py:295` (only refreshes first channel currently) |
| 5 | FB "Load more" | `facebook_browser_panel.py:68` (early-returns, but base `_start_fetcher` could still be reached if state inconsistent) |

## Other potentially-blocking actions

| Action | File:line | Blocking op | Severity |
|---|---|---|---|
| Saved-channel mutations (add/star/remove/rename/edit URL) | `saved_channels_panel.py:208,335,345,362,395` | `_persist()` → atomic file write | Low — single small JSON write, ~10–80ms |
| Library uploader sidebar click | `library_panel.py:184` | In-memory filter only (refresh() reads disk, but only fires on `history_changed`) | Negligible |
| "Download all new" | `saved_channels_panel.py:400` | `_persist()` write | Low |
| Engine queue / cancel / retry | `download_engine.py` | already QThread-based | OK |

## Existing async patterns

- **`ChannelFetcher` / `FacebookFetcher`** — QThread with `video_found` / `error` / `finished_fetch` signals. Good pattern.
- **`DownloadWorker` / `DownloadEngine`** — QThread pool. Good pattern.
- **Library search** — 200ms QTimer debounce. Good pattern (`library_panel.py:117-122`).
- **Browse button disabled during fetch** — present (`base_browser_panel.py:129,164`).

## Existing progress UI

- `status_label` text updates ("Fetching videos...", "Found N videos") — no spinner.
- Per-row progress bars in download queue table. Good.
- **No** `QProgressBar` for indeterminate fetches.
- **No** busy cursor during long ops.
- **No** disable-during-fetch on saved-channels table or context menus.

## Fix scope (recommended)

P0 — **wait() removal + busy UI**:
1. Replace `fetcher.wait()` with signal-based handoff (no blocking).
2. Add indeterminate `QProgressBar` to `BaseBrowserPanel` — shown during fetch.
3. Emit `fetch_started` / `fetch_finished` signals so siblings can disable controls.
4. `SavedChannelsPanel` disables its table + Add/Refresh-all + context menu while a fetch is active.
5. Add Cancel button (visible only during fetch) — sets `_cancelled`, no blocking wait.

P1 — **deferred** (low impact, skip for YAGNI):
- Debounce `_persist()` writes
- Async history file load

## Open questions

- Should "Refresh all" do sequential auto-refresh (currently only triggers first)? Out of scope here.
- Should we expose a "queue this fetch" option so user can click another profile and have it start when the current one finishes? KISS says no — disable controls, user clicks Cancel if they want to switch.

**Status:** DONE
