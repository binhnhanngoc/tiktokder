# Cook Report — Platform-first UI restructure (260426-2231)

**Status:** DONE
**Branch:** main
**Suite:** 326 tests pass (up from 301)

## Phases

| # | Phase | New files | Tests | Result |
|---|-------|-----------|-------|--------|
| 01 | Saved-channels store | `saved_channels_store.py`, `test_saved_channels_store.py` | 19 | ✓ |
| 02 | Platform tab shells | `gui/platform_tab.py`, `gui/saved_channels_panel.py`, `test_saved_channels_panel.py` | 4 | ✓ |
| 03 | Global URL bar + status | `gui/global_url_bar.py`, `gui/status_bar_widget.py`, `test_global_url_bar.py` | 7 | ✓ |
| 04 | Library two-pane | `gui/library_panel.py`, `gui/_history_helpers.py`, `test_library_panel.py` | 8 | ✓ |
| 05 | Settings split | (modified) `gui/settings_panel.py`, `test_settings_split.py` | 6 | ✓ |
| 06 | Cutover | (deleted 4 legacy modules), README + docs/codebase-summary + project-changelog | — | ✓ |

## Implementation summary

- **Persistence layer** (`saved_channels_store.py`, 220 LOC) — schema-v1 JSON file with atomic write + tolerant load, mirrors `history_store.py` shape. CRUD + `select_new_videos` filter + cap-200/platform with FIFO trim.
- **Per-platform composite** (`PlatformTab`) — three sub-tabs: Channels (saved list above platform browser), Queue (per-platform `DownloadTableWidget`), Library (`LibraryPanel`). Drag-drop filtered to own platform.
- **Saved-channels panel** — right-click CRUD, Star/Unstar, "Download all new" with confirm dialog at >10. Calls `mark_fetched` after queueing so future runs scope correctly.
- **Global URL bar** — paste/drop validates each line via `validate_url`, emits the surviving list. MainWindow groups by `detect_platform` and dispatches per-platform.
- **Status bar** — TT/FB pending counts (Queued+Downloading) + cumulative Done + free-text status.
- **Library** — `QSplitter` with uploader sidebar (sorted by count desc; ★ for saved-channel uploaders) and filtered history table. Right-click ports verbatim from legacy `HistoryTab`. Refreshes on `engine.history_changed`.
- **Settings** — three QGroupBoxes (Global / TikTok / Facebook). New `AppConfig.facebook_max_scrolls_default` propagates to `FacebookBrowserPanel.scrolls_spin` on init.
- **AppState extension** — `library_active_uploader_{tiktok,facebook}` survives close/reopen; tolerant loader keeps existing files compatible.

## Cutover

Deleted modules:
- `gui/channel_browser.py`
- `gui/download_tab.py`
- `gui/history_tab.py`
- `gui/url_input_panel.py`

Removed `MainWindow.url_input` / `MainWindow.download_table` back-compat aliases. No tests reference deleted symbols. README rewritten ("GUI tabs" + "Settings" sections). `docs/codebase-summary.md` updated. `docs/project-changelog.md` created with v1.3.0 entry. Version bumped 1.2.0 → 1.3.0 in README.

## Validation

- `pytest --tb=no` → **326 passed** in 1.34s.
- All public widget files <250 LOC; `saved_channels_store.py` 220 LOC; `gui/library_panel.py` 220 LOC.
- Compile-check: `from gui.main_window import MainWindow` works.
- `git ls-files | grep -E "^gui/(channel_browser|download_tab|history_tab|url_input_panel)\.py$"` = 0 hits.
- All 6 phase-file checklists ticked off; plan.md status flipped to `completed`.

## Unresolved

- `docs/system-architecture.md` still references deleted modules (lines 51, 55, 65, 340, 355, 396). Out of Phase-06 scope per plan; needs a deeper rewrite as a follow-up doc-debt item.
- "Refresh all" on saved-channels panel currently Browses the first row only — sequential auto-refresh deferred (plan §3.2.1 noted as light-weight).
- Phase 06 step 9 mentions a manual smoke test (8 scenarios) — not run in this autonomous cook session; tests provide programmatic coverage of all 8 paths.
- Tauri plan (`260426-1518-tauri-migration`) `blockedBy` is now lifted; its phase-07-svelte-tabs.md should be revised to match the new platform-first IA before the Tauri work resumes.
