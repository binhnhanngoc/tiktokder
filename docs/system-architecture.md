# System Architecture

## High-Level Overview

TikTokDer is a dual-interface (GUI + CLI) application for batch-downloading videos from TikTok and Facebook. Both interfaces share common core modules for multi-platform URL validation, downloading, and configuration management.

```
┌─────────────────────────────────────────────────────────┐
│                   User Interface Layer                  │
├──────────────────────┬──────────────────────────────────┤
│   GUI (PySide6)      │   CLI (Argparse + Rich)          │
│   app.py             │   main.py                        │
│   gui/*.py (6 files) │   Single entry point             │
└──────────────────────┴──────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          Business Logic Layer (Shared, Multi-platform)  │
├─────────────────────────────────────────────────────────┤
│  download_engine.py   (orchestration)                   │
│  url_parser.py        (TikTok & Facebook validation)    │
│  downloader.py        (yt-dlp wrapper)                  │
│  channel_fetcher.py   (TikTok metadata)                 │
│  facebook_fetcher.py  (Facebook scraping via Playwright)│
│  config.py            (settings management)             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              External Dependencies                      │
├──────────────────────┬──────────────────────────────────┤
│   yt-dlp             │   Playwright                     │
│   (video extraction) │   (Facebook browser automation)  │
└──────────────────────┴──────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              Persistent Storage                         │
├──────────────────────┬──────────────────────────────────┤
│   Local Filesystem   │   ~/.tiktokder/config.json       │
│   ./downloads/       │   (application settings)         │
│   (video files)      │                                  │
└──────────────────────┴──────────────────────────────────┘
```

## Architectural Layers

### 1. User Interface Layer

#### GUI (PySide6) — v1.4.0 Library 3-Pane + SemVer
- **Entry Point:** `app.py` → `MainWindow`
- **Top-level Layout:**
  1. **GlobalUrlBar** (`gui/global_url_bar.py`) — Persistent QLineEdit + Add button above tabs; drag-drop `.txt` and URLs; emits `urls_submitted(list[str])`
  2. **QTabWidget** (3 tabs):
     - **TikTok Tab** → `PlatformTab(platform="tiktok")`
     - **Facebook Tab** → `PlatformTab(platform="facebook")`
     - **Settings Tab** → `SettingsPanel`
  3. **StatusBarWidget** (`gui/status_bar_widget.py`) — Labels: TT: N | FB: N | Done: N | free-text status

- **PlatformTab Composite** (`gui/platform_tab.py`) — Three sub-tabs per platform:
  1. **Channels Sub-tab** (`gui/saved_channels_panel.py`)
     - Saved channels table (nickname, URL, video count, last-fetched relative time)
     - Embedded browser panel below (TikTokBrowserPanel or FacebookBrowserPanel)
     - Toolbar: Add, Refresh All; right-click: Browse, Refresh, Download all new (confirm >10), Rename+notes, Edit URL, Star, Remove
  2. **Queue Sub-tab** (`gui/download_table.py`)
     - Download queue table per platform (URL, Title, Status, Progress %, File path)
     - Toolbar: Clear Completed, Clear All, Retry Failed, Cancel All
     - Right-click: Open file, Reveal, Copy URL, Retry, Force Download, Clear row
  3. **Library Sub-tab** (`gui/library_panel.py`) (v1.4.0)
     - **3-pane layout:** left uploader sidebar (frequency-sorted, ★ for saved channels), middle sortable/filterable history table with thumbnail column, right preview pane
     - **Middle pane:** Columns (Thumbnail, Title, Quality, Size, Date, Status); **all sortable by header click** (Size numeric, Date chronologic, default Date desc); thumbnail column uses `LibraryThumbnailDelegate`
     - **Right pane:** `LibraryPreviewPane` (cached large thumbnail, metadata form, description QTextEdit)
     - **Advanced filter row:** Quality dropdown, Date From/To (toggleable), Size ≥ MB, Status (Available/Missing), search box (200ms debounce, matches title/uploader/URL/description)
     - Right-click: Open file, Reveal folder, Re-download, Copy URL, Remove from history

- **Browser Panels** (`gui/base_browser_panel.py`, `gui/tiktok_browser_panel.py`, `gui/facebook_browser_panel.py`)
  - Embedded in Channels sub-tab above table
  - URL input + Browse button, video table, Select All/Deselect/Download Selected
  - TikTok: ChannelFetcher integration
  - Facebook: FacebookFetcher + Scrolls spinbox (1–50, default 10) + "Load more" button
  - State snapshots restored on app relaunch

**GUI Data Flow (v1.4.0):**
```
GlobalUrlBar drag-drop or paste URL / .txt file
    ↓
MainWindow._on_urls_submitted() [platform detection]
    ↓
Route to platform tab: PlatformTab.add_urls() or .queue_panel
    ↓
download_engine.add_urls() + .start_downloads() [QThread]
    ↓
DownloadEngine emits progress signals → DownloadTableWidget updates
    ↓
Per-platform queue displays real-time status/progress/size
    ↓
Engine.history_changed → tiktok_tab.library_panel.refresh() + facebook_tab.library_panel.refresh()
    ↓
[Parallel] SavedChannelsPanel can load URL → browser panel (embedded) → user selects → Download Selected → engine queue
```

#### CLI (Rich + Argparse)
- **Entry Point:** `main.py`
- **Argument Parser:** Argparse with 7 CLI options
  - `url` (positional, TikTok or Facebook video URL)
  - `--batch FILE` (mixed-platform URLs, one per line)
  - `--user USERNAME` (TikTok profile scraping)
  - `--facebook-page PAGE_URL` (Facebook page scraping)
  - `--output DIR` (output directory, default ./downloads)
  - `--workers N` (concurrent downloads, default 3)
  - `--delay N` (delay between requests, default 1.0)
- **Progress UI:** Rich progress bar with percentage and elapsed time
- **Error Output:** Rich console with color-coded messages

**CLI Data Flow:**
```
Command-line Arguments
    ↓
parse_args() + validate input mode (mutually exclusive)
    ↓
build_urls() [single, batch file, profile, or page]
    ↓
validate_url() [auto-detect platform per URL]
    ↓
downloader.download_batch() [concurrent ThreadPoolExecutor]
    ↓
Rich Progress Bar [real-time percentage and status]
    ↓
Summary Report [downloaded/failed/skipped counts]
```

### 2. Business Logic Layer (Shared)

#### `url_parser.py` — URL Validation & Parsing
**Responsibilities:**
- Validate TikTok and Facebook video URLs with regex patterns
- Detect platform (TikTok vs. Facebook)
- Detect if URL is a channel/page (vs. single video)
- Extract video IDs from various URL formats
- Parse batch files (remove comments, deduplicate, validate)
- Normalize URLs (handle short links, trailing slashes)

**Key Functions:**
```python
validate_tiktok_url(url: str) -> bool
validate_facebook_url(url: str) -> bool
validate_url(url: str) -> bool
is_channel_url(url: str) -> bool
is_facebook_page_url(url: str) -> bool
is_page_or_channel_url(url: str) -> bool
detect_platform(url: str) -> str | None
extract_video_id(url: str) -> str | None
read_batch_file(path: str) -> list[str]
build_user_url(username: str) -> str
```

**Key Patterns:**
- `TIKTOK_URL_PATTERN` — Matches TikTok videos and profiles
- `CHANNEL_URL_PATTERN` — Matches TikTok channels (no /video/ suffix)
- `FACEBOOK_URL_PATTERN` — Matches Facebook videos (watch, videos, reel, posts, story, short links)
- `FACEBOOK_PAGE_PATTERN` — Matches Facebook pages (no video path suffix)

**Error Handling:**
- Invalid URL → returns False (non-exception)
- Missing batch file → raises FileNotFoundError
- Malformed batch entries → logged, skipped, not raised

#### `downloader.py` — yt-dlp Wrapper & Concurrent Execution
**Responsibilities:**
- Wrap yt-dlp with platform-agnostic extraction options (supports TikTok and Facebook)
- Handle single video downloads with optional progress hooks
- Manage concurrent downloads via ThreadPoolExecutor
- Skip already-downloaded videos (filesystem scan)
- Return structured DownloadResult objects

**Key Functions:**
```python
get_ydl_opts(output_dir: str, quality="best", write_subs=False, write_thumb=True, cookies_file=None) -> dict
# v1.4.0: write_thumb=True always; cookie wiring delegated to yt_dlp_helpers.apply_cookies()
download_video(url: str, output_dir: str, progress_hook: Callable | None = None, cookies_file: str | None = None) -> DownloadResult
download_batch(urls: list[str], output_dir: str, workers: int = 3, delay: float = 1.0, progress_callback: Callable | None = None) -> list[DownloadResult]
get_downloaded_ids(output_dir: str) -> set[str]
```

**Threading Model:**
- ThreadPoolExecutor with configurable worker count (default: 3)
- Each worker downloads one video at a time
- Progress hook called frequently by yt-dlp (high-frequency updates)
- Exceptions caught per-video (batch continues on failure)

#### `download_engine.py` — Unified Orchestration
**Responsibilities:**
- Queue URLs for download
- Manage download lifecycle (start, cancel, pause)
- Emit progress signals/callbacks for GUI integration
- Coordinate with `downloader.py` for actual work
- Run downloads in background thread (GUI responsiveness)

**Key Class:**
```python
class DownloadEngine:
    def add_urls(self, urls: list[str]) -> None
    def start_downloads(self) -> None
    def cancel(self) -> None
    def on_progress(self, callback: Callable) -> None  # Register callback
```

**Threading Model:**
- Runs `downloader.download_batch()` in separate thread
- Emits progress updates to registered callbacks
- GUI calls callbacks on QThread for thread-safe updates
- CLI uses simple blocking calls

#### `channel_fetcher.py` — TikTok Channel Metadata Retrieval (v1.4.0 + cookies.txt)
**Responsibilities:**
- Fetch TikTok channel metadata (followers, bio, video count)
- Retrieve list of videos from TikTok channel
- Extract video IDs, titles, descriptions
- Handle network errors gracefully
- **v1.4.0:** Support Netscape `cookies.txt` via `yt_dlp_helpers.apply_cookies()` (parity with Facebook)

**Key Functions:**
```python
get_channel_videos(channel: str, limit: int = 30, cookies_file: str | None = None) -> list[dict]
get_channel_metadata(channel: str) -> dict | None
```

**Data Format:**
```python
{
    "video_id": "1234567890",
    "title": "Video Title",
    "description": "Optional description",
    "url": "https://www.tiktok.com/@user/video/1234567890"
}
```

#### `facebook_fetcher.py` — Facebook Page Scraping
**Responsibilities:**
- Fetch Facebook page metadata via Playwright browser automation
- Retrieve list of videos from Facebook page
- Extract video IDs, titles, URLs
- Handle authentication and rate limiting

**Key Functions:**
```python
scrape_facebook_page(page_url: str, limit: int = 50, cookies_file: str | None = None) -> list[dict]
get_facebook_page_metadata(page_url: str) -> dict | None
```

**Data Format:**
```python
{
    "video_id": "page_id_timestamp",
    "title": "Post caption or description",
    "url": "https://www.facebook.com/watch/?v=...",
    "upload_date": "2026-03-22"
}
```

**Threading:** Async Playwright browser (headless, auto-closed)

**Cookies Integration (v1.4.0):** Optional Netscape `cookies.txt` lifts 10-reel anonymous cap; uses `facebook_cookies.load_netscape_cookies()` to convert to Playwright cookie dict

#### `config.py` — Settings Persistence
**Responsibilities:**
- Load/save application configuration from JSON
- Provide default values for missing settings
- Validate configuration values on load
- Store window geometry (for GUI persistence)

**Key Class & Functions:**
```python
@dataclass
class AppConfig:
    output_dir: str = "./downloads"
    workers: int = 3
    delay: float = 1.0
    cookie_browser: str | None = None
    window_width: int = 900
    window_height: int = 600
    window_x: int | None = None
    window_y: int | None = None

load_config() -> AppConfig
save_config(config: AppConfig) -> None
```

**Storage Location:**
- Path: `~/.tiktokder/config.json`
- Format: JSON with snake_case keys
- Fallback: Defaults if file missing or corrupted

### 3. External Dependencies

#### yt-dlp (2024.0.0+)
- **Purpose:** Extract TikTok videos without watermarks
- **Integration:** Wrapped in `downloader.py`
- **Configuration:**
  - `noplaylist: True` (single video, not playlist)
  - `quiet: False` (verbose for debugging)
  - `no_warnings: True`
  - Progress hooks for real-time status
  - Format selection for best quality

#### Rich Library (13.0.0+)
- **Purpose:** CLI progress bars and colored output
- **Integration:** Used in `main.py` only
- **Features:**
  - Progress bar with percentage, elapsed time
  - Colored console output (errors, warnings, success)
  - Spinners for loading operations

#### PySide6 (6.6.0+)
- **Purpose:** Desktop GUI framework
- **Integration:** All files in `gui/` package
- **Components:**
  - QMainWindow, QTabWidget for layout
  - QLineEdit, QPushButton for input
  - QTableWidget for download list
  - QSpinBox, QDoubleSpinBox for settings
  - QFileDialog for folder picker

### 4. Persistent Storage

#### Local Filesystem
- **Video Storage:** `./downloads/` (configurable via UI/CLI)
- **File Naming:** `{video_id}_{title}.mp4` (platform-aware tree: `/tiktok/{uploader}/` or `/facebook/{pagename}/`)
- **Facebook Folders (v1.4.0):** Uses page **slug** (URL-safe name) instead of display name for folder hierarchy (e.g., `downloads/facebook/bbc-news/` not `downloads/facebook/BBC News/`)
- **Thumbnails (v1.4.0):** Sidecar `.jpg`/`.webp` always written next to each video; used by Library preview pane
- **Duplicate Detection:** Filesystem scan + history dedup check

#### Configuration File
- **Location:** `~/.tiktokder/config.json`
- **Owner:** `config.py` (load/save functions)
- **Size:** ~0.5KB typical
- **Format:** JSON with flat structure

**Example config.json:**
```json
{
  "output_dir": "./downloads",
  "workers": 3,
  "delay": 1.0,
  "cookie_browser": null,
  "window_width": 900,
  "window_height": 600,
  "window_x": 100,
  "window_y": 100
}
```

#### UI State (v1.3.0)
- **Location:** `data/state.json`
- **Owner:** `app_state.py` (AppState dataclass)
- **Restored on relaunch** by `app.py` and `MainWindow.__init__()`
- **Contains:** Active tab index, channel_active_sub_tab per platform, download_queue snapshot, browser panel state (scrollback, selected channel), full state tolerance (malformed JSON → empty defaults)

**Example state.json:**
```json
{
  "active_tab_index": 0,
  "channel_active_sub_tab": {"tiktok": "channels", "facebook": "library"},
  "download_queue": [{"url": "...", "title": "...", "status": "queued"}],
  "tiktok_browser": {"url": "...", "scroll_position": 1500},
  "facebook_browser": {"url": "...", "scroll_position": 2000}
}
```

#### History Records (schema v3, v1.4.0)
- **Location:** `data/history.json`
- **Owner:** `history_store.py` (v1→v3 migration on first write)
- **FIFO cap:** 10,000 entries; trim oldest metadata (video files untouched)
- **Fields per record:** platform, uploader, video_id, title, quality, size, downloaded_at, file_path, **description, thumbnail_path** (v1.4.0)
- **Description & Thumbnail:** Surfaced in Library preview pane; thumbnails cached via QPixmapCache "large:" prefix

#### Saved Channels (v1.3.0)
- **Location:** `data/saved_channels.json`
- **Owner:** `saved_channels_store.py` (SavedChannelsStore)
- **Scoped:** Per-platform (tiktok, facebook), max 200 each
- **Fields per channel:** url, nickname, note, starred, last_fetched_at, last_fetched_video_ids (for dedup)
- **FIFO trim:** Oldest entries removed if platform cap exceeded

## Data Flow Diagrams

### Single Video Download (GUI)
```
User enters URL (TikTok or Facebook)
    ↓
Click "Download" button
    ↓
url_input_panel.on_download_clicked()
    ↓
validate_url(url) + detect_platform(url) → ('tiktok' or 'facebook')
    ↓
download_engine.add_urls([url])
    ↓
download_engine.start_downloads() [thread spawned]
    ↓
downloader.download_video(url, output_dir, progress_hook=gui_callback)
    ↓
yt_dlp.YoutubeDL().extract_info(url) [platform-agnostic]
    ↓
progress_hook({"status": "downloading", "_percentage_str": "45%", ...})
    ↓
[GUI thread - thread-safe callback]
download_table.update_progress(video_id, status, percent, size)
    ↓
User sees table row update in real-time
    ↓
Download completes (yt-dlp finishes)
    ↓
status_label.setText("Download complete!")
```

### Batch Download (CLI)
```
User runs: python main.py --batch urls.txt --workers 5
    ↓
parse_args() → read_batch_file("urls.txt") [mixed platforms]
    ↓
validate_url() + detect_platform() for each URL
    ↓
get_downloaded_ids(output_dir) → skip already-downloaded
    ↓
downloader.download_batch(urls, workers=5, delay=1.0)
    ↓
ThreadPoolExecutor with 5 workers + delay between starts
    ├─ Worker 1: download_video(tiktok_url)
    ├─ Worker 2: download_video(facebook_url)
    ├─ Worker 3: download_video(tiktok_url)
    ├─ Worker 4: download_video(facebook_url)
    └─ Worker 5: download_video(tiktok_url)
    ↓
Rich Progress Bar [real-time percentage, elapsed time]
    ↓
Batch completes
    ↓
Print summary: "Downloaded 8/10, Failed 1, Skipped 1"
```

### Channel/Page Browse & Download (GUI — v1.3)
```
User enters TikTok channel URL or Facebook page URL in browser panel (Channels sub-tab)
    ↓
Click "Browse" button
    ↓
[Auto-detect platform via url_parser.detect_platform()]
    ├─ TikTok: TikTokBrowserPanel → ChannelFetcher.get_channel_videos()
    └─ Facebook: FacebookBrowserPanel → FacebookFetcher.scrape_facebook_page()
    ↓
Browser panel fetches & populates table (checkbox / title / duration / quality / views / date)
    ↓
User checks videos, clicks "Download Selected"
    ↓
MainWindow routes to platform engine → download_engine.add_urls()
    ↓
download_engine.start_downloads() [QThread spawned]
    ↓
Progress → DownloadTableWidget (Queue sub-tab) updates in real-time
    ↓
Completion → history_store writes records → both library panels refresh
```

### Download All New (Saved Channels — v1.3)
```
User navigates to Channels sub-tab → clicks "Download all new" on saved channel row
    ↓
SavedChannelsPanel._on_download_all_new(channel: SavedChannel)
    ↓
Call saved_channels_store.select_new_videos(channel.url) [dedup filter]
    ↓
→ Returns videos NOT in engine._queued_urls AND NOT in history_ids_resolver AND newer than channel.last_fetched_at
    ↓
If >10 videos, show confirm dialog (counts matching, cached, new)
    ↓
MainWindow → download_engine.add_urls(new_video_urls)
    ↓
Update channel.last_fetched_at + last_fetched_video_ids atomically
    ↓
Engine downloads; history_store writes → library panels refresh (filter shows new records)
```

## Concurrency Model

### Threading Strategy
- **Main Thread:** GUI rendering (PySide6 requirement)
- **Download Thread:** `download_engine` runs `downloader.download_batch()` in QThread
- **Worker Threads:** ThreadPoolExecutor (default 3) for concurrent downloads

### Thread Safety
- **Signal/Slot Pattern:** GUI updates marshaled through Qt signals
- **Queue-Safe Callbacks:** Progress hooks use thread-safe callbacks
- **Config Persistence:** Atomic JSON write on app exit

### Synchronization
```
GUI Thread                  Download Thread
    │                              │
    ├─ ui.download_clicked()       │
    │                    ─────────→│ download_engine.start()
    │                              │
    │                              ├─ ThreadPoolExecutor.map()
    │                              │  [5 yt-dlp processes]
    │                              │
    │ ←─ progress_callback() ──────┤
    │ (thread-safe signal)         │
    │                              │
    ├─ table.update_row()          │
    │                              │
    └─ (repeat for each update)───→└
```

## Error Handling Strategy

### Validation Errors
- **Invalid URL** → `validate_tiktok_url()` returns False (no exception)
- **Missing Batch File** → Caught in `main.py`, user-friendly message

### Network Errors
- **Download Failure** → Caught per-video in `download_batch()`, continues
- **TikTok Blocking** → Increase `--delay` in CLI or UI settings
- **Channel Not Found** → `get_channel_videos()` returns empty list

### System Errors
- **Permission Denied** → Caught on file write, logged with path
- **Disk Full** → yt-dlp exception caught, video marked "Failed"
- **Config Corruption** → Ignored, defaults used, config overwritten on exit

### Error Reporting
- **GUI:** Modal dialogs with "Error" title and actionable message
- **CLI:** Rich console with red "[ERROR]" prefix

## Security & Privacy

### Data Protection
- **No Credentials Stored** — yt-dlp handles auth-free downloads
- **No Tracking** — No external calls beyond TikTok (via yt-dlp)
- **No Cloud Sync** — All data stored locally

### File Security
- **Config File:** Readable by owner only (`~/.tiktokder/config.json`)
- **Downloaded Videos:** Stored in user-specified directory
- **Path Validation:** No directory traversal exploits (paths validated before use)

### Network Security
- **TLS/HTTPS:** yt-dlp handles all TLS validation
- **Rate Limiting:** `--delay` prevents abuse detection

## Performance Characteristics

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| Load config.json | <1ms | Cached in memory |
| Validate URL | <1ms | Regex match |
| Download single video (1-10 MB) | 5-30s | Depends on TikTok server |
| Batch of 10 videos (3 workers) | 20-60s | Concurrent, staggered |
| Channel fetch (30 videos) | 5-10s | API calls, with delay |
| GUI startup | 1-2s | PySide6 initialization |

## Scalability Limits

- **Batch File Size** — Tested up to 10,000+ URLs (linear memory usage)
- **Concurrent Workers** — Recommended max 5-10 (beyond = TikTok rate limiting)
- **Download Queue** — GUI table memory scales with video count (~100 bytes per row)
- **Video Size** — No limit; depends on storage capacity

## Future Architectural Changes

1. **Database Integration** — Replace filesystem duplicate detection with persistent DB
2. **Task Persistence** — Save/restore download queue to survive app restart
3. **Plugin System** — Allow custom video sources (YouTube, Instagram, etc.)
4. **Cloud Storage** — Integration with S3, Google Drive for backup
5. **API Service** — Expose download queue as REST API for external tools
