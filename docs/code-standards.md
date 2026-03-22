# Code Standards & Architecture

## Project Structure

```
tiktokder/
├── app.py                      # GUI entry point
├── main.py                     # CLI entry point
├── config.py                   # Settings persistence
├── url_parser.py               # URL validation & parsing (TikTok & Facebook)
├── downloader.py               # yt-dlp wrapper, concurrent downloads
├── download_engine.py          # Unified download orchestration
├── channel_fetcher.py          # TikTok channel & Facebook page fetcher
├── facebook_fetcher.py         # Playwright-based Facebook scraper
├── gui/
│   ├── __init__.py
│   ├── main_window.py          # Main window & tab orchestration
│   ├── url_input_panel.py      # Single URL input UI
│   ├── download_table.py       # Download queue display
│   ├── channel_browser.py      # Channel/page discovery UI
│   └── settings_panel.py       # Configuration UI
├── docs/
│   ├── project-overview-pdr.md
│   ├── code-standards.md
│   ├── system-architecture.md
│   ├── codebase-summary.md
│   └── gui-usage.md
├── test_tiktokder.py           # Core module tests
├── test_config.py              # Config persistence tests
├── test_download_engine.py     # Download engine tests
├── test_channel_fetcher.py     # Channel fetcher tests
├── requirements.txt
└── README.md
```

## Code Style Guidelines

### Python Standards
- **Version:** Python 3.10+ (type hints required)
- **Type Hints:** All function signatures must include type hints
- **Line Length:** 100 characters preferred, 120 maximum
- **Imports:** Group into stdlib, third-party, local (PEP 8)
- **Docstrings:** Module, class, and function docstrings required (Google style)
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes

### Example Function
```python
def validate_tiktok_url(url: str) -> bool:
    """Validate if URL is a TikTok video link.

    Args:
        url: URL string to validate

    Returns:
        True if valid TikTok URL, False otherwise
    """
    # Implementation
```

## Module Responsibilities

### `url_parser.py`
- **Purpose:** Multi-platform URL validation, parsing, and batch file handling
- **Functions:**
  - `validate_tiktok_url(url: str) -> bool` — Validate TikTok video URLs
  - `validate_facebook_url(url: str) -> bool` — Validate Facebook video URLs
  - `validate_url(url: str) -> bool` — Validate TikTok or Facebook URLs
  - `is_channel_url(url: str) -> bool` — Detect if URL is a TikTok channel
  - `is_facebook_page_url(url: str) -> bool` — Detect if URL is a Facebook page
  - `is_page_or_channel_url(url: str) -> bool` — Detect if URL is any page/channel
  - `detect_platform(url: str) -> str | None` — Auto-detect ('tiktok', 'facebook', or None)
  - `extract_video_id(url: str) -> str | None` — Extract video ID
  - `read_batch_file(path: str) -> list[str]` — Parse batch (mixed platforms, skip comments)
  - `build_user_url(username: str) -> str` — Build TikTok user profile URL

### `downloader.py`
- **Purpose:** Multi-platform video extraction via yt-dlp (TikTok and Facebook)
- **Functions:**
  - `get_ydl_opts(output_dir: str) -> dict` — Build yt-dlp options (watermark removal, format)
  - `download_video(url: str, output_dir: str, progress_hook: Callable | None = None) -> DownloadResult` — Download single video (auto-detects platform)
  - `download_batch(urls: list[str], output_dir: str, workers: int = 3, delay: float = 1.0, progress_callback: Callable | None = None) -> list[DownloadResult]` — Concurrent downloads (mixed platforms)
  - `get_downloaded_ids(output_dir: str) -> set[str]` — Get already-downloaded video IDs (filesystem scan)

### `download_engine.py`
- **Purpose:** Unified download orchestration for GUI and CLI
- **Classes:**
  - `DownloadEngine` — Manages downloads with progress hooks for GUI integration
- **Methods:**
  - `add_urls(urls: list[str])` — Queue videos
  - `start_downloads()` — Begin concurrent processing
  - `cancel()` — Stop all downloads
  - `progress_hook(info: dict) -> None` — Receive yt-dlp progress updates

### `channel_fetcher.py`
- **Purpose:** Retrieve TikTok channel and Facebook page information and video lists
- **Functions:**
  - `get_channel_videos(channel: str, limit: int = 30) -> list[dict]` — Fetch TikTok channel or Facebook page videos
  - `get_channel_metadata(channel: str) -> dict | None` — Get channel/page info (followers, bio, video count)

### `facebook_fetcher.py` (NEW)
- **Purpose:** Playwright-based Facebook page scraping for video discovery
- **Functions:**
  - `scrape_facebook_page(page_url: str, limit: int = 50) -> list[dict]` — Extract videos from Facebook page using headless browser
  - `get_facebook_page_metadata(page_url: str) -> dict | None` — Retrieve page info (name, follower count)
- **Dependencies:** Playwright, async browser automation
- **Notes:** Headless browser required; may trigger Facebook rate limiting

### `config.py`
- **Purpose:** Settings persistence and management
- **Classes:**
  - `AppConfig` — Dataclass for application settings
- **Functions:**
  - `load_config() -> AppConfig` — Load from `~/.tiktokder/config.json`
  - `save_config(config: AppConfig) -> None` — Save to disk

### `gui/main_window.py`
- **Purpose:** Main application window and tab orchestration
- **Classes:**
  - `MainWindow(QMainWindow)` — Top-level window with tab widget

### `gui/url_input_panel.py`
- **Purpose:** Single URL input and download controls
- **Classes:**
  - `UrlInputPanel(QWidget)` — URL input field, download button, status label

### `gui/download_table.py`
- **Purpose:** Display download queue and real-time progress
- **Classes:**
  - `DownloadTable(QTableWidget)` — Table showing video status, progress, size

### `gui/channel_browser.py`
- **Purpose:** Channel/page discovery and browsing interface
- **Classes:**
  - `ChannelBrowser(QWidget)` — Search TikTok channels or Facebook pages, display video list, batch download

### `gui/settings_panel.py`
- **Purpose:** Configuration UI
- **Classes:**
  - `SettingsPanel(QWidget)` — Output dir, workers, delay spinboxes with Save button

## Error Handling

### Pattern: Try-Except with Logging
```python
try:
    result = download_video(url, output_dir)
except NetworkError as e:
    logger.error(f"Network error for {url}: {e}")
    return DownloadResult(url, False, str(e))
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
    raise
```

### Error Types
- `NetworkError` — Network failures, TikTok blocking
- `InvalidURLError` — Malformed or non-TikTok URLs
- `PermissionError` — Output directory write access denied
- `DuplicateError` — Video already downloaded (logged, not raised)

## Testing Standards

### Test Structure
- Test files parallel module structure: `test_<module>.py`
- Use `pytest` framework
- Organize tests with classes: `class Test<Module>`
- One test per function/behavior

### Example Test
```python
def test_validate_tiktok_url_with_valid_url():
    """Test URL validation accepts standard TikTok URLs."""
    url = "https://www.tiktok.com/@user/video/1234567890"
    assert validate_tiktok_url(url) is True

def test_validate_tiktok_url_with_invalid_url():
    """Test URL validation rejects non-TikTok URLs."""
    assert validate_tiktok_url("https://youtube.com/watch?v=xyz") is False
```

### Coverage Goals
- Aim for 85%+ line coverage
- Cover error paths and edge cases
- Mock network calls in tests

## Version Control & Commits

### Commit Message Format
- Type: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Example: `feat: add is_channel_url() to url_parser module`
- Keep focused on logical changes

### File Ownership
- **Core:** url_parser.py, downloader.py, download_engine.py, channel_fetcher.py, config.py
- **GUI:** gui/*.py
- **Tests:** test_*.py
- **Docs:** docs/*.md

## Performance Considerations

### Concurrency
- Default 3 concurrent downloads balances speed and TikTok rate limits
- ThreadPoolExecutor used (network-bound, not CPU-bound)
- Progress hooks called on every yt-dlp status update (high frequency)

### Memory
- Batch files loaded entirely into memory (limit ~100k+ URLs)
- Download metadata stored in GUI tables (manage retention for large batches)
- Config stored as JSON (keep small, ~1KB typical)

### GUI Responsiveness
- Long operations run in separate threads (QThread or ThreadPoolExecutor)
- Main thread handles UI updates via signals/slots
- Progress callbacks marshal updates to GUI thread safely

## Security Considerations

- No credentials stored (yt-dlp handles auth-free downloads)
- Config file stored in user home directory (~/.tiktokder/)
- No external API calls (uses yt-dlp's TikTok extraction)
- File paths validated before use (no directory traversal)

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| yt-dlp | 2024.0.0+ | Multi-platform video extraction (TikTok, Facebook) |
| PySide6 | 6.6.0+ | Desktop GUI framework |
| Rich | 13.0.0+ | CLI progress bars and colored output |
| Playwright | 1.40.0+ | Headless browser for Facebook scraping |
| pytest | 7.0.0+ | Unit testing framework |
| PyInstaller | 6.0.0+ | Standalone executable packaging |

## Future Standards

- Add mypy type checking to CI
- Enforce Black code formatting
- Add linting with flake8 or ruff
- Integration tests for download flow
- GUI performance testing with large batch queues
