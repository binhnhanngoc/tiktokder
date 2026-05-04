# Code Standards & Architecture

## Project Structure

```
tiktokder/
├── app.py                      # GUI entry point; bootstrap QApp + MainWindow
├── main.py                     # CLI entry point; argparse dispatcher
├── config.py                   # AppConfig + PlatformDefaults; persistence
├── app_state.py                # AppState UI state snapshots (v1.3)
├── url_parser.py               # URL validation, platform detection, batch parsing
├── downloader.py               # yt-dlp wrapper; quality profiles; platform-aware jitter
├── download_engine.py          # Unified orchestration (QThread-based)
├── channel_fetcher.py          # TikTok channel metadata via yt-dlp flat-playlist
├── facebook_fetcher.py         # Playwright Facebook scraper; cookies.txt injection
├── facebook_resolver.py        # fb.watch pre-resolver (curl_cffi)
├── retry_policy.py             # Tenacity + typed exceptions
├── history_store.py            # HistoryRecord persistence; v1→v3 migration (v1.4.0: description + thumbnail_path)
├── path_builder.py             # Slugify + outtmpl builders
├── saved_channels_store.py     # SavedChannel CRUD + "Download all new" (v1.3)
├── version.py                  # __version__ SSOT (v1.4.0)
├── yt_dlp_helpers.py           # apply_cookies() mutator for file-precedence cookie wiring (v1.4.0)
├── gui/
│   ├── __init__.py
│   ├── main_window.py          # MainWindow + QTabWidget orchestration
│   ├── global_url_bar.py       # Persistent URL bar (v1.3)
│   ├── platform_tab.py         # Per-platform composite widget (v1.3)
│   ├── saved_channels_panel.py # Saved channels CRUD + browser (v1.3)
│   ├── library_panel.py        # Two-pane history + uploader sidebar (v1.3)
│   ├── download_table.py       # Queue sub-tab table widget
│   ├── base_browser_panel.py   # Shared TikTok/Facebook browser base
│   ├── tiktok_browser_panel.py # TikTok browser UI
│   ├── facebook_browser_panel.py # Facebook browser + Scrolls spinbox
│   ├── library_preview_pane.py # Preview pane with thumbnail + metadata + description (v1.4.0)
│   ├── library_thumbnail_delegate.py # Thumbnail column delegate (v1.4.0)
│   ├── progress_styles.py      # Token-aware QSS for progress bars (v1.4.0)
│   ├── status_bar_widget.py    # Status badges (v1.3)
│   ├── settings_panel.py       # Global/TikTok/Facebook settings
│   ├── _history_helpers.py     # format_size, format_date, open_path (v1.3)
│   ├── theme.py                # Dark theme bootstrap + OS listener
│   ├── tokens.py               # 15 semantic color tokens
│   ├── spacing.py              # 8pt grid spacing
│   └── icons.py                # qtawesome icon cache
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
- **Purpose:** yt-dlp wrapper for multi-platform video extraction (TikTok + Facebook)
- **Classes:**
  - `DownloadResult` — Dataclass: `url, success, video_id, title, error, skipped, file_path`
- **Functions:**
  - `get_ydl_opts(output_dir, cookie_browser=None, quality="best", write_subs=False, write_thumb=True, cookies_file=None) -> dict` — Build yt-dlp options (quality preset, impersonate=chrome136, postprocessors). **v1.4.0: `write_thumb=True` always** (toggle removed). Cookie wiring delegated to `yt_dlp_helpers.apply_cookies()` (file > browser > none).
  - `download_video(url, output_dir, progress_hook=None, cookies_file=None, ...) -> DownloadResult` — Single video; pre-resolves FB shortlinks; wraps `_do_download` in tenacity retry
  - `download_batch(urls, output_dir, workers=3, delay=1.0, progress_callback=None, ...) -> list[DownloadResult]` — Concurrent CLI batch (platform-aware pacing)

### `yt_dlp_helpers.py` (v1.4.0)
- **Purpose:** Shared yt-dlp option mutators kept out of `downloader.py`
- **Functions:**
  - `apply_cookies(ydl_opts, browser, file_path) -> None` — Mutate `ydl_opts` to add cookie source. File precedence over browser; missing/empty file falls through to browser; neither set → no mutation. Used by both TikTok and Facebook (parity in v1.4.0).

### `download_engine.py`
- **Purpose:** Qt download orchestration for GUI (queue, dedup, history, retries)
- **Classes:**
  - `DownloadWorker(QThread)` — Runs `download_video()` for one URL; emits `progress`, `finished_download`
  - `DownloadEngine(QObject)` — Queue manager with concurrency, dedup, history persistence
- **Signals:** `download_started(url)`, `download_progress(url, percent)`, `download_finished(url, DownloadResult)`, `all_finished()`, `queue_updated(remaining)`, `history_changed()`
- **Methods:**
  - `add_urls(urls, force=False)` — Queue URLs (skips duplicates + already-downloaded IDs); auto-spawns workers
  - `cancel_url(url)` — Cancel one active worker
  - `cancel_all()` — Clear queue + cancel all active
  - `retry_url(url, force=False)` / `retry_urls(urls, force=False)` — Drop from dedup, re-queue
  - `apply_runtime_settings(...)` — Live-propagate Settings panel changes

### `channel_fetcher.py` (v1.4.0 + cookies.txt)
- **Purpose:** TikTok channel video listing via yt-dlp flat-playlist (QThread)
- **Classes:**
  - `ChannelFetcher(QThread)` — Emits `video_found(VideoInfo)`, `error(str)`, `finished()`; supports `cancel()`. **v1.4.0: accepts `cookies_file` parameter** for Netscape cookies.txt support (parity with Facebook)

### `facebook_fetcher.py`
- **Purpose:** Facebook page/profile scraping via Playwright headless Chromium (QThread)
- **Classes:**
  - `FacebookFetcher(QThread)` — Scroll & scrape reel/video links; optional cookies.txt injection (lifts 10-reel anonymous cap); 3-empty-streak stop; supports `cancel()`
- **Signals:** `video_found(VideoInfo)`, `progress(str)`, `error(str)`, `finished()`
- **Dependencies:** Playwright (chromium), `facebook_cookies.load_netscape_cookies()`
- **Notes:** Headless browser required; max_scrolls configurable (1–50); falls back to anonymous if cookies file missing

### `config.py`
- **Purpose:** Settings persistence and management
- **Classes:**
  - `AppConfig` — Dataclass for application settings
- **Functions:**
  - `load_config() -> AppConfig` — Load from `~/.tiktokder/config.json`
  - `save_config(config: AppConfig) -> None` — Save to disk

### `gui/main_window.py`
- **Purpose:** Main application window with platform-first tab orchestration
- **Classes:**
  - `MainWindow(QMainWindow)` — Central: GlobalUrlBar (top) + QTabWidget (TikTok/Facebook/Settings) + StatusBarWidget (bottom)
- **Responsibilities:** Window geometry persistence, tab signal routing, per-platform queue/library refresh

### `gui/global_url_bar.py`
- **Purpose:** Persistent URL input bar above all tabs
- **Classes:**
  - `GlobalUrlBar(QWidget)` — QLineEdit + Add button, drag-drop support, emits `urls_submitted(list[str])`
- **Features:** Mixed-platform batch import from `.txt` files, URL MIME drag-drop

### `gui/platform_tab.py`
- **Purpose:** Per-platform composite widget with 3 sub-tabs
- **Classes:**
  - `PlatformTab(platform, browser_panel, store, store_path)` — QTabWidget with Channels / Queue / Library; drag-drop filtered to own platform

### `gui/library_panel.py` (v1.4.0 — 3-pane + advanced filtering)
- **Purpose:** Per-platform history with 3-pane layout, sortable columns, advanced filters, and preview pane
- **Classes:**
  - `LibraryPanel(QWidget)` — **3-pane layout:** left uploader sidebar (frequency-sorted, ★ for saved channels), middle sortable/filterable history table with thumbnail column (Size numeric, Date chronologic, default Date desc), right `LibraryPreviewPane`
  - **Advanced filter row:** Quality dropdown, Date From/To pickers, Size ≥ MB, Status (Available/Missing), search box (200ms debounce, matches title/uploader/URL/description)
  - Right-click: Open file / Open folder / Re-download / Copy URL / Remove. Single-click row triggers preview pane update.
- **Responsibilities:** Sub-tab selection state, platform-scoped signal routing

### `gui/saved_channels_panel.py`
- **Purpose:** Saved channels management + embedded browser
- **Classes:**
  - `SavedChannelsPanel(QWidget)` — Toolbar (Add/Refresh All), channel list table (★/nickname/url/count/last-fetched), embedded browser below
- **Features:** Right-click CRUD, "Download all new" with dedup filter, star/nickname/notes editing

### `gui/library_panel.py`
- **Purpose:** Per-platform history with uploader sidebar and discovery
- **Classes:**
  - `LibraryPanel(QWidget)` — Two-pane: left uploader sidebar (frequency-sorted, ★ for saved channels), right history table (Title/Quality/Size/Date/Path)
- **Features:** Search (200ms debounce), per-uploader selection, right-click (Open/Reveal/Re-download/Copy URL/Remove)

### `gui/download_table.py`
- **Purpose:** Queue sub-tab table for per-platform downloads
- **Classes:**
  - `DownloadTableWidget(QWidget)` — URL / Title / Status / Progress / Size columns; toolbar (Clear Completed / Clear All / Retry / Force)
- **Features:** Right-click for Open/Reveal/Retry/Force/Copy URL/Clear row

### `gui/base_browser_panel.py`
- **Purpose:** Shared base for TikTok and Facebook browser panels
- **Classes:**
  - `BaseBrowserPanel(QWidget)` — URL input + Browse button, video table (`✓` / Title / Duration / Quality / Views / Date columns), Quality + 3-state Downloaded (`All` / `New only` / `Downloaded only`) combos, From/To date toggles, Select All/Deselect/Download Selected, state snapshot/restore. Injected resolvers — `history_ids_resolver: () -> set[str]` and `history_record_resolver: (id) -> HistoryRecord | None` — drive the `✓` cell + Downloaded predicate; `on_history_changed` coalesces engine pulses through a 100 ms one-shot timer before rebuilding the column.

### `gui/tiktok_browser_panel.py`
- **Purpose:** TikTok channel browser UI
- **Classes:**
  - `TikTokBrowserPanel(BaseBrowserPanel)` — Extends base; dispatches to ChannelFetcher

### `gui/facebook_browser_panel.py`
- **Purpose:** Facebook page browser with Playwright scrape control
- **Classes:**
  - `FacebookBrowserPanel(BaseBrowserPanel)` — Scrolls spinbox (1–50, default 10), "Load more" button to resume Playwright scrape

### `gui/status_bar_widget.py`
- **Purpose:** Status bar badges
- **Classes:**
  - `StatusBarWidget(QWidget)` — Labels for TT count, FB count, Done count, free-text status

### `gui/settings_panel.py`
- **Purpose:** Application configuration UI (Global, TikTok, Facebook)
- **Classes:**
  - `SettingsPanel(QWidget)` — Three QGroupBoxes (Global/TikTok/Facebook); output dir, workers, delay, quality, cookies, scrolls; auto-save on field change

### `gui/_history_helpers.py`
- **Purpose:** Shared UI utility functions (v1.3)
- **Functions:**
  - `format_size(bytes) -> str` — Human-readable file size
  - `format_date(timestamp) -> str` — Human-readable date
  - `open_path(path: str)` — Cross-platform file open
  - `reveal_in_file_manager(path: str)` — Cross-platform Reveal in Explorer/Finder

### `gui/theme.py`
- **Purpose:** Dark theme bootstrap and live mode switching
- **Functions:**
  - `bootstrap(app: QApplication, config: AppConfig)` — Load qdarktheme on startup, start OS listener
  - `apply(mode: str)` — Switch theme live (system/light/dark)

### `gui/tokens.py`
- **Purpose:** Semantic color tokens for headless testing
- **Exports:** 15 color keys (bg_primary, border_subtle, text_muted, accent_primary, etc.)

### `gui/spacing.py`
- **Purpose:** 8pt grid spacing constants
- **Constants:** XS (4), SM (8), MD (12), LG (16), XL (24), XXL (32), XXXL (48)

### `gui/icons.py`
- **Purpose:** qtawesome icon caching
- **Functions:** `get_icon(name: str, color: str) -> QIcon` with memo cache

## Error Handling

### Pattern: Typed Exceptions + Tenacity Retry
```python
from retry_policy import (
    LoginRequired, Private, NotFound,
    RateLimited, TransientFailure, with_retry,
)

@with_retry(max_attempts=3)
def _do_download(url, output_dir, ...) -> DownloadResult:
    try:
        ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        raise _classify_error(e)  # → typed exception
```

### Error Types (defined in `retry_policy.py`)

**Permanent (no retry):**
- `LoginRequired` — Login wall detected (FB cookies expired/missing)
- `Private` — Video private/restricted
- `NotFound` — HTTP 404 / video removed

**Retryable:**
- `RateLimited` — HTTP 429; honors `Retry-After` header
- `TransientFailure` — Connection reset, timeout, fragment errors

**Classification:** `_classify_error()` in `downloader.py` string-matches yt-dlp error messages against `FB_LOGIN_WALL_MARKERS` (config), "HTTP 429", "private", "404", connection/timeout patterns.

**Outer retry** (tenacity) sits above yt-dlp's inner per-fragment retries. Decorrelated jitter base=2.0s, cap=60s.

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

### `gui/library_preview_pane.py` (v1.4.0)
- **Purpose:** Right-pane preview widget for Library history
- **Class:** `LibraryPreviewPane(QWidget)` — Displays cached large thumbnail (QPixmapCache "large:" prefix), metadata form (date/size/uploader/quality/views/platform), full description in scrollable QTextEdit
- **Integration:** Embedded in `LibraryPanel` 3-pane layout; triggered by single-click on history table row

### `gui/library_thumbnail_delegate.py` (v1.4.0)
- **Purpose:** Custom QStyledItemDelegate for thumbnail column rendering in Library table
- **Class:** `ThumbnailDelegate(QStyledItemDelegate)` — Scales cached thumbnail images to row height; integrates with QPixmapCache
- **Integration:** Injected into Library history table's thumbnail column

### `gui/progress_styles.py` (v1.4.0)
- **Purpose:** Token-aware QSS stylesheet builder for per-row progress bars
- **Functions:** `build_progress_stylesheet(tokens: Tokens, mode: str) -> str` — Returns QSS with semantic color tokens for progress bar styling (light/dark modes)
- **Integration:** Applied to per-row QProgressBar in `download_table.py`; supports live theme switching via `theme.apply(mode)`

### `version.py` (v1.4.0)
- **Purpose:** Single source of truth for application version (SemVer)
- **Export:** `__version__ = "1.4.0"` constant
- **Governance:** Manual bump only; all downstream references auto-update on import. Major/Minor/Patch bumps documented in `release-process.md`
- **Integration:** Imported by `app.py` (GUI title + About dialog), `main.py` (CLI `--version` flag), `build.py` (PyInstaller spec)

## Future Standards

- Add mypy type checking to CI
- Enforce Black code formatting
- Add linting with flake8 or ruff
- Integration tests for download flow
- GUI performance testing with large batch queues
