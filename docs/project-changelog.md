# Project Changelog

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
