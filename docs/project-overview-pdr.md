# TikTok Batch Video Downloader - Project Overview & PDR

## Project Definition

**Name:** TikTok Batch Video Downloader
**Version:** 1.0.0
**Status:** Initial Release
**Last Updated:** 2026-03-21

## Executive Summary

A lightweight Python CLI tool for batch-downloading TikTok videos without watermarks. Supports single URLs, batch file processing, and user profile scraping with concurrent downloads and automatic duplicate detection.

## Core Features

1. **Single & Batch Downloads** — Download individual videos or process multiple URLs from a file
2. **User Profile Scraping** — Download all videos from a TikTok user profile
3. **Concurrent Processing** — Parallel downloads with configurable worker threads (default: 3)
4. **Skip Duplicates** — Automatically detects and skips previously downloaded videos
5. **Rate Limiting** — Configurable inter-request delay to respect TikTok's rate limits
6. **Clean Output** — Videos saved without watermarks; filenames include video ID and title
7. **Rich CLI UI** — Real-time progress bar with color-coded status messages

## Technical Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.10+ |
| **Video Engine** | yt-dlp 2024.0.0+ |
| **UI Framework** | Rich 13.0.0+ |
| **Testing** | pytest 7.0.0+ |
| **Concurrency** | ThreadPoolExecutor (Python stdlib) |

## Architecture Overview

```
main.py (CLI entry point)
├── parse_args() → Argparse CLI handler
├── validate inputs → Exactly one input mode
├── build URL list
│   ├── Single URL: validate_tiktok_url()
│   ├── Batch file: read_batch_file() → deduplicate
│   └── User profile: build_user_url()
├── skip already-downloaded → get_downloaded_ids()
└── download_batch() → concurrent ThreadPoolExecutor
    └── download_video() → yt-dlp wrapper
```

**Key Modules:**
- `url_parser.py` — URL validation, extraction, batch file parsing
- `downloader.py` — yt-dlp wrapper, concurrent execution, progress tracking
- `main.py` — CLI orchestration

## Functional Requirements

| Req ID | Requirement | Status |
|--------|-------------|--------|
| FR-1 | Accept single TikTok video URL | ✓ Implemented |
| FR-2 | Accept batch file with URLs (one per line) | ✓ Implemented |
| FR-3 | Accept TikTok username for profile scraping | ✓ Implemented |
| FR-4 | Skip empty lines and comments in batch files | ✓ Implemented |
| FR-5 | Remove duplicate URLs in batch | ✓ Implemented |
| FR-6 | Validate TikTok URLs before processing | ✓ Implemented |
| FR-7 | Extract clean video without watermark | ✓ Implemented |
| FR-8 | Detect and skip already-downloaded videos | ✓ Implemented |
| FR-9 | Display real-time download progress | ✓ Implemented |
| FR-10 | Configure output directory | ✓ Implemented |

## Non-Functional Requirements

| Req ID | Requirement | Status |
|--------|-------------|--------|
| NFR-1 | Support 3+ concurrent downloads by default | ✓ Implemented |
| NFR-2 | Configurable inter-request delay for rate limiting | ✓ Implemented |
| NFR-3 | Graceful error handling per video | ✓ Implemented |
| NFR-4 | Keyboard interrupt handling (SIGINT) | ✓ Implemented |
| NFR-5 | Handle batch files up to 10,000+ URLs | ✓ Scalable |
| NFR-6 | No API keys or authentication required | ✓ Implemented |
| NFR-7 | Unit test coverage for all modules | ✓ 67 tests |

## CLI Interface

```
usage: python main.py <url> [options]

Positional arguments:
  url                   Single TikTok video URL

Optional arguments:
  --batch FILE         Path to text file with URLs (one per line)
  --user USERNAME      TikTok username to scrape (with or without @)
  --output DIR         Output directory (default: ./downloads)
  --workers N          Concurrent downloads (default: 3)
  --delay N            Delay between downloads in seconds (default: 1.0)
```

**Input Modes (mutually exclusive):**
- Direct URL as positional argument
- `--batch FILE` for bulk processing
- `--user USERNAME` for profile scraping

## Success Criteria

- [x] All 67 unit tests pass
- [x] Single video downloads without watermark
- [x] Batch file processing with duplicate detection
- [x] User profile scraping capability
- [x] Concurrent downloads with progress UI
- [x] Automatic skip of previously downloaded videos
- [x] CLI accepts all required arguments with validation
- [x] Error messages are user-friendly and actionable

## Known Limitations

1. **Profile scraping:** Depends on yt-dlp's ability to extract profile URLs; may be rate-limited
2. **Watermark removal:** Uses yt-dlp best-effort extraction; quality depends on TikTok's current video format
3. **Persistence:** No database; duplicate detection based solely on filesystem scan
4. **Error recovery:** Failed downloads are logged but not retried

## Dependencies & Constraints

- **External:** yt-dlp must be maintained for TikTok compatibility
- **OS:** Cross-platform (Windows, macOS, Linux)
- **Network:** Requires active internet connection
- **Rate limits:** TikTok may throttle requests; `--delay` mitigates this
- **Storage:** Videos stored locally; no cloud integration

## Future Enhancements

- Resume interrupted batch downloads
- Video metadata export (duration, likes, comments)
- Filter videos by date range or engagement metrics
- Database for persistent download history
- Scheduled/recurring batch downloads
- Webhook notifications on completion

## Testing & Quality Assurance

- **Unit Tests:** 67 tests covering all modules
- **Test Coverage:** URL parsing, batch processing, download logic, error handling
- **CI/CD Ready:** pytest integration for automated testing
- **Error Scenarios:** Network failures, invalid URLs, missing files, file permissions

## Maintenance & Support

- **Documentation:** README.md with usage examples and CLI reference
- **Code Quality:** Type hints, docstrings, error handling
- **Backwards Compatibility:** Semver versioning; breaking changes documented
- **Updates:** Follow yt-dlp releases for TikTok compatibility
