# Phase 4: Channel/Profile Video Listing

## Context
- [plan.md](plan.md) | [phase-03](phase-03-download-engine.md)
- Depends on: Phase 2, Phase 3

## Overview
- **Priority:** P1
- **Status:** complete
- **Description:** Browse a TikTok channel, list all videos with metadata, select which to download

## Key Insights
- yt-dlp `--flat-playlist` extracts video URLs from profile page without downloading
- yt-dlp `--dump-json` provides metadata (title, views, likes, duration, upload_date)
- Pagination may be limited (~20-30 videos) - document this limitation
- Rate limiting: 1-3s delays between metadata requests
- Cookie support (`--cookies-from-browser chrome`) improves reliability

## Requirements
### Functional
- Paste channel URL (e.g., `https://www.tiktok.com/@chg12.movie`), click "Browse"
- List all discovered videos in a table: thumbnail placeholder, title, duration, views, upload date
- Select/deselect individual videos via checkboxes
- "Select All" / "Deselect All" buttons
- "Download Selected" button sends selected URLs to DownloadEngine
- Loading spinner while fetching video list

### Non-functional
- Fetch runs in QThread (non-blocking UI)
- Handle errors gracefully (profile not found, rate limited)

## Architecture
```
gui/channel_browser.py (NEW)
  ├── QLineEdit for channel URL
  ├── QPushButton "Browse"
  ├── QTableWidget with columns: [checkbox, title, duration, views, date]
  ├── Select All / Deselect All / Download Selected buttons
  └── Uses ChannelFetcher worker

channel_fetcher.py (NEW)
  ├── ChannelFetcher(QThread)
  │   ├── Uses yt-dlp --flat-playlist + --dump-json
  │   ├── Emits video_found(dict) per video
  │   └── Emits finished(total_count)
  └── VideoInfo dataclass: url, title, duration, views, upload_date, video_id
```

## Related Code Files
### Modify
- `url_parser.py` - add `is_channel_url()` (if not done in phase 2)

### Create
- `channel_fetcher.py` - QThread worker for yt-dlp profile extraction
- `gui/channel_browser.py` - channel browsing UI widget

## Implementation Steps
1. Create `VideoInfo` dataclass in `channel_fetcher.py`:
   - Fields: `url`, `title`, `duration`, `view_count`, `upload_date`, `video_id`
2. Create `ChannelFetcher(QThread)`:
   - Input: channel_url, optional cookies_from_browser
   - Use yt-dlp with `extract_flat='in_playlist'` to get video URLs
   - For each entry, extract metadata from the flat extraction info
   - Emit `video_found(VideoInfo)` signal per video
   - Emit `finished()` when done
   - Emit `error(str)` on failure
   - Respect delay between requests
3. Create `gui/channel_browser.py`:
   - Channel URL input + Browse button at top
   - QTableWidget below with checkbox column
   - Populate table rows as `video_found` signals arrive
   - Select All / Deselect All toggle buttons
   - Download Selected button: collect checked URLs, emit `download_requested(list[str])` signal
   - Show loading indicator during fetch
4. Wire channel browser tab in MainWindow:
   - Connect `download_requested` to DownloadEngine.add_urls

## Todo
- [x] Create VideoInfo dataclass
- [x] Implement ChannelFetcher QThread
- [x] Implement gui/channel_browser.py widget
- [x] Wire into MainWindow channel tab
- [x] Test with real TikTok profile URL

## Success Criteria
- Paste channel URL, click Browse, videos appear in table
- Can select/deselect videos
- "Download Selected" sends URLs to download queue
- Loading indicator shown during fetch
- Errors displayed gracefully

## Risk Assessment
- yt-dlp may only return 20-30 videos for large profiles (TikTok pagination limit)
  - Mitigation: document limitation, show count, consider adding cookie support toggle
- Rate limiting may cause failures
  - Mitigation: configurable delay, retry logic
