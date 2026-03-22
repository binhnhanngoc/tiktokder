# Phase 3: Download Engine Refactor (QThread Integration)

## Context
- [plan.md](plan.md) | [phase-02](phase-02-core-gui-window.md)
- Depends on: Phase 1
- Current `downloader.py` uses ThreadPoolExecutor + Rich progress (CLI-coupled)

## Overview
- **Priority:** P1
- **Status:** complete
- **Description:** Extract download logic from Rich UI dependency, create QThread-based engine with Qt signals

## Key Insights
- Current `download_video()` is clean and reusable (no UI coupling)
- `download_batch()` is tightly coupled to Rich Progress - need to decouple
- QThread + signals pattern: worker emits progress, UI slot updates table
- Keep `download_batch()` working for CLI (backward compat)

## Requirements
### Functional
- `DownloadWorker(QThread)`: downloads single video, emits progress signals
- `DownloadEngine`: manages queue of DownloadWorkers, respects max workers
- Signals: `download_started(url)`, `download_progress(url, percent)`, `download_finished(url, DownloadResult)`, `all_finished()`
- Support cancel/pause per download and globally

### Non-functional
- No UI imports in engine (pure Qt Core signals)
- Thread-safe queue management

## Architecture
```
downloader.py (unchanged - CLI still uses download_batch)
  └── download_video() - shared core function

download_engine.py (NEW)
  ├── DownloadWorker(QThread)
  │   ├── signals: started, progress, finished, error
  │   └── uses download_video() internally
  └── DownloadEngine(QObject)
      ├── add_to_queue(url)
      ├── start() / pause() / cancel()
      ├── signals: queue_updated, all_finished
      └── manages worker pool (max_workers from config)
```

## Related Code Files
### Modify
- `downloader.py` - add progress_hook callback parameter to `download_video()`

### Create
- `download_engine.py` - QThread workers + engine manager

## Implementation Steps
1. Refactor `download_video()` in `downloader.py`:
   - Add optional `progress_hook: Callable | None = None` parameter
   - Pass hook to yt-dlp opts as `progress_hooks` list
   - CLI path unaffected (hook=None)
2. Create `download_engine.py`:
   - `DownloadSignals(QObject)` with pyqtSignal definitions
   - `DownloadWorker(QThread)`:
     - Takes url, output_dir
     - Calls `download_video()` with progress hook that emits signals
     - Emits `finished(url, DownloadResult)` on completion
   - `DownloadEngine(QObject)`:
     - Internal queue (list of URLs)
     - Active workers dict (url -> DownloadWorker)
     - `add_urls(urls: list[str])` - add to queue
     - `start()` - spawn workers up to max_workers
     - `_on_worker_finished()` - start next from queue
     - `cancel_all()` - terminate all workers
     - Respects delay between downloads
3. Ensure `download_batch()` in downloader.py still works for CLI

## Todo
- [x] Add progress_hook param to download_video()
- [x] Create DownloadWorker QThread class
- [x] Create DownloadEngine manager class
- [x] Test signals fire correctly
- [x] Verify CLI still works after refactor

## Success Criteria
- `download_video(url, dir, progress_hook=callback)` invokes callback with percentage
- DownloadEngine processes queue, emits signals per download
- `python main.py` still works identically

## Risk Assessment
- yt-dlp progress_hooks format: `{'status': 'downloading', 'downloaded_bytes': N, 'total_bytes': N}` - must parse correctly
- Thread termination: QThread.terminate() is unsafe; use flag-based cancellation
