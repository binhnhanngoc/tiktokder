---
title: "Phase 07 — Engine wiring + polish (drag-drop, import/export)"
priority: P1
effort: 1h
status: planned
depends: [03, 04, 05, 06]
---

# Phase 07 — Engine Wiring + Polish

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ Polish features — wiring)
- Affected files: `download_engine.py`, `gui/main_window.py`, `gui/url_input_panel.py` (or new drag-drop overlay), `gui/history_tab.py`

## Overview
Connect everything: engine emits enriched `HistoryRecord` on each successful download; `engine.history_changed` signal triggers History tab refresh; Download tab accepts drag-and-drop URLs and `.txt` files; Import/Export buttons round-trip URL lists; live `settings_changed` propagates quality/subs/thumb to engine.

## Key Insights
- After a successful download, `_do_download` (Phase 02) returns the yt-dlp `info` dict — already contains `id`, `title`, `uploader`, `filename`/`requested_downloads[0].filepath`, `filesize_approx`, `height`. Engine wraps these into a `HistoryRecord`.
- Quality of the actual saved file: prefer `requested_downloads[0].height` if present; else fallback to user-selected quality (e.g. `1080p` literal).
- Drag-drop: `QWidget.setAcceptDrops(True)` on Download tab; override `dragEnterEvent`/`dropEvent`. Accept `text/uri-list` and `text/plain`.
- Import/Export uses existing `read_batch_file` for input parsing; export writes one URL per line with `# platform: uploader` header for each block.

## Requirements

### Functional
1. **Engine record persistence**
   - `DownloadResult` gains optional fields: `uploader`, `quality`, `file_path`, `size_bytes` (or attach to a `record: HistoryRecord | None = None`). New fields default to None — back-compat for CLI callers.
   - `DownloadEngine._on_worker_finished`: on success, build `HistoryRecord`, call `add_history_record(record)`, emit new `history_changed` signal.
   - Replace `self._history = load_history()` + `save_history(self._history)` with set+record dual-store: keep `self._history_ids` for fast O(1) dedup; persist via `add_history_record`.
2. **Settings → engine live propagation**
   - Engine `__init__` accepts `quality, write_subs, write_thumb, history_max_entries`.
   - `MainWindow._apply_settings` propagates the four new fields when `settings_changed` fires.
   - `DownloadWorker` reads `engine.quality / write_subs / write_thumb` (passed in constructor) and forwards to `download_video`.
3. **History tab live refresh**
   - `MainWindow` connects `engine.history_changed` → `history_tab.refresh()`.
   - On `remove_history_requested(video_id)`: load records → drop matching → save → call `refresh()`.
   - On `redownload_requested(url)`: call `engine.retry_url(url, force=True)` and switch to Download tab.
4. **Drag-and-drop on Download tab**
   - `MainWindow.download_tab.setAcceptDrops(True)`.
   - Override `dragEnterEvent` to accept `text/uri-list` (file URIs) and `text/plain`.
   - Override `dropEvent`: parse URLs from text; for any path ending `.txt`, read via `read_batch_file`. Add result to `engine.add_urls(...)`.
5. **Import / Export buttons in Download tab**
   - Two new `QPushButton`s in toolbar of `download_table.py` or above it: `Import URLs`, `Export URLs`.
   - Import: `QFileDialog.getOpenFileName` filtered to `*.txt` → `read_batch_file` → `engine.add_urls(urls)`.
   - Export: `QFileDialog.getSaveFileName` → write current queue + history URLs to `.txt` with `# platform: uploader` headers per block.

### Non-Functional
- `download_engine.py` ≤ 280 LOC after additions (currently 223).
- `main_window.py` ≤ 280 LOC after additions (currently 207).
- All hooks degrade gracefully if metadata missing (record fields default to None; History tab renders `—`).

## Architecture

### Record Build
```python
def _record_from_info(url: str, info: dict, quality_label: str) -> HistoryRecord:
    files = info.get("requested_downloads") or []
    file_path = files[0].get("filepath") if files else info.get("filename")
    height = files[0].get("height") if files else info.get("height")
    quality_str = f"{height}p" if isinstance(height, int) else quality_label
    return HistoryRecord(
        video_id=str(info.get("id", "")),
        platform=detect_platform(url),
        uploader=info.get("uploader") or info.get("channel"),
        title=info.get("title"),
        url=url,
        quality=quality_str,
        file_path=file_path,
        size_bytes=info.get("filesize") or info.get("filesize_approx"),
        downloaded_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    )
```

`_do_download` already returns the info dict; we just need to surface it through `DownloadResult`. Add `DownloadResult.info_extra: dict | None = None` (or thread `record` through). Decision: extend `DownloadResult` with `record: HistoryRecord | None`, keep all existing fields untouched.

### Drag-Drop
```python
class DownloadTab(QWidget):  # rename existing self.download_tab to a real class
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()
    def dropEvent(self, e):
        urls = []
        for u in e.mimeData().urls():
            local = u.toLocalFile()
            if local.endswith(".txt"):
                urls.extend(read_batch_file(local))
            else:
                urls.append(u.toString())
        if e.mimeData().hasText() and not e.mimeData().urls():
            for line in e.mimeData().text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        if urls:
            self.engine.add_urls(urls)  # parent injection or signal emit
```

To avoid circular ref, use a Qt signal `urls_dropped(list[str])` from a tiny `DownloadTab` widget; MainWindow connects to engine.

### Import/Export
```python
def export_urls(path: str, queue: list[str], history_records: list[HistoryRecord]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for url in queue:
            f.write(f"{url}\n")
        f.write("\n# === History ===\n")
        for r in history_records:
            f.write(f"# platform: {r.platform} uploader: {r.uploader}\n")
            f.write(f"{r.url}\n")
```

## Related Code Files

### To Modify
- `download_engine.py` — accept quality/subs/thumb in `__init__`, pass to `DownloadWorker`; emit `history_changed`; build and persist `HistoryRecord` instead of bare ID set.
- `downloader.DownloadResult` — add optional `record: HistoryRecord | None = None`.
- `downloader._do_download` / `download_video` — return record or info-extra alongside result so engine can build the record (alternative: engine builds from `DownloadWorker` if worker exposes the info dict — pick this; `DownloadWorker.finished_download` payload already includes `result`; extend it to include the info dict by storing it on the worker after the download completes).
- `gui/main_window.py` — wire `engine.history_changed` → `history_tab.refresh`; handle `redownload_requested`, `remove_history_requested`; instantiate a `DownloadTab` widget that emits `urls_dropped`; add Import/Export buttons.
- `gui/download_table.py` — add `Import URLs` / `Export URLs` buttons to toolbar (signals out, MainWindow handles).
- `gui/url_input_panel.py` — already accepts a single URL; no changes (drag-drop is on the parent Download tab, not the input row).

### To Create
- `gui/download_tab.py` (optional, ~80 LOC) — wraps `UrlInputPanel + DownloadTableWidget` and owns drag-drop + import/export plumbing. If skipped, fold into `main_window.py` (acceptable, but pushes MainWindow over 280 LOC; *prefer creating the wrapper*).

### Not Touched This Phase
- `path_builder.py`, `config.py` (Phase 01 already provides `add_history_record`).

## Implementation Steps
1. Extract `DownloadTab(QWidget)` from MainWindow inline layout — encapsulates URL input + table + import/export.
2. Add `urls_dropped(list[str])` signal; wire in MainWindow.
3. Override `dragEnterEvent` / `dropEvent`.
4. Add Import / Export buttons to `download_table.py` toolbar; emit `import_requested(str)` and `export_requested(str)` signals.
5. MainWindow handles import (`read_batch_file`, `engine.add_urls`) and export (queue + history records).
6. Modify `DownloadWorker.run` to keep the `info` dict on `self._info` after `download_video` returns; the worker's `finished_download` signal payload remains the same (`url, result`) — engine reads `worker._info` directly when wiring up callback. *Cleaner alternative:* make `download_video` return `(DownloadResult, dict | None)`; update CLI callers to unpack. **Pick the cleaner option.**
7. Engine constructs `HistoryRecord` from the info dict + URL + quality label; calls `add_history_record(record)`; emits `history_changed`.
8. MainWindow `_apply_settings` propagates `quality_default / write_subtitles / write_thumbnail` to `engine.quality / write_subs / write_thumb`.
9. MainWindow connects `engine.history_changed` → `history_tab.refresh`.
10. Wire `history_tab.redownload_requested` → `engine.retry_url(url, force=True)` + tab switch.
11. Wire `history_tab.remove_history_requested` → load records, filter, save, call refresh.
12. Run app smoke: drop a URL, verify record appears in History tab.
13. Run `pytest test_download_engine.py -v`.

## Todo
- [ ] Extract `gui/download_tab.py` wrapper.
- [ ] Drag-drop accept + parse.
- [ ] `urls_dropped` signal wired to `engine.add_urls`.
- [ ] Import/Export buttons + signals + handlers.
- [ ] `download_video` returns `(result, info)` tuple; CLI callers updated.
- [ ] Engine builds `HistoryRecord`, calls `add_history_record`, emits `history_changed`.
- [ ] Engine accepts quality/subs/thumb args.
- [ ] `MainWindow._apply_settings` propagates new fields.
- [ ] Wire `history_tab.refresh` to `engine.history_changed`.
- [ ] Wire history-tab signals (re-download, remove).
- [ ] Manual smoke: download → History row appears → drag-drop URL → exports/imports round-trip.

## Success Criteria
- Dropping a TikTok URL on Download tab adds it to queue.
- Dropping a `urls.txt` file imports all valid URLs.
- Export writes a file that imports cleanly back into a fresh session.
- Completing a download adds a row to History tab within 1s, with non-null fields where metadata available.
- Changing Settings quality from `Best` to `720p` and starting a new download produces a ≤720p file.
- `Re-download` from History switches to Download tab and re-queues with `force=True`.
- `Remove from history` removes the row and persists.
- `pytest test_download_engine.py -v` passes (including any new tests).

## Risk & Mitigation
- **`download_video` signature change breaks CLI** — keep return type as `DownloadResult` for public API, expose `(result, info)` via private helper `download_video_with_info`. CLI keeps single-value return.
- **`history_changed` storm during 100-URL batch** — emit per completion; tab debounces refresh (200ms `QTimer`).
- **Drag-drop on macOS file URIs use `file://`** — `QUrl.toLocalFile()` handles all platforms.
- **DownloadTab extraction touches MainWindow heavily** — keep it a thin wrapper; mainwindow keeps direct access to `download_tab.url_input`, `download_tab.download_table` properties for back-compat.

## Security
- Drag-dropped URLs validated via `validate_url` before queueing; invalid URLs silently dropped (consistent with batch-file behaviour).
- Imported `.txt` parsed via existing `read_batch_file` — comments and blank lines skipped.

## Next Steps
- Phase 08: tests + docs catch-up.
