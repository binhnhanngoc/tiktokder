# GUI Usage Guide (v1.3.0)

## Launching the GUI

```bash
python app.py
```

TikTokDer opens with a **platform-first** interface: separate tabs for TikTok and Facebook, each with Channels / Queue / Library sub-tabs. A persistent URL bar above the tabs centralizes pasting and batch import.

## Interface Overview

### Main Window Layout
- **Top:** Global URL Bar (drag-drop, paste, import `.txt`)
- **Center:** QTabWidget with 3 top-level tabs:
  1. **TikTok Tab** → Platform-specific Channels / Queue / Library
  2. **Facebook Tab** → Platform-specific Channels / Queue / Library
  3. **Settings Tab** → Global / TikTok / Facebook groups
- **Bottom:** Status Bar (TT count | FB count | Done count | free-text status)
- **Window Persistence:** Position and size saved on close (default: 900x600)

## Global URL Bar

The QLineEdit at the top accepts URLs, batch files, or mixed drag-drop.

**Usage:**
1. Paste a TikTok or Facebook URL → press Enter or click **Add**
2. Or drag a `.txt` file with one URL per line (comments start with `#`)
3. System auto-detects platform and routes to matching tab's Queue

**Supported Formats:**
- TikTok: `https://www.tiktok.com/@user/video/1234567890` or `https://vt.tiktok.com/XXXXXX`
- Facebook: `https://www.facebook.com/watch/?v=1234567890` or `https://www.facebook.com/reel/1234567890`
- Batch files: Plain text, one URL per line, `#` comments ignored

**Tip:** Invalid URLs are silently dropped (consistent with batch parsing).

## TikTok Tab (& Facebook Tab)

Each platform tab has **3 sub-tabs** with identical layout and features (adapted to platform).

### Sub-tab 1: Channels

Save and manage your favorite TikTok channels or Facebook pages.

**Features:**
- **Saved Channels Table** — List of bookmarks (nickname, URL, video count, last-fetched date)
- **Embedded Browser** — Preview channel/page; fetch video list
- **Right-click Actions:**
  - **Browse** → Load channel URL into browser panel below
  - **Refresh** → Re-fetch video list from this channel
  - **Download all new** → Auto-filter new videos (not in history, not already queued, newer than last-fetch time) → confirm dialog if >10 videos
  - **Rename + notes** → Update nickname and optional note
  - **Edit URL** → Change channel/page URL with validation
  - **Star** → Toggle starred status (★ indicator)
  - **Remove** → Delete bookmark

**Embedded Browser Panel:**
- **URL Input** with Browse button
- **Video Table** (checkbox, title, duration, quality, views, upload date)
- **Controls:** Select All / Deselect / Download Selected buttons
- **TikTok:** Fetches via ChannelFetcher (yt-dlp flat-playlist)
- **Facebook:** Fetches via FacebookFetcher (Playwright headless browser)
  - **Scrolls spinbox** (1–50, default 10) — how many times to scroll to load more videos
  - **Load more button** — resume Playwright scrape (useful if interrupted)
- **State snapshot:** Browser URL and scroll position saved on app close → restored on relaunch

### Sub-tab 2: Queue

Per-platform download queue with real-time progress.

**Table Columns:**
- Checkbox (for multi-select actions)
- URL
- Title (extracted from metadata)
- Status (Queued / Downloading / Complete / Failed / Skipped / Cancelled)
- Progress % (0–100)
- File path (once downloaded)

**Toolbar Actions:**
- **Clear Completed** — Remove Complete/Skipped rows only
- **Clear All** — Remove all rows (confirm dialog); resets engine dedup, so URLs can re-queue
- **Retry Failed** — Re-queue all Failed rows in one click
- **Cancel All** — Stop active downloads and clear pending queue

**Right-click Actions:**
- **Open file** — Launch downloaded video in default player
- **Reveal** — Show file in File Explorer (Windows), Finder (macOS), or file manager (Linux)
- **Retry** — Re-queue a single Failed video immediately
- **Force Download** — Re-download even if already on disk (ignores dedup)
- **Copy URL** — Copy video URL to clipboard
- **Clear row** — Remove from queue (does NOT delete file)

### Sub-tab 3: Library

Per-platform download history with uploader sidebar and search.

**Two-Pane Layout:**
- **Left pane:** Uploader sidebar
  - List of uploaders (TikTok creators or Facebook pages) sorted by frequency
  - ★ indicator for uploaders with saved channels
  - Click to filter right pane to that uploader
- **Right pane:** History table
  - Title, Quality, Size, Date (download timestamp), File path
  - Search box (200ms debounce) filters by title or uploader
  - Stats label (total videos, total size, date range)

**Right-click Actions:**
- **Open file** → Launch video in default player
- **Open folder** → Show parent directory in file manager
- **Re-download** → Add URL back to Queue with `force=True` flag
- **Copy URL** → Clipboard copy
- **Remove** → Delete from history (file untouched)

**Filtering:**
- By uploader (click sidebar)
- By search term (case-insensitive)
- Platform-scoped (TikTok tab shows TikTok videos, Facebook tab shows Facebook videos)

## Settings Tab

Configure application behavior. Changes apply immediately.

### Global Section
| Setting | Options | Default | Notes |
|---------|---------|---------|-------|
| **Appearance** | System / Light / Dark | System | OS dark-mode listener active; changes apply live |
| **Output Directory** | path picker | `./downloads` | Per-uploader subfolders auto-created |
| **Concurrent Downloads** | 1–10 | 3 | Platform-aware pacing on top (TT: 3, FB: 1 recommended) |
| **Delay (seconds)** | 0.0–10.0 | 1.0 | Gaussian jitter per platform (TT: 1.5s mean, FB: 3.0s mean) |
| **Default Quality** | Best / 1080p / 720p / 480p / Audio only | Best | Audio-only requires ffmpeg; writes `.m4a` |
| **Write Subtitles** | on / off | off | Downloads `.srt` sidecar (English) |
| **Write Thumbnail** | on / off | off | Downloads `.jpg` sidecar |

### TikTok Section
| Setting | Options | Notes |
|---------|---------|-------|
| **Cookie Browser** | None / Chrome / Firefox / Edge | Auto-extracts session from your browser |

### Facebook Section
| Setting | Options | Notes |
|---------|---------|-------|
| **Cookies File** | path to `cookies.txt` | Netscape format; lifts 10-reel anonymous cap. Export with *Get cookies.txt LOCALLY* extension |
| **Default Max Scrolls** | 1–50 | Scroll budget for Channels browser (Facebook tab) |

**Tip:** All settings auto-save and sync between GUI and CLI via `~/.tiktokder/config.json`.

## Download Progress & Status

### Real-time Updates
- **Status Bar** (bottom right) shows per-platform queue counts + "Done: N"
- **Queue sub-tab table** updates as downloads start/progress/complete
- **Progress bar** per row (if available from yt-dlp)
- **File size** populated once known

### Completion
- **Complete** → Video saved to disk; path visible in table
- **Skipped** → Already on disk (dedup detected)
- **Failed** → Network/permission error; error message in status column
- **Cancelled** → User clicked Cancel All or closed app

## Keyboard Shortcuts

- **Ctrl+Q** → Quit
- **Tab** → Switch between top-level tabs (TikTok / Facebook / Settings)
- **Enter** (in URL bar) → Submit URL
- **Ctrl+F** (in Library tab) → Focus search box

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid URL | Malformed or non-TikTok/Facebook URL | Verify URL format and try again |
| Network Error | Connection failure or TikTok/Facebook blocking | Increase Delay in Settings; wait and retry |
| Permission Denied | Output directory not writable | Check folder permissions; change Output Directory in Settings |
| Duplicate Download | Video already on disk | Right-click row → Force Download to re-download; or delete file and retry |
| Login Required | Facebook login wall (for page videos) | Add `cookies.txt` in Settings (Facebook section) from logged-in session |

## Persistence & State Recovery

On app close:
- Window geometry (size, position) saved to `~/.tiktokder/config.json`
- **UI state** (active tab, browser URL, scroll position) saved to `data/state.json`
- **Configuration** (workers, delay, output dir, theme) persisted
- **Download queue snapshot** included in state (restored on relaunch)

On app start:
- Window opens at previously saved position/size
- Active tab restored (TikTok / Facebook / Settings)
- Channels browser reloads previous channel (if any)
- Queue sub-tab shows pending downloads from last session
- Library history fully restored

## Tips & Troubleshooting

**Rate Limiting:**
- If TikTok/Facebook blocks: Increase **Delay** to 2.0–3.0 seconds in Settings
- Reduce **Concurrent Downloads** to 1–2 if issues persist
- Wait 1–2 hours before retrying

**Performance:**
- **Workers: 3** is safe and balanced; 5+ may trigger rate limits
- **Delay: 1.5s** (TikTok default) is reliable; adjust for your network
- Single video download typically 5–30s (depends on server)

**File Management:**
- Output directory auto-creates per-uploader subfolders: `downloads/tiktok/@user/` or `downloads/facebook/pagename/`
- Filenames: `{video_id}_{title}.{ext}` (legacy flat-root files recognized for dedup)
- Duplicate detection is filesystem + history based (no re-downloads of known IDs)

**Saved Channels:**
- Star channels you download from frequently (helps with Library sidebar)
- "Download all new" auto-filters videos already in history and queue
- Last-fetch timestamp tracks when you last refreshed; filters by this date

**Browser State:**
- Scroll position saved per tab (Channels sub-tab restores on relaunch)
- If Playwright hangs, close Channels browser or use Load more button to resume
- Facebook Scrolls spinbox controls max scroll depth (higher = more videos, slower fetch)
