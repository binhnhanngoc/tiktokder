# Progress Bar & Loading Indicator UI Map

## Summary
The PySide6 GUI app uses **two primary QProgressBar instances** for progress feedback: one indeterminate marquee bar in the browser panels (showing network fetch activity) and per-row progress bars in the download queue table. No custom spinners or animated loaders. Theme support via `qdarktheme` + semantic token system with live OS appearance switching.

---

## 1. QProgressBar Usages

### A. Download Queue Table — Per-Row Progress Bars
**File:** `D:\Projects\tiktokder\gui\download_table.py`

- **Lines 122–125** (add_download): Creates a new progress bar for each queued URL.
  - Range: 0–100 (determinate mode)
  - Initial value: 0
  - Cell widget inserted into table column 2
  
- **Lines 142–144** (on_download_progress): Updates progress bar value (0–100) as download progresses.
  - Called via `download_progress` signal from `DownloadWorker` in `download_engine.py`
  
- **Lines 157–159** (on_download_finished): Sets bar to 100 on success.
  
- **Lines 401–404** (load_from_state): Restores progress bars from persisted state on app restart.
  - Complete downloads show 100%, others show 0%

### B. Browser Panel — Indeterminate "Busy" Bar
**File:** `D:\Projects\tiktokder\gui\base_browser_panel.py`

- **Lines 81–85** (constructor): Creates marquee-mode progress bar (range 0–0 = indeterminate).
  - No text display
  - Hidden by default
  
- **Line 162** (\_start_fetcher): Made visible when fetch begins
  
- **Line 202** (\_on_fetch_done): Hidden when fetch completes
  
- **Purpose:** Shows fetcher is running (yt-dlp/Playwright scraping videos); no byte-level progress available

---

## 2. Progress Value Update Paths

### Download Progress Flow
1. **DownloadWorker** (`download_engine.py:58`):
   - `progress.emit(url, pct)` — emits float (0–100)
   
2. **DownloadEngine** → routes to **MainWindow** (`main_window.py:151, 205`):
   - `download_progress.connect(self._route_progress)`
   
3. **MainWindow** → **PlatformTab.queue_panel** (`main_window.py:205`):
   - Routes to correct platform's DownloadTableWidget
   
4. **DownloadTableWidget.on_download_progress** (`download_table.py:138–144`):
   - Retrieves `QProgressBar` widget from table cell
   - Calls `setValue(int(percent))`

### Fetch Status Flow
- **BaseBrowserPanel** controls visibility only:
  - No value updates; marquee bar auto-animates when `range(0, 0)`
  - Visibility toggled via `setVisible(True/False)` at start/finish

---

## 3. Custom Progress Widgets
**None found.** The app uses only standard `QProgressBar`. No custom spinners, busy indicators, or animated loaders.

---

## 4. Per-Row / Per-Item Progress Display
**Yes, in download queue table:**
- Table widget: 4 columns (Title | Status | Progress | Size)
- Column 2 hosts a `QProgressBar` per row via `setCellWidget(row, 2, bar)`
- Each row tracks its own URL and progress independently
- Status text (Queued/Downloading/Complete/Failed/Skipped) shown in column 1 with token-resolved colors

---

## 5. Styling & Stylesheet Rules

### No Custom QSS Files
- No `.qss` files found in the project
- All styling delegated to **qdarktheme** (external library)

### Inline Styling
- **QProgressBar** bars: rely on qdarktheme defaults + PySide6 native rendering
- **Table text colors:** resolved via semantic tokens at paint time
  - Example: `download_table.py:180` → `token(_STATUS_TOKENS[status])`
  - Token system provides hex colors; applied via `item.setForeground(QColor(...))`

---

## 6. Theme Support

### Theme Bootstrap & Mode System
**File:** `gui/theme.py`

- **Startup:** `bootstrap(app, config)` called before window.show()
- **Modes:** "system" (OS auto-detect), "light", "dark"
- **Current mode:** `_current_mode` global; can be overridden by user via Settings

### OS Listener (System Mode)
- Daemon thread runs `darkdetect.listener()` when mode = "system"
- Emits `system_theme_changed` signal on OS appearance change
- Signal marshaled back to Qt main thread; re-applies theme via `apply()`

### Token Palette Resolution
**File:** `gui/tokens.py`

- **LIGHT palette:** 15 semantic color keys (white/bright grays/dark text/green/orange/red)
- **DARK palette:** 15 semantic color keys (dark/medium grays/light text/green/orange/red)
- **Runtime lookup:** `token(name)` returns hex color based on active `_mode`
- **No auto-repaint on mode switch:** Stylesheets built at construction time don't refresh; only widgets that call `token()` at paint-time respond to live theme changes

### QProgressBar Appearance
- Inherits qdarktheme stylesheet defaults (no custom overrides)
- Background, groove, and sub-page colors adapt to light/dark palette automatically via qdarktheme

---

## 7. Signal/Slot Connections Summary

| Signal Source | Emitter | Target | Handler | Line |
|---|---|---|---|---|
| `progress` | DownloadWorker | DownloadEngine | (internal queue) | download_engine.py:22 |
| `download_progress` | DownloadEngine | MainWindow | `_route_progress` | main_window.py:151, 205 |
| `download_progress` | MainWindow | DownloadTableWidget | `on_download_progress` | download_table.py:138 |
| `finished_fetch` | BaseBrowserPanel fetcher | BaseBrowserPanel | `_on_fetch_done` | base_browser_panel.py:202 |
| `fetch_started` / `fetch_finished` | BaseBrowserPanel | (SavedChannelsPanel) | visibility guards | base_browser_panel.py:48–49 |

---

## 8. No Found Issues
- Progress bars correctly range 0–100 (determinate) and 0–0 (indeterminate marquee)
- Theme switching via qdarktheme handles bar colors automatically
- Per-row isolation prevents cross-table interference
- Graceful fallback: missing bar widgets checked with `if bar:` before updates

---

## Files Summary
- **Progress components:** `download_table.py` (per-row bars), `base_browser_panel.py` (marquee bar)
- **Signaling:** `download_engine.py` (worker emissions), `main_window.py` (routing)
- **Theming:** `theme.py` (mode management), `tokens.py` (color resolution)
- **No QSS/stylesheet files**

**Total QProgressBar instances: 2 (one marquee in browser, N determinate in download table)**
