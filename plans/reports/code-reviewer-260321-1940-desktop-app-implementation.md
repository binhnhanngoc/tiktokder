# Code Review: TikTokDer Desktop App Implementation

**Date:** 2026-03-21
**Reviewer:** code-reviewer
**Scope:** 15 files (NEW: 12, MODIFIED: 3) | ~900 LOC new
**Tests:** 104 passed, 0 failed

## Overall Assessment

Solid first implementation. Clean architecture with proper separation of concerns across GUI components. Signal/slot wiring is correct. However, several thread safety issues and a potential memory leak need attention before production use.

---

## Critical Issues

### 1. Thread blocks GUI in `_on_worker_finished` (download_engine.py:117-118)

```python
if self._queue and self.delay > 0:
    QThread.msleep(int(self.delay * 1000))
```

`_on_worker_finished` is a slot called on the **main thread** (signal emitted from worker thread crosses thread boundary). `QThread.msleep()` here **freezes the entire GUI** for `delay` seconds after every download completes.

**Fix:** Use `QTimer.singleShot()` to schedule `_start_next` after delay:
```python
from PySide6.QtCore import QTimer

# Replace lines 117-120 with:
if self._queue:
    if self.delay > 0:
        QTimer.singleShot(int(self.delay * 1000), self._start_next)
    else:
        self._start_next()
else:
    self._start_next()  # Still need to check all_finished
```

### 2. Worker thread not properly cleaned up -- memory leak (download_engine.py:105-107)

```python
worker = self._active.pop(url, None)
if worker:
    worker.wait()
```

`worker.wait()` on main thread is blocking. After `wait()`, workers are never `deleteLater()`'d. QThread instances accumulate. Additionally, if download fails with exception before emitting `finished_download`, the worker stays in `_active` forever.

**Fix:**
- Call `worker.deleteLater()` after `worker.wait()`
- Wrap `download_video` call in `run()` with try/except to always emit `finished_download`

### 3. Cancellation via exception is fragile (download_engine.py:31)

```python
raise Exception("Download cancelled")
```

Raising a generic exception inside yt-dlp's progress hook relies on yt-dlp propagating it correctly. Some yt-dlp versions may catch and suppress it. The exception will propagate as a failed download, not a cancelled one -- no way to distinguish cancel from failure.

**Fix:** Use a custom exception class, catch it in `run()`, and emit a cancelled-specific result:
```python
class DownloadCancelled(Exception):
    pass

def run(self):
    try:
        result = download_video(...)
        self.finished_download.emit(self.url, result)
    except DownloadCancelled:
        result = DownloadResult(url=self.url, success=False, error="Cancelled")
        self.finished_download.emit(self.url, result)
    except Exception as e:
        result = DownloadResult(url=self.url, success=False, error=str(e))
        self.finished_download.emit(self.url, result)
```

---

## High Priority

### 4. Settings changes don't propagate to running engine (settings_panel.py + main_window.py)

`SettingsPanel._save()` updates `self.config` and persists to disk, but `DownloadEngine` was created with initial config values. Changing workers/delay/output_dir in settings has **zero effect** on active engine. User will be confused.

**Fix:** Either:
- Emit a `settings_changed` signal from `SettingsPanel`, connect in `MainWindow` to update `engine.max_workers`, `engine.output_dir`, `engine.delay`
- Or at minimum, display a note: "Changes take effect on next app launch"

### 5. `_total_count` bookkeeping is wrong (download_engine.py:83)

```python
self._total_count += len(urls)
```

This adds ALL urls including skipped ones to total count, but skipped URLs never enter `_queue`. The total includes skipped, but `_completed_count` only increments for actual worker completions. These counters will never reconcile. Currently `_total_count` is unused externally, but it's a latent bug.

### 6. Duplicate URL handling missing in engine (download_engine.py:73-85)

If user pastes same URL twice, it enters the queue twice. Workers will both start, both download, both write to the same file. No dedup check.

**Fix:** Track queued/active URLs in a set; skip duplicates in `add_urls()`.

### 7. `_rebuild_mappings` is O(n^2) and fragile (download_table.py:211-236)

After clearing completed rows, it does nested iteration through old mappings and string matching against display text. If title was updated from URL to actual title, the mapping breaks (line 228 compares against both URL and title but `data.get("title")` is never set in `_row_data`).

**Fix:** Store URL as data on the `QTableWidgetItem` via `setData(Qt.ItemDataRole.UserRole, url)` instead of reverse-mapping from display text.

---

## Medium Priority

### 8. No URL validation in channel browser (channel_browser.py:76-78)

`_on_browse()` accepts any text and passes it directly to `yt_dlp.YoutubeDL.extract_info()`. No `is_channel_url()` validation.

**Fix:** Validate with `is_channel_url()` before fetching, show error label if invalid.

### 9. `ChannelFetcher` thread not cleaned up on widget destroy (channel_browser.py:90)

`self._fetcher` is parented to `self`, but if widget is destroyed while fetcher is running, QThread destruction while running causes undefined behavior (typically a crash/warning).

**Fix:** Override `closeEvent` or use `destroyed` signal to cancel and wait for fetcher.

### 10. Red border style never resets (url_input_panel.py:64)

When invalid URL entered, border turns red. But no code resets it -- next valid URL submission still shows red border.

**Fix:** Reset stylesheet at start of `_on_add()`:
```python
self.url_input.setStyleSheet("")
```

### 11. Config file race condition (config.py)

If two instances of the app run simultaneously, `save_config` and `save_history` can corrupt JSON (no file locking). Low probability but worth noting.

### 12. Window geometry restore can place window off-screen

`_restore_geometry()` in `main_window.py:149-153` restores saved x/y position. If user disconnected a monitor, window may be invisible.

**Fix:** Validate position against `QApplication.screens()` geometry before restoring.

---

## Low Priority

### 13. Unused imports (download_table.py:3-5)

`os`, `subprocess`, `sys` imported but never used.

### 14. `__dataclass_fields__` access (config.py:35)

Uses internal `__dataclass_fields__` attribute. Use `dataclasses.fields(AppConfig)` instead:
```python
known = {f.name for f in fields(AppConfig)}
```

### 15. PyInstaller spec missing yt-dlp hidden imports

`tiktokder.spec` only lists PySide6 hidden imports. yt-dlp extractors are dynamically loaded and may need explicit inclusion for frozen builds.

---

## Security

- **URL handling:** URLs are validated via regex before GUI submission. Channel fetcher lacks validation (see #8). No injection risk as URLs are passed to yt-dlp, which handles them safely.
- **Cookie browser option:** Exposes browser cookie access to yt-dlp. Acceptable since yt-dlp does this natively. No user credential exposure.
- **File path handling:** Output directory comes from user config, no path traversal risk.
- **No secrets exposed:** Config stored in `~/.tiktokder/`, no API keys.

---

## Positive Observations

- Clean dataclass-based config with forward/backward compatible JSON persistence
- Proper signal/slot architecture; no direct cross-thread method calls
- History dedup prevents re-downloading known videos
- Good test coverage for config, channel fetcher, and engine logic
- Cancellation support at both individual and queue level
- Context menu with copy URL and retry functionality

---

## Recommended Actions (Priority Order)

1. **[CRITICAL]** Replace `QThread.msleep` with `QTimer.singleShot` in engine (GUI freeze)
2. **[CRITICAL]** Add `deleteLater()` for finished workers (memory leak)
3. **[CRITICAL]** Wrap worker `run()` in try/except to always emit `finished_download`
4. **[HIGH]** Add settings-changed propagation or restart notice
5. **[HIGH]** Add duplicate URL dedup in engine
6. **[HIGH]** Fix `_rebuild_mappings` to use `UserRole` data instead of text matching
7. **[MEDIUM]** Validate channel URL before fetching
8. **[MEDIUM]** Reset red border on valid input
9. **[MEDIUM]** Clean up fetcher thread on widget destruction
10. **[LOW]** Remove unused imports, use `fields()` API

---

## Metrics

| Metric | Value |
|--------|-------|
| Test Coverage | Good (104 tests, all passing) |
| Linting Issues | ~3 (unused imports) |
| Type Annotations | Consistent throughout |
| File Sizes | All under 250 lines |
| Error Handling | Moderate -- needs improvement in worker lifecycle |

---

## Unresolved Questions

- Should the app support drag-and-drop of batch files onto the window?
- Is there a max queue size consideration for very large channel profiles (1000+ videos)?
- Should `ChannelFetcher` support pagination/lazy loading for large channels?
