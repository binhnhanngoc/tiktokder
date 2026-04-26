# TikTokDer Codebase Summary

## Overview

TikTokDer is a dual-interface (GUI + CLI) Python application for batch-downloading TikTok and Facebook videos without watermarks. Organized into three layers: user interface (PySide6 GUI, Rich CLI), shared business logic, and external dependencies (yt-dlp, Playwright).

**Current Statistics (v1.3.0):**
- **Total Python Modules:** ~28 (core + GUI components + new v1.3 modules)
- **Total LOC:** ~5350 (root: ~2650, GUI: ~2700)
- **Test Coverage:** 326+ tests across 4 test files
- **Python Version:** 3.10+
- **External Dependencies:** 8+ (yt-dlp, PySide6, Rich, pytest, PyInstaller, Playwright, tenacity, curl_cffi, qtawesome, pyqtdarktheme, darkdetect)

### v1.3.0 additions (platform-first UI restructure)
- `saved_channels_store.py` — schema-v1 saved-channels persistence (`data/saved_channels.json`); CRUD, atomic write, tolerant load, cap-200/platform with FIFO trim, `select_new_videos` filter for "Download all new". 19 tests.
- `gui/platform_tab.py` — composite per-platform widget hosting Channels / Queue / Library sub-tabs; drag-drop filtered to own platform.
- `gui/saved_channels_panel.py` — saved-channel list + browser-below for one platform; right-click CRUD, "Download all new" with confirm dialog (>10 videos).
- `gui/library_panel.py` — two-pane Library (uploader sidebar + filtered history table); ★ marks uploaders with saved channels; right-click open/folder/redownload/copy/remove.
- `gui/global_url_bar.py` — persistent URL bar above tabs, drag-drop + paste; auto-routes by `detect_platform`.
- `gui/status_bar_widget.py` — TT/FB/Done/free-text badges in status bar.
- `gui/_history_helpers.py` — extracted `format_size`, `format_date`, `open_path`, `reveal_in_file_manager` from legacy `history_tab.py`.

### v1.3.0 removals
- `gui/channel_browser.py`, `gui/download_tab.py`, `gui/history_tab.py`, `gui/url_input_panel.py` — superseded by platform tabs + global URL bar + library panel.

### v1.2.0 additions
- `app_state.py` — UI state persistence (Download queue + Channel/Page browse snapshots) in `data/state.json`. Tolerant load.
- `history_store.py` — schema-v2 history persistence with v1 auto-migration, atomic writes, FIFO cap.
- `path_builder.py` — pure helpers for slugify + platform/uploader-aware yt-dlp `outtmpl`.
- `gui/base_browser_panel.py`, `gui/tiktok_browser_panel.py`, `gui/facebook_browser_panel.py` — per-platform sub-panels.

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

**Tabs (v1.3.0):**
1. **TikTok** — `PlatformTab(platform="tiktok")` with Channels (`SavedChannelsPanel` + `TikTokBrowserPanel`) / Queue (`DownloadTableWidget`) / Library (`LibraryPanel`) sub-tabs.
2. **Facebook** — `PlatformTab(platform="facebook")` with the same composite, FB browser panel inside Channels.
3. **Settings** — `SettingsPanel` with Global / TikTok / Facebook QGroupBoxes.

A persistent `GlobalUrlBar` sits above the tab widget; a `StatusBarWidget` shows per-platform queue + done badges in the QMainWindow status bar.

#### 10. `gui/global_url_bar.py`
**Purpose:** Persistent URL bar above all tabs.
**Key Class:** `GlobalUrlBar(QWidget)` — QLineEdit + Add button, drag-drop, validates and emits `urls_submitted: list[str]` (mixed-platform). MainWindow groups by `detect_platform` and dispatches.

#### 11. `gui/download_table.py`
**Purpose:** Per-platform download queue table (one instance per `PlatformTab.queue_panel`).
**Key Class:** `DownloadTableWidget(QWidget)` — Title / Status / Progress / Size columns; right-click for Open/Copy/Retry/Force; toolbar with Clear Completed / Clear All / Retry Failed / Cancel All.

#### 12. `gui/platform_tab.py` + `gui/saved_channels_panel.py` + `gui/library_panel.py`
**Purpose:** Composite per-platform widget and its sub-panels.
**Key Classes:**
- `PlatformTab(platform, browser_panel, store, store_path)` — three-sub-tab QTabWidget (Channels / Queue / Library); drag-drop filtered to own platform.
- `SavedChannelsPanel` — saved-channel list above an injected browser panel; right-click for Browse/Refresh, Download all new (confirm dialog >10), Rename + notes, Edit URL, Star/Unstar, Remove.
- `LibraryPanel` — two-pane uploader sidebar + filtered history table; ★ marks uploaders with saved channels; right-click for Open file / Open folder / Re-download / Copy URL / Remove. **All columns sortable by header click** (Size numeric, default Date desc). **Compact filter row**: Quality dropdown, From/To date pickers (toggleable), Size ≥ MB threshold, Status (Available/Missing via `os.path.exists`). All filters share 200ms debounce with search box.

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
│   └── config.py (load_config, AppConfig)
│   └── gui/main_window.py
│       ├── gui/global_url_bar.py
│       │   └── url_parser.py (validate_url, detect_platform, read_batch_file)
│       ├── gui/status_bar_widget.py
│       ├── gui/platform_tab.py
│       │   ├── gui/saved_channels_panel.py
│       │   │   ├── saved_channels_store.py
│       │   │   └── url_parser.py
│       │   ├── gui/download_table.py
│       │   └── gui/library_panel.py
│       │       ├── gui/_history_helpers.py
│       │       └── history_store.py
│       ├── gui/tiktok_browser_panel.py / gui/facebook_browser_panel.py
│       │   ├── channel_fetcher.py / facebook_fetcher.py
│       │   │   └── yt-dlp / Playwright
│       │   └── gui/base_browser_panel.py
│       ├── download_engine.py
│       │   └── downloader.py
│       │       └── yt-dlp
│       └── gui/settings_panel.py
│           └── config.py

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

## Key Improvements (v1.3.0)

1. **Platform-First UI Restructure** — Top-level TikTok / Facebook tabs, each with Channels / Queue / Library sub-tabs; centralizes per-platform workflows
2. **Global URL Bar** — Persistent drag-drop + paste above tabs; auto-routes URLs by platform; supports `.txt` batch import
3. **Saved Channels Management** — CRUD bookmarks with starred/nicknames; "Download all new" filters cached videos against download history + timestamp cutoff
4. **UI State Persistence** — `AppState` snapshots active tab, browser scrollback, queue onto `data/state.json`; restores on relaunch (Tier-1 UX improvement)
5. **Enhanced Library Panel** — Two-pane uploader sidebar (frequency-sorted, ★ for saved) + right-pane history table with search; right-click (Open/Reveal/Re-download/Copy URL/Remove)
6. **Facebook Cookies Injection** — yt-dlp + Playwright both accept `cookies.txt` (Netscape format) to lift anonymous 10-reel scrape cap
7. **Dark Theme Bootstrap** — OS dark-mode listener + pyqtdarktheme integration (Accent #4F46E5); live theme swap via Settings
8. **Per-Platform Browser Panels** — BaseBrowserPanel base + TikTokBrowserPanel (ChannelFetcher) + FacebookBrowserPanel (FacebookFetcher + Scrolls spinbox + "Load more"); state snapshots per tab
9. **Tenacity Retry Layer** — Typed exceptions (LoginRequired, RateLimited, Private, NotFound) + Retry-After awareness; curl_cffi pre-resolver for fb.watch → fast-fail login walls
10. **Test Expansion** — 326+ tests; new test files for app_state, saved_channels_store, retry_policy, facebook_resolver
11. **Status Bar Badges** — Per-platform queue counts (TT / FB / Done) + free-text status indicator
12. **Modular UI Components** — _history_helpers.py, tokens.py, spacing.py, icons.py for reusable design system

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
