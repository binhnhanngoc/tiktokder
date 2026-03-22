# Phase 2: Core Implementation

## Overview
- **Priority:** High
- **Status:** Complete
- **Description:** Implement URL parser, downloader wrapper, and CLI entry point

## Key Insights
- yt-dlp handles TikTok extraction natively — no API keys needed
- Use `yt_dlp.YoutubeDL` as Python library, not subprocess
- yt-dlp supports `--flat-playlist` for user profile URL enumeration
- Rich console for progress bars and status output

## Requirements

### Functional
- Single URL download: `python main.py <url>`
- Batch from file: `python main.py --batch urls.txt`
- Profile scrape: `python main.py --user @username`
- Output dir control: `--output ./path`
- Concurrent downloads: `--workers N` (default 3)
- Skip already-downloaded videos by ID

### Non-Functional
- Graceful error handling per-video (don't abort batch on single failure)
- Rate limiting between requests (configurable delay)
- Clear progress output

## Related Code Files
- Create: `url_parser.py` (renamed from url-parser.py for Python import compat)
- Create: `downloader.py`
- Create: `main.py`

## Implementation Steps

### url_parser.py (~50 lines)
1. `validate_tiktok_url(url)` — regex check for valid TikTok video URLs
2. `extract_video_id(url)` — extract video ID from URL
3. `read_batch_file(filepath)` — read URLs from text file, skip empty/comment lines
4. `build_user_url(username)` — construct profile URL from @username

### downloader.py (~60 lines)
1. `get_ydl_opts(output_dir)` — return yt-dlp options dict:
   - `outtmpl`: `{output_dir}/%(id)s_%(title).50s.%(ext)s`
   - `format`: best video
   - `quiet`: True (use rich for output instead)
   - `no_warnings`: True
2. `download_video(url, output_dir)` — download single video with yt-dlp
   - Return success/failure status with video info
3. `download_batch(urls, output_dir, workers)` — concurrent downloads using `concurrent.futures.ThreadPoolExecutor`
   - Rich progress bar for overall batch progress
   - Per-video status (success/fail/skipped)
   - Configurable delay between downloads
4. `get_downloaded_ids(output_dir)` — scan output dir for already-downloaded video IDs

### main.py (~50 lines)
1. `argparse` CLI with:
   - Positional `url` (optional)
   - `--batch FILE` — batch file path
   - `--user USERNAME` — TikTok username
   - `--output DIR` — output directory (default: `./downloads`)
   - `--workers N` — concurrent workers (default: 3)
   - `--delay SECONDS` — delay between downloads (default: 1)
2. Validate inputs (must provide exactly one of: url, --batch, --user)
3. Build URL list from input source
4. Filter already-downloaded
5. Call `download_batch()`
6. Print summary (downloaded/failed/skipped counts)

## Todo List
- [x] Implement url_parser.py (~50 lines)
- [x] Implement downloader.py (~100 lines)
- [x] Implement main.py (~80 lines)
- [x] Manual test: single URL download
- [x] Manual test: batch file download

## Success Criteria
- Single URL downloads video without watermark
- Batch file processes all URLs with progress bar
- Profile URL resolves and downloads user videos
- Already-downloaded videos are skipped
- Failed downloads logged, don't crash batch

## Risk Assessment
| Risk | Mitigation |
|------|-----------|
| TikTok API changes break yt-dlp | Pin yt-dlp version, update regularly |
| Rate limiting | Configurable delay between downloads |
| Some videos watermark-only | Log warning, continue batch |

## Security Considerations
- Sanitize file paths from user input (--output, --batch)
- No shell injection via URLs (yt-dlp library, not subprocess)
- Don't log sensitive user data
