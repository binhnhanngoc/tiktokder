# Project Changelog

## Versioning Policy

TikTokDer follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):
- **MAJOR** — breaking changes to CLI flags, config schema, history/state file format, or data folder layout.
- **MINOR** — new features, additive config keys, new GUI panels (backwards compatible).
- **PATCH** — bug fixes, dependency bumps, doc-only changes, performance tweaks (no UX or data changes).

The single source of truth is `version.py` (`__version__`). The README badge line and the latest changelog entry below must match it on every release. See `docs/release-process.md` for the bump checklist.

## [1.5.0] — 2026-05-02 — Health View

### Added
- **Health View** — visible signals for platform fragility. Status-bar pill (gray/green/amber/red) reflects max severity; click opens a popover listing current issues. New "Health" QGroupBox at the top of Settings lists each issue with a fix-action button (open cookies file / open releases page / refresh channel) and a dismiss `×`. "Refresh now" button forces a recompute including the 24h-cached yt-dlp PyPI version check.
- **6 health signals** (pure-data layer, zero Qt imports): stale fetch (≥14d info, ≥30d warn), auth-wall likely (empty fetch despite cookies), no new downloads in 30d, login-required marker, cookies file age (≥60d warn, ≥120d error), yt-dlp outdated.
- **Sidecar cache** (`data/health_cache.json`, schema v1) — 24h yt-dlp PyPI version cache, per-channel last-fetch outcome markers, dismissed-issue IDs. Atomic writes serialized via `threading.Lock` so engine + GUI threads can't drop each other's updates.
- **CLI smoke entry**: `python -m health_check` prints the current report — Qt-free.
- 34 new tests (`test_health_check.py`, `test_health_widgets.py`); coverage `health_check.py` 87%, `health_signals.py` 85%.

### Notes
- Refresh cadence: app start + post-download (`engine.history_changed`) + 30-min `QTimer`. Compute runs in `QThreadPool` so the optional PyPI fetch never blocks the UI thread.
- `MainWindow.closeEvent` now stops the timer and waits ≤2s on the global thread pool to prevent dangling-slot crashes during shutdown.
- No backwards-incompatible changes; new cache file is created on first refresh and ignored if absent.

## [1.4.0] — 2026-05-01 — Library polish, cookies parity, versioning infra

### Added
- **Library**: thumbnails always-on (sidecars next to videos) + right-side preview pane with metadata and full description.
- **Cookies**: TikTok `cookies.txt` parity with Facebook (per-platform cookie file paths).
- **Channels**: Facebook downloads use page-name folders (per-channel browse cache).
- **GUI**: progress bar styled with token-aware QSS.
- **Versioning infrastructure**: `version.py` SSOT wired through GUI title bar, About dialog, CLI `--version`, build artifact filename, and Windows EXE metadata. New `docs/release-process.md`.

### Fixed
- **GUI**: rapid profile switch no longer hangs the window.

### Notes
- No data-format changes; no breaking config changes. Forward-compatible with 1.3.x state files.

## [1.3.1] — 2026-04-27 — Library panel sort & filters
- **Library**: All columns now sortable by header click (Size sorts by raw bytes, default Date desc)
- **Library**: Added compact filter row — Quality dropdown, Date range (From/To) with toggles, Size ≥ MB threshold, Status (Available/Missing via file scan). All filters debounced 200ms.

## [1.3.0] — 2026-04-26 — Platform-first UI restructure

### Added
- Top-level **TikTok / Facebook / Settings** tabs replace the function-mixed `Download / Channel / History / Settings` IA.
- Each platform tab hosts **Channels / Queue / Library** sub-tabs.
- **Saved channels** persistence (`data/saved_channels.json`, schema v1) — `saved_channels_store.py` with CRUD, atomic write, tolerant load, cap-200/platform with FIFO trim.
- **Download all new** action on saved channels — filters out already-downloaded videos and (when `last_fetched_at` known) videos older than the cutoff. Confirm dialog at >10.
- **Library** two-pane view per platform — uploader sidebar (★ marks saved channels) + filtered history table. Right-click rows for Open / Folder / Re-download / Copy URL / Remove.
- **Global URL bar** above all tabs — paste/drop URLs or `.txt` files; auto-routes by `detect_platform` to the matching platform's queue.
- **Status bar** with TT / FB / Done badges + free-text status.
- **Settings split** into Global / TikTok / Facebook QGroupBoxes.
- `AppConfig.facebook_max_scrolls_default` (10) — propagates to `FacebookBrowserPanel.scrolls_spin` on init.
- `AppState.library_active_uploader_{tiktok,facebook}` — survives app close/reopen.
- 25 new tests across `test_saved_channels_store.py`, `test_saved_channels_panel.py`, `test_global_url_bar.py`, `test_library_panel.py`, `test_settings_split.py`.

### Removed
- `gui/channel_browser.py`, `gui/download_tab.py`, `gui/history_tab.py`, `gui/url_input_panel.py` — superseded by platform tabs + global URL bar + library panel.
- `MainWindow.url_input` / `MainWindow.download_table` back-compat aliases.

### Notes
- Hard cutover — no `layout_v2` flag.
- Backend untouched (`download_engine.py`, fetchers, `history_store.py`, `path_builder.py` unchanged).
- Test count: 326 (up from 301 in v1.2.0).
