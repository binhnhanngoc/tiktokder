# TikTok Batch Video Downloader - Project Overview & PDR

## Project Definition

**Name:** TikTok & Facebook Batch Video Downloader
**Version:** 1.4.0
**Status:** Stable (Library 3-pane with thumbnails, SemVer infra, TikTok cookies parity)
**Last Updated:** 2026-05-02

## Executive Summary

Dual-interface Python application for batch-downloading TikTok and Facebook videos without watermarks. Includes PySide6 desktop GUI with tabbed interface and command-line tool with Rich progress UI. Features concurrent downloads, profile/page scraping, channel browsing, and automatic duplicate detection across both platforms.

## Core Features

1. **Dual Interface** — PySide6 desktop GUI (tabbed interface) or CLI with Rich UI
2. **Multi-platform Support** — TikTok and Facebook videos in single batch
3. **Download Modes** — Single URLs, batch files, TikTok user profiles, Facebook pages
4. **Channel/Page Browsing** — Discover and browse TikTok channels and Facebook pages via GUI
5. **Concurrent Processing** — ThreadPoolExecutor with configurable workers (default: 3)
6. **Duplicate Detection** — Filesystem scan prevents re-downloading; cross-platform awareness
7. **Rate Limiting** — Configurable inter-request delay to respect platform rate limits
8. **Watermark Removal** — yt-dlp extraction for clean, high-quality output
9. **Real-time Progress** — GUI table updates and CLI progress bar with percentages
10. **Settings Persistence** — Configuration saved to ~/.tiktokder/config.json (output dir, workers, delay)
11. **Library Preview Pane** — 3-pane layout with large thumbnail, metadata, and description; sortable/filterable history; advanced search across title/uploader/URL/description (v1.4.0)
12. **TikTok Cookies Parity** — Netscape `cookies.txt` support for both TikTok and Facebook, lifts anonymous rate limits (v1.4.0)
13. **SemVer Infrastructure** — Automated version management via `version.py` SSOT; reflected in GUI title, CLI `--version`, and build artifacts (v1.4.0)

## Technical Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.10+ |
| **Video Engine** | yt-dlp 2024.0.0+ |
| **Desktop UI** | PySide6 6.6.0+ |
| **CLI UI** | Rich 13.0.0+ |
| **Testing** | pytest 7.0.0+ |
| **Packaging** | PyInstaller 6.0.0+ |
| **Concurrency** | ThreadPoolExecutor (Python stdlib) |

## Architecture Overview

### Entry Points
- **`app.py`** — PySide6 desktop GUI entry point
- **`main.py`** — CLI entry point with argparse handler

### Core Modules
- **`url_parser.py`** — URL validation, platform detection, channel detection, batch file parsing
- **`downloader.py`** — yt-dlp wrapper, concurrent execution, platform-aware jitter, quality profiles
- **`download_engine.py`** — Unified download orchestration for GUI & CLI; QThread-based; queue dedup & history integration
- **`channel_fetcher.py`** — TikTok channel metadata and video list retrieval via yt-dlp flat-playlist
- **`facebook_fetcher.py`** — Playwright-based Facebook page scraping (headless Chromium; cookies.txt injection to lift 10-reel anon cap)
- **`facebook_resolver.py`** — Pre-resolve fb.watch shortlinks to fast-fail login walls (curl_cffi)
- **`config.py`** — AppConfig + PlatformDefaults; ~/ .tiktokder/config.json persistence
- **`app_state.py`** — AppState dataclass (active tab, browser state snapshots, queue) → data/state.json
- **`saved_channels_store.py`** — SavedChannel + Store CRUD; platform-scoped bookmarks; "Download all new" filters
- **`history_store.py`** — v1→v2 schema migration; FIFO cap; atomic write; HistoryRecord per download
- **`path_builder.py`** — platform/uploader-aware path building + slug normalization
- **`retry_policy.py`** — Tenacity decorators + typed exceptions (LoginRequired, RateLimited, etc.)

### GUI Package (`gui/`) — v1.4.0 Library Preview Pane
- **`main_window.py`** — Main window with global URL bar + QTabWidget (TikTok / Facebook / Settings)
- **`global_url_bar.py`** — Persistent URL input above tabs; drag-drop `.txt` files and URLs
- **`platform_tab.py`** — Per-platform composite widget with 3 sub-tabs (Channels / Queue / Library)
- **`saved_channels_panel.py`** — Saved channels list with browser embedded; "Download all new" feature
- **`library_panel.py`** — 3-pane layout: uploader sidebar + sortable/filterable history table + preview pane (v1.4.0); advanced filter row (quality/date/size/status); search debounce across title/uploader/URL/description
- **`library_preview_pane.py`** — Right-pane preview widget (NEW v1.4.0): cached large thumbnail + metadata form + description QTextEdit
- **`library_thumbnail_delegate.py`** — Table cell renderer for thumbnail column (NEW v1.4.0)
- **`download_table.py`** — Queue sub-tab table; real-time status/progress/size columns; token-aware QSS progress bars
- **`base_browser_panel.py`** — Shared base for TikTok/Facebook browser panels
- **`tiktok_browser_panel.py`** — TikTok channel browser via ChannelFetcher
- **`facebook_browser_panel.py`** — Facebook page browser via FacebookFetcher; Scrolls spinbox + "Load more"
- **`status_bar_widget.py`** — Status bar badges: TT/FB/Done counts + free-text status
- **`settings_panel.py`** — Settings tab with Global / TikTok / Facebook QGroupBox sections
- **`_history_helpers.py`** — Utility funcs: `format_size`, `format_date`, `open_path`, `reveal_in_file_manager`
- **`theme.py`** — Bootstrap dark theme + OS dark-mode listener; Accent #4F46E5
- **`tokens.py`** — 15 semantic color keys (headless-testable)
- **`spacing.py`** — 8pt grid spacing constants (XS–XXXL)
- **`icons.py`** — qtawesome icon memo cache
- **`progress_styles.py`** — Per-row QProgressBar stylesheet builder, token-aware QSS (NEW v1.4.0)

### Data Flow (GUI)
```
app.py → MainWindow → TabWidget
├── url_input_panel → download_engine → downloader → yt-dlp
├── channel_browser → channel_fetcher → TikTok data
└── settings_panel → config.py (persistence)
```

### Data Flow (CLI)
```
main.py → parse_args() → download_batch() → concurrent ThreadPoolExecutor
└── download_video() → yt-dlp wrapper (with optional progress_hook)
```

## Functional Requirements

| Req ID | Requirement | Status |
|--------|-------------|--------|
| FR-1 | Accept single TikTok or Facebook video URL (GUI & CLI) | ✓ Implemented |
| FR-2 | Accept batch file with mixed-platform URLs | ✓ Implemented |
| FR-3 | Accept TikTok username for profile scraping | ✓ Implemented |
| FR-4 | Accept Facebook page URL for scraping | ✓ Implemented |
| FR-5 | Skip empty lines and comments in batch files | ✓ Implemented |
| FR-6 | Remove duplicates and validate mixed URLs | ✓ Implemented |
| FR-7 | Detect platform (TikTok vs. Facebook) automatically | ✓ Implemented |
| FR-8 | Extract clean videos without watermarks | ✓ Implemented |
| FR-9 | Detect and skip already-downloaded videos | ✓ Implemented |
| FR-10 | Display real-time progress (GUI table + CLI bar) | ✓ Implemented |
| FR-11 | Browse TikTok channels and Facebook pages (GUI) | ✓ Implemented |
| FR-12 | Configure output dir, workers, delay | ✓ Implemented |
| FR-13 | Persist settings to ~/.tiktokder/config.json | ✓ Implemented |

## Non-Functional Requirements

| Req ID | Requirement | Status |
|--------|-------------|--------|
| NFR-1 | Support 3+ concurrent downloads by default | ✓ Implemented |
| NFR-2 | Configurable inter-request delay for rate limiting | ✓ Implemented |
| NFR-3 | Graceful error handling per video | ✓ Implemented |
| NFR-4 | Keyboard interrupt handling (SIGINT) | ✓ Implemented |
| NFR-5 | Handle batch files up to 10,000+ URLs | ✓ Scalable |
| NFR-6 | No API keys or authentication required | ✓ Implemented |
| NFR-7 | Unit test coverage for all modules | ✓ 104 tests |
| NFR-8 | Save/restore GUI window position and size | ✓ Implemented |
| NFR-9 | Responsive GUI with non-blocking downloads | ✓ Implemented |
| NFR-10 | Cross-platform support (Windows, macOS, Linux) | ✓ Supported |

## CLI Interface

```
usage: python main.py <url|--batch FILE|--user USERNAME|--facebook-page URL> [options]

Input modes (choose one):
  url                        Single TikTok or Facebook video URL
  --batch FILE               Text file with URLs (mixed platforms, one per line)
  --user USERNAME            TikTok username to scrape (with or without @)
  --facebook-page PAGE_URL   Facebook page URL to scrape

Options:
  --output DIR              Output directory (default: ./downloads)
  --workers N               Concurrent downloads (default: 3)
  --delay N                 Delay between requests in seconds (default: 1.0)
```

**Input Modes (mutually exclusive):**
- Direct URL (auto-detects TikTok or Facebook)
- `--batch FILE` for bulk mixed-platform processing
- `--user USERNAME` for TikTok profile scraping
- `--facebook-page URL` for Facebook page scraping

## Success Criteria

- [x] All 326+ unit tests pass
- [x] Single video downloads without watermark (TikTok & Facebook, GUI & CLI)
- [x] Batch file processing with mixed-platform support
- [x] TikTok profile and Facebook page scraping capability
- [x] Concurrent downloads with real-time progress (GUI & CLI)
- [x] Automatic skip of previously downloaded videos (cross-platform)
- [x] Platform detection (TikTok vs. Facebook) automatic
- [x] CLI accepts all required arguments with validation
- [x] Desktop GUI with platform-first tabs (TikTok / Facebook / Settings); each platform has Channels / Queue / Library sub-tabs
- [x] Global URL bar with drag-drop `.txt` and URL support; auto-routes by platform
- [x] Per-platform Library with uploader sidebar + filtered history; right-click actions (open/reveal/re-download/remove)
- [x] Saved Channels management: CRUD, "Download all new" (filters cached videos), starred/nicknames
- [x] Persistent UI state: active tab, browser scrollback, queue snapshot → data/state.json
- [x] Settings persisted to ~/.tiktokder/config.json with auto-sync on field change
- [x] Facebook browser with Scrolls spinbox (1–50) and "Load more" button for Playwright scrape resumption
- [x] User-friendly error dialogs and CLI messages

## Known Limitations

1. **Platform scraping:** TikTok and Facebook may rate-limit; use `--delay` to mitigate
2. **Watermark removal:** yt-dlp best-effort; quality depends on platform video format
3. **Persistence:** No database; duplicate detection filesystem-based only
4. **Error recovery:** Failed downloads logged but not auto-retried
5. **Facebook Playwright:** Requires headless browser; may be rate-limited by Facebook

## Dependencies & Constraints

- **External:** yt-dlp must be maintained for TikTok compatibility
- **OS:** Cross-platform (Windows, macOS, Linux)
- **Network:** Requires active internet connection
- **Rate limits:** TikTok may throttle requests; `--delay` mitigates this
- **Storage:** Videos stored locally; no cloud integration

## Semver Release Infrastructure (v1.4.0)

- **SSOT:** `version.py` contains `__version__ = "1.4.0"` constant
- **Propagation:** Imported by `app.py` (GUI title + About dialog), `main.py` (CLI `--version` flag), `build.py` (PyInstaller spec)
- **Versioning:** Follow semantic versioning (Major.Minor.Patch)
- **Details:** See `docs/release-process.md` for version bump procedures

## Facebook Folder Structure (v1.4.0)

Output tree now uses Facebook **page slug** (URL-safe name) instead of display name:
```
downloads/facebook/{pagename}/{title} [{short_id}].{ext}
```
Example: `downloads/facebook/bbc-news/breaking story [a1b2c3].mp4` (not `downloads/facebook/BBC News/...`). Legacy `{video_id}_{title}.{ext}` files saved by prior versions remain dedup-recognized.

## Future Enhancements

- Resume interrupted batch downloads
- Video metadata export (duration, likes, views, upload date)
- Database for persistent download history and statistics
- Scheduled/recurring batch downloads
- Webhook notifications on completion
- Standalone executable (PyInstaller packaging — via `build.py`)
- Advanced search and filtering in channel/page browser
- Support for additional platforms (Instagram, YouTube, Twitter)

## Testing & Quality Assurance

- **Unit Tests:** 104 tests covering all modules (67 original + 37 new for GUI/config/engine)
- **Test Files:** 4 test modules (test_tiktokder.py, test_config.py, test_download_engine.py, test_channel_fetcher.py)
- **Test Coverage:** URL parsing, batch processing, download logic, channel detection, config persistence, error handling
- **CI/CD Ready:** pytest integration for automated testing
- **Error Scenarios:** Network failures, invalid URLs, missing files, file permissions, invalid config

## Maintenance & Support

- **Documentation:** README.md with usage examples and CLI reference
- **Code Quality:** Type hints, docstrings, error handling
- **Backwards Compatibility:** Semver versioning; breaking changes documented
- **Updates:** Follow yt-dlp releases for TikTok compatibility
