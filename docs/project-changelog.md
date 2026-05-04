# Project Changelog

## Versioning Policy

TikTokDer follows [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):
- **MAJOR** — breaking changes to CLI flags, config schema, history/state file format, or data folder layout.
- **MINOR** — new features, additive config keys, new GUI panels (backwards compatible).
- **PATCH** — bug fixes, dependency bumps, doc-only changes, performance tweaks (no UX or data changes).

The single source of truth is `version.py` (`__version__`). The README badge line and the latest changelog entry below must match it on every release. See `docs/release-process.md` for the bump checklist.

## [1.9.0] — 2026-05-04 — In-app Help dialog

### Added
- **`Help` menu surfaces a tabbed in-app manual** — entries for User Manual (F1), How to Export Cookies, How to Configure Cookies, Channels & Library, Troubleshooting, Keyboard Shortcuts, About. Each menu entry opens the dialog at the matching tab.
- **`gui/help_dialog.py` + `gui/help_content.py`** — non-modal `QDialog` with `QTabWidget` of `QTextBrowser` panes; HTML content lives in a separate data module (≈ 200 LOC of pure strings). External `https://` links route through `QDesktopServices` so the dialog never tries to render web pages itself.
- **Cookie walkthroughs** — explicit step-by-step for the *Get cookies.txt LOCALLY* extension (Chrome / Edge / Firefox), with privacy + expiry notes; configure tab explains the TikTok Cookie-Browser-vs-File precedence and what each unblocks.

### Changed
- **`MainWindow._setup_menu`** — replaces the single About entry with the seven-item Help menu; About now opens the same dialog on its own tab. The previous `QMessageBox.about` and its `__version__` import in main_window are removed.
- **`docs/gui-usage.md`** — adds an "In-App Help" section and `F1` to Keyboard Shortcuts.

### Notes
- 12 new tests in `test_help_dialog.py` (tab definitions, dialog instantiation, `open_at_tab` per id, fallback, non-modal, menu wiring, F1 shortcut). All existing tests pass.

## [1.8.0] — 2026-05-04 — Channel browse Downloaded filter

### Added
- **Downloaded filter combo** — TikTok and Facebook browse sub-panels gain a 3-state `Downloaded:` combo (`All` / `New only` / `Downloaded only`) sharing the existing 200 ms debounce timer. AND-combines with search / Quality / date range; status-label tail reads `Found N videos — showing M (K already downloaded)` whenever a filter hides rows.
- **`✓` marker column** — sortable column rendering `✓` for rows whose `video.video_id ∈ history`, with a tooltip showing the `downloaded_at` timestamp from `HistoryRecord` when available. `NumericItem(1, "✓")` / `NumericItem(0, "")` keeps DESC sort grouping downloaded rows together.
- **Per-platform persistence** — two new `AppConfig` string fields (`tiktok_browse_downloaded_filter`, `facebook_browse_downloaded_filter`, default `"all"`); `MainWindow` restores combo state at init and writes back through `save_config` on every `currentIndexChanged`.
- **Live `✓` refresh on download completion** — `BaseBrowserPanel.on_history_changed` slot is wired to `engine.history_changed`; bursts coalesce through a 100 ms one-shot `QTimer` before re-rendering every `✓` cell + reapplying the filter, so a row in the panel flips its mark within ~100 ms of the worker finishing.

### Changed
- **`BaseBrowserPanel` table layout** — column count 6 → 7; new `_COL_DOWNLOADED = 1` shifts every later constant. All call sites use the constants (no integer literals leaked).
- **`_apply_filters` snapshots history ids once per pass** into `self._cached_history_ids` so the per-row predicate is O(1).

### Notes
- 11 new tests (`test_base_browser_panel.py` × 9 covering ✓ render, 3-state predicate, status breadcrumb, signal-block restore, coalesced refresh, hide-aware Select All; `test_config.py` × 2 round-trip). 485 total pass repo-wide.

## [1.7.0] — 2026-05-04 — Channel browse filters + title-leading filenames

### Added
- **Channel browse filters** — TikTok and Facebook browse sub-panels now have a search box, Quality dropdown, From/To date toggles, and sortable headers. Mirrors the Library filter idiom (200ms debounce, single timer). Select All / Download Selected respect the active filter — hidden rows are never selected or queued.
- **Date column populated for TikTok** — `channel_fetcher.upload_date_from_entry` converts yt-dlp's flat-playlist `timestamp` (UTC epoch) to `YYYYMMDD` so the Date column is no longer "—" on a typical creator's recent uploads. Facebook stays "—" because the Playwright DOM scrape has no per-video metadata; documented in `FacebookFetcher`.
- **Shared `gui/_table_items.py::NumericItem`** — extracted from `library_panel.py`; reused by browse panels for numeric-aware Duration / Views / Date sorting.

### Changed
- **Filename layout — title leads, ID is now a 6-char bracketed suffix.** Old: `{id}_{title}.{ext}`. New: `{title} [{short_id}].{ext}`. Path tree (`downloads/{platform}/{uploader}/`) is unchanged. Legacy files from prior versions stay dedup-recognized (regex `^(\d{15,25})_`); new files are dedup-recognized via `history.json`. The 6-char bracketed ID uniquifies same-title videos so silent overwrites are impossible.
- **`downloader.get_downloaded_ids` returns the union** of legacy filename regex + history-oracle. Added `_path_under` helper (realpath + commonpath) so a poisoned `history.json` cannot leak phantom IDs from outside `output_dir`.

### Fixed
- **Live-fetch filter visibility bug** — re-enabling table sorting after each row insert can reorder rows; the predicate now re-applies by current row index instead of a captured pre-sort index, so filters and sort interact correctly during streaming fetch.

### Notes
- No file on disk is renamed by the layout change. Old downloads keep their `{id}_{title}.{ext}` shape; new downloads use the new shape; both sources count as "already downloaded".
- 11 new tests (date helper × 7, dedup union × 4, browse filter row × 8 incl. live-fetch+sort regression). 474 total pass repo-wide.

## [1.6.0] — 2026-05-02 — In-app player

### Added
- **Inline Library playback** — double-clicking a Library row plays the video inside the right-side preview pane via `QStackedWidget` (thumbnail ↔ player). Replaces the previous "Open in OS player" bounce. Transport bar (play/pause + scrubber + time label), letterbox aspect ratio, audio-only files keep the thumbnail visible.
- **Resume-from-position** — after closing or switching records, the next play resumes within (5s, duration−5s) of the saved offset. Position writes are debounced to one disk hit per 5s window plus a final write on stop / pause / source-change / window close.
- **Keyboard shortcuts** (active only when the player page has focus): `J`/`L` = ±10s, `←`/`→` = ±5s, `space`/`K` = toggle play/pause.
- **Codec fallback** — if `QMediaPlayer.errorOccurred` fires (VP9, exotic containers, etc.), the video area swaps to a small "Open externally" panel that hands off to the OS default player. No crashes, no retry loops.
- **HistoryRecord schema v4** — additive: new `last_played_at` and `play_position_seconds` fields. Read paths transparently accept v1 / v2 / v3 / v4. `update_history_record_fields(path, video_id, **patch)` helper added for atomic single-record updates without rewriting the full file model.
- **PyInstaller spec** — bundles `PySide6.QtMultimedia` + `QtMultimediaWidgets` and the multimedia plugin DLLs (`windowsmediaplugin.dll`, `ffmpegmediaplugin.dll`). Fallback handles both `plugins/multimedia` and legacy `Qt/plugins/multimedia` wheel layouts.
- **28 new tests** (`test_history_records.py` v4 suite + `test_library_player.py`); 455 total pass repo-wide.

### Notes
- Schema bump is forward-compat: a v4 file loads cleanly on a v4 binary; downgrading to a pre-v4 binary returns an empty list (documented behavior matching the v2→v3 path).
- Manual clean-VM smoke for the frozen exe is deferred to the next release build (per phase-04 plan).

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
