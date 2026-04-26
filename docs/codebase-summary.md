# TikTokDer Codebase Summary

## Overview

TikTokDer is a dual-interface (GUI + CLI) Python application for batch-downloading TikTok and Facebook videos without watermarks. Organized into three layers: user interface (PySide6 GUI, Rich CLI), shared business logic, and external dependencies (yt-dlp, Playwright).

**Current Statistics (v1.2.0):**
- **Total Python Modules:** 22 (8 core + 1 CLI + 1 GUI + 9 GUI components + 3 extras)
- **Test Coverage:** 257 tests across 7 test files
- **Python Version:** 3.10+
- **External Dependencies:** 6 (yt-dlp, PySide6, Rich, pytest, PyInstaller, Playwright)

### v1.2.0 additions
- `history_store.py` — schema-v2 history persistence with v1 auto-migration, atomic writes, FIFO cap.
- `path_builder.py` — pure helpers for slugify + platform/uploader-aware yt-dlp `outtmpl`.
- `gui/history_tab.py` — 4th top-level tab with rich record list, search, platform filter, stats, context menu.
- `gui/download_tab.py` — wraps URL input + queue table; owns drag-drop + Import/Export.
- `gui/base_browser_panel.py`, `gui/tiktok_browser_panel.py`, `gui/facebook_browser_panel.py` — replaces monolithic `channel_browser.py` with a thin `QTabWidget` wrapper + per-platform sub-panels.
- `test_history_records.py`, `test_path_builder.py`, `test_engine_history_integration.py` — ~50 new tests.

## Module Inventory

### Core Modules (Shared Logic)

#### 1. `url_parser.py`
**Purpose:** URL validation, parsing, and batch file handling
**Key Exports:**
- `validate_tiktok_url(url: str) -> bool` — Validates TikTok video URLs using regex
- `is_channel_url(url: str) -> bool` — Detects if URL points to a channel
- `extract_video_id(url: str) -> str | None` — Extracts video ID from various URL formats
- `read_batch_file(path: str) -> list[str]` — Parses batch file (removes comments, normalizes)
- `build_user_url(username: str) -> str` — Constructs user profile URL

**Test Coverage:** `test_tiktokder.py` (15+ tests)

#### 2. `downloader.py`
**Purpose:** yt-dlp wrapper and concurrent download orchestration
**Key Exports:**
- `get_ydl_opts(output_dir, cookie_browser=None, retries=10) -> dict` — Builds yt-dlp configuration with platform-aware retries, `extractor_retries`, `fragment_retries`, `sleep_interval(_requests)`, and per-layer `retry_sleep_functions`
- `download_video(url, output_dir, progress_hook=None, cookie_browser=None, retries=None, max_attempts=None) -> DownloadResult` — Wraps inner `_do_download` with tenacity outer retry; raises typed exceptions internally, returns `DownloadResult` to callers
- `download_batch(urls, output_dir, workers=3, delay=1.0, skip_ids=None, delay_std=None, delay_floor=None) -> list[DownloadResult]` — Concurrent downloads with gaussian-jittered, per-platform pacing
- `get_downloaded_ids(output_dir) -> set[str]` — Scans output for already-downloaded video IDs
- Internal helpers: `_jittered_sleep`, `_classify_error`, `_kind_to_exception`, `_exception_to_kind`, `_friendly_error`, `_do_download`

**Key Classes:**
- `DownloadResult` (dataclass) — `url`, `success`, `video_id`, `title`, `error`, `skipped`. `error` is now a typed kind string (`"login_required"`, `"rate_limited"`, etc.) for known classes, raw message otherwise.

**Test Coverage:** `test_tiktokder.py` (35+ tests)

#### 3. `download_engine.py`
**Purpose:** Unified download orchestration for both GUI and CLI
**Key Exports:**
- `DownloadEngine` class with methods:
  - `add_urls(urls: list[str])` — Queue URLs for download
  - `start_downloads()` — Begin concurrent processing in background thread
  - `cancel()` — Stop all pending downloads
  - `on_progress(callback: Callable)` — Register progress callback
  - `get_status()` → dict — Return current queue status

**Thread Model:** Runs downloads in separate thread to prevent UI blocking

**Test Coverage:** `test_download_engine.py` (25+ tests)

#### 4. `channel_fetcher.py`
**Purpose:** Retrieve TikTok channel and Facebook page metadata and video lists
**Key Exports:**
- `get_channel_videos(channel: str, limit: int = 30) -> list[dict]` — Fetch videos from TikTok channel or Facebook page
- `get_channel_metadata(channel: str) -> dict | None` — Get channel/page info (followers, bio, video count)

**Returns:** List of dicts with keys: `video_id`, `title`, `description`, `url`

**Test Coverage:** `test_channel_fetcher.py` (15+ tests)

#### 5. `facebook_fetcher.py` (NEW)
**Purpose:** Playwright-based Facebook page scraping for video discovery
**Key Exports:**
- `scrape_facebook_page(page_url: str, limit: int = 50) -> list[dict]` — Extract videos from Facebook page
- `get_facebook_page_metadata(page_url: str) -> dict | None` — Retrieve page info

**Returns:** List of dicts with: `video_id`, `title`, `url`, `upload_date`

**Dependencies:** Playwright (headless browser automation)

**Notes:** Headless browser required; may trigger rate limiting

#### 6. `config.py`
**Purpose:** Application settings persistence and per-platform resilience presets
**Key Exports:**
- `AppConfig` (dataclass) — output_dir, workers, delay, cookie_browser, window geometry
- `PlatformDefaults` (frozen dataclass) — `delay_mean`, `delay_std`, `delay_floor`, `workers`, `retries`
- Module constants:
  - `TIKTOK_DEFAULTS = PlatformDefaults(1.5, 0.5, 0.2, 3, 10)`
  - `FACEBOOK_DEFAULTS = PlatformDefaults(3.0, 1.5, 0.5, 1, 2)`
  - `MAX_RETRY_ATTEMPTS_TIKTOK = 3`, `MAX_RETRY_ATTEMPTS_FACEBOOK = 2` (tenacity outer)
  - `FB_LOGIN_WALL_MARKERS` — tuple of HTML markers for login-wall detection
- `get_platform_defaults(url) -> PlatformDefaults` — fallback to TikTok defaults
- `get_max_retry_attempts(url) -> int` — tenacity outer-layer attempts per platform
- `load_config() / save_config()`, `load_history() / save_history()`

**Storage:** `~/.tiktokder/config.json` (readable/writable by owner)

**Test Coverage:** `test_config.py` (30+ tests)

#### 6a. `retry_policy.py` (NEW)
**Purpose:** Tenacity-based outer retry layer with typed exceptions and Retry-After awareness
**Key Exports:**
- Exceptions: `LoginRequired`, `Private`, `NotFound`, `RateLimited(retry_after)`, `TransientFailure`, `PermanentFailure`
- `parse_retry_after(msg) -> float | None` — extracts `Retry-After: N` from error messages
- `decorrelated_jitter(base=2.0, cap=60.0)` — AWS-style jitter wait function factory
- `retry_after_aware_wait(base=2.0, cap=60.0)` — honors `RateLimited.retry_after`, falls back to decorrelated jitter
- `with_retry(max_attempts=3, base=2.0, cap=60.0)` — composed tenacity decorator
- `_is_retryable(exc) -> bool` — True only for `RateLimited`/`TransientFailure`

**Test Coverage:** `test_retry_policy.py` (~17 tests)

#### 6b. `facebook_resolver.py` (NEW)
**Purpose:** Pre-resolve `fb.watch` shortlinks via curl_cffi to fast-fail login walls
**Key Exports:**
- `is_fb_shortlink(url) -> bool` — matches `fb.watch/...`
- `resolve_fb_shortlink(url, timeout=5.0) -> tuple[canonical_url, status]` — returns `"login_required"`, `"ok"`, or `"unknown"` (fail-open)

**Behavior:** One-hop HEAD/GET via `curl_cffi.requests.Session(impersonate="chrome131")`, scans 3xx Location and 200 body (50KB cap) for FB login markers. Reuses `FB_LOGIN_WALL_MARKERS` from `config`.

**Test Coverage:** `test_facebook_resolver.py` (~12 tests, all mocked HTTP)

### Entry Points

#### 7. `app.py`
**Purpose:** PySide6 desktop GUI entry point
**Key Function:**
- `main() -> None` — Initializes QApplication, loads config, creates MainWindow, handles window geometry persistence on exit

**Usage:** `python app.py`

#### 8. `main.py`
**Purpose:** CLI entry point with argparse interface
**Key Function:**
- `main() -> None` — Parses arguments, validates input mode, orchestrates downloads, displays progress

**CLI Arguments:**
- `url` (positional) — Single TikTok or Facebook video URL
- `--batch FILE` — Path to text file with mixed URLs (one per line)
- `--user USERNAME` — TikTok username for profile scraping
- `--facebook-page URL` — Facebook page URL for scraping
- `--output DIR` — Output directory (default: `./downloads`)
- `--workers N` — Concurrent downloads (default: 3 for TikTok, 1 for Facebook — derived from URL when omitted)
- `--delay N` — Mean delay between downloads in seconds, gaussian-jittered (default: 1.5 TikTok, 3.0 Facebook)

**Usage:** `python main.py <url|--batch FILE|--user USERNAME|--facebook-page URL> [options]`

### GUI Package (`gui/`)

#### 9. `gui/main_window.py`
**Purpose:** Main application window with tab-based interface
**Key Class:**
- `MainWindow(QMainWindow)` — Top-level window container
  - Initializes QTabWidget with 3 tabs
  - Manages window geometry persistence
  - Coordinates between tabs and download engine

**Tabs (v1.2.0):**
1. **Download** — `DownloadTab` wrapper (URL input + queue table + drag-drop + Import/Export)
2. **Channel / Page** — `ChannelBrowser` (QTabWidget with TikTok and Facebook sub-panels, each with own URL input + Quality column)
3. **History** — `HistoryTab` (rich-record list with search, platform filter, stats, right-click actions)
4. **Settings** — `SettingsPanel` (now also: Default Quality combo, Write subtitles toggle, Write thumbnail toggle)

#### 10. `gui/url_input_panel.py`
**Purpose:** Single URL input and download controls
**Key Class:**
- `UrlInputPanel(QWidget)` — Provides:
  - QLineEdit for URL input (TikTok or Facebook)
  - QPushButton for download action
  - QLabel for status display
  - Integration with `download_engine`
  - Detects channels via `is_channel_url()` and routes appropriately

#### 11. `gui/download_table.py`
**Purpose:** Real-time download queue and progress display
**Key Class:**
- `DownloadTable(QTableWidget)` — Displays:
  - Video ID, Title, Status, Progress (%), Size
  - Updates from download_engine progress callbacks
  - Supports selection and clearing

#### 12. `gui/channel_browser.py`
**Purpose:** Channel/page discovery and video browsing interface
**Key Class:**
- `ChannelBrowser(QWidget)` — Provides:
  - QLineEdit for TikTok channel or Facebook page name input
  - "Search Channel" button triggering `channel_fetcher` or `facebook_fetcher`
  - QTableWidget displaying video list
  - "Download Selected" button for batch queuing

#### 13. `gui/settings_panel.py`
**Purpose:** Application configuration interface
**Key Class:**
- `SettingsPanel(QWidget)` — Provides:
  - QFileDialog for output directory selection
  - QSpinBox for workers (1-10)
  - QDoubleSpinBox for delay (0.1-10.0)
  - Save button persisting to config.json
  - Load button refreshing from config

## Test Infrastructure

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_tiktokder.py` | 67 | url_parser, downloader basics, main.py integration |
| `test_config.py` | 12 | config load/save, defaults, corruption handling |
| `test_download_engine.py` | 13 | download orchestration, threading, cancellation |
| `test_channel_fetcher.py` | 12 | channel metadata, video list retrieval |
| **Total** | **104** | **Core + new modules** |

### Test Framework
- **Runner:** pytest 7.0.0+
- **Command:** `pytest test_*.py -v`
- **Mocking:** unittest.mock for network calls
- **Fixtures:** Temporary directories for config/download testing

## Dependency Tree

```
app.py
├── PySide6.QtWidgets
│   └── config.py (load_config)
│   └── gui/main_window.py
│       ├── gui/url_input_panel.py
│       │   ├── url_parser.py (validate_tiktok_url, is_channel_url)
│       │   └── download_engine.py
│       │       └── downloader.py
│       │           └── yt-dlp
│       ├── gui/download_table.py
│       ├── gui/channel_browser.py
│       │   ├── channel_fetcher.py
│       │   │   └── yt-dlp
│       │   └── download_engine.py
│       └── gui/settings_panel.py
│           ├── config.py
│           └── pathlib.Path

main.py
├── argparse
├── url_parser.py
├── downloader.py
│   └── yt-dlp
├── Rich (progress bars, console)
└── config.py (optional, for defaults)
```

## Configuration

### Default Settings
- **Output Directory:** `./downloads`
- **Concurrent Workers:** 3
- **Request Delay:** 1.0 second
- **Window Size:** 900x600 pixels
- **Window Position:** Centered on screen

### Configuration File
**Location:** `~/.tiktokder/config.json`
**Format:** JSON
**Scope:** Application-wide (shared between GUI and CLI)

## API Contracts

### URL Validation
```python
# Returns True for valid TikTok video URLs
validate_tiktok_url("https://www.tiktok.com/@user/video/1234567890")  # True
validate_tiktok_url("https://vt.tiktok.com/XXXXXX")  # True
validate_tiktok_url("https://youtube.com/watch?v=...")  # False

# New: Detect if URL is a channel
is_channel_url("https://www.tiktok.com/@username")  # True
is_channel_url("https://www.tiktok.com/@user/video/1234567890")  # False
```

### Download Results
```python
# DownloadResult tuple: (url, success, message, filename, size)
result = download_video(url, output_dir)
if result.success:
    print(f"Downloaded {result.filename} ({result.size} bytes)")
else:
    print(f"Failed: {result.message}")
```

### Progress Hook (New)
```python
# Callbacks receive yt-dlp progress dicts
def progress_hook(info: dict):
    if info['status'] == 'downloading':
        print(f"Progress: {info['_percentage_str']}")
    elif info['status'] == 'finished':
        print(f"Downloaded: {info['filename']}")

download_video(url, output_dir, progress_hook=progress_hook)
```

### Channel Fetcher
```python
# Returns list of video metadata dicts
videos = get_channel_videos("@username", limit=30)
for video in videos:
    print(f"{video['video_id']}: {video['title']}")
```

## Key Improvements (v1.1.0)

1. **Facebook Support** — Multi-platform downloads with automatic detection
2. **Playwright Integration** — Headless browser-based Facebook page scraping
3. **PySide6 Desktop GUI** — Full graphical interface with 3 tabs
4. **Channel/Page Browser** — Discover and download from TikTok channels or Facebook pages
5. **Configuration UI** — Settings panel for output dir, workers, delay
6. **Progress Hooks** — Real-time callbacks for GUI progress updates
7. **download_engine.py** — Unified orchestration for GUI and CLI
8. **Test Expansion** — 104+ tests covering all modules
9. **Mixed-platform Batches** — Single batch file with TikTok and Facebook URLs
10. **JSON Config** — Persistent settings in ~/.tiktokder/config.json

## Known Limitations

1. **Channel Scraping:** Depends on yt-dlp capability; may be rate-limited by TikTok
2. **Error Recovery:** Failed downloads not retried automatically
3. **Persistence:** Download queue not saved if app crashes mid-operation
4. **Authentication:** Cannot use cookie-based authentication (feature placeholder)

## Build & Packaging

### PyInstaller Support
- **Spec File:** Available for standalone executable generation
- **Command:** `pyinstaller --onefile tiktokder.spec`
- **Output:** Single executable bundling Python, dependencies, and code

## Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| App Startup (GUI) | <2s | ~1.5s |
| URL Validation | <1ms | <1ms |
| Batch Parse (1000 URLs) | <100ms | ~50ms |
| Single Download (5MB video) | 10-30s | Varies by server |
| Concurrent 5 Videos (3 workers) | 30-60s | Staggered start |

## Future Enhancements

- [ ] Database for persistent download history
- [ ] Advanced filtering by date, engagement metrics
- [ ] Dark/light theme support in GUI
- [ ] Scheduled batch downloads
- [ ] Webhook notifications on completion
- [ ] Direct S3/cloud storage integration
- [ ] REST API server mode
