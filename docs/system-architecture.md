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

#### GUI (PySide6)
- **Entry Point:** `app.py`
- **Main Window:** `gui/main_window.py` (QMainWindow with QTabWidget)
- **Tabs:**
  1. **URL Input Panel** (`gui/url_input_panel.py`)
     - Input field for single TikTok URLs
     - Download button triggering `download_engine`
     - Status label showing operation feedback
  2. **Channel Browser** (`gui/channel_browser.py`)
     - Channel name search field
     - Video list table populated by `channel_fetcher`
     - Batch download of selected videos
  3. **Settings Panel** (`gui/settings_panel.py`)
     - Output directory picker
     - Workers spinbox (1-10)
     - Delay spinbox (0.1-10.0 seconds)
     - Save button persisting to config.json

- **Download Progress Display** (`gui/download_table.py`)
  - QTableWidget showing all downloads
  - Columns: Video ID, Title, Status, Progress %, Size
  - Real-time updates via `download_engine` callbacks

**GUI Data Flow:**
```
User Input (URL, Channel, Settings)
    ↓
URL Input Panel / Channel/Page Browser / Settings Panel
    ↓
download_engine.add_urls() + download_engine.start_downloads()
    ↓
[Auto-detect platform: TikTok or Facebook]
    ↓
Progress Callback (thread-safe for GUI updates)
    ↓
Download Table Widget (real-time status, progress %, file size)
    ↓
Status Label (completion notification)
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
get_ydl_opts(output_dir: str) -> dict
download_video(url: str, output_dir: str, progress_hook: Callable | None = None) -> DownloadResult
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

#### `channel_fetcher.py` — TikTok Channel Metadata Retrieval
**Responsibilities:**
- Fetch TikTok channel metadata (followers, bio, video count)
- Retrieve list of videos from TikTok channel
- Extract video IDs, titles, descriptions
- Handle network errors gracefully

**Key Functions:**
```python
get_channel_videos(channel: str, limit: int = 30) -> list[dict]
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
scrape_facebook_page(page_url: str, limit: int = 50) -> list[dict]
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
- **File Naming:** `{video_id}_{title}.mp4`
- **Duplicate Detection:** Based on filename scan (video_id extraction)

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

### Channel/Page Browse & Download (GUI)
```
User enters TikTok channel or Facebook page name
    ↓
Click "Search Channel" button
    ↓
channel_browser.on_search_clicked()
    ↓
[Auto-detect platform via URL pattern]
    ├─ TikTok: channel_fetcher.get_channel_videos("@channel")
    └─ Facebook: facebook_fetcher.scrape_facebook_page("facebook.com/page")
    ↓
Populate table with video list (ID, title, description)
    ↓
User selects 5 videos and clicks "Download Selected"
    ↓
Collect URLs from selected rows
    ↓
download_engine.add_urls(urls)
    ↓
download_engine.start_downloads() [thread spawned]
    ↓
[Same as single video flow, but with 5 videos in parallel]
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
