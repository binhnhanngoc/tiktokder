# TikTok & Facebook Batch Video Downloader

A Python desktop and CLI tool for batch-downloading videos from TikTok and Facebook without watermarks. Dual interface: PySide6 GUI or CLI with Rich progress UI.

**v1.2.0** | Python 3.10+ | Cross-platform (Windows/macOS/Linux)

## Features

- **Dual Interface** — Desktop GUI (PySide6) and CLI (Rich + Argparse)
- **Multi-platform** — TikTok videos and Facebook videos in single batch
- **Download Modes** — Single URL, batch files, user profiles, Facebook pages
- **Channel Browsing** — Dedicated **TikTok** and **Facebook** sub-tabs in the GUI, each with independent URL state and a quality column
- **History Tab** — Browse every downloaded video with rich metadata (title, platform, uploader, quality, size, date, path); filter by platform or live search; right-click to open file, open folder, re-download, copy URL, or remove
- **Quality Selector** — Default Quality setting (`Best`, `1080p`, `720p`, `480p`, `Audio only`) plus optional subtitle (`en`) and thumbnail downloads
- **Concurrent Downloads** — ThreadPoolExecutor with configurable workers (default: 3)
- **Per-uploader Folder Layout** — Output organized as `downloads/{platform}/{uploader}/{id}_{title}.{ext}`
- **Drag-and-drop & Import/Export** — Drop URLs or `.txt` files onto the Download tab; round-trip via Import/Export buttons
- **Duplicate Detection** — Recursive filesystem scan; auto-skip already-downloaded videos (works across the new tree and any legacy flat-root files)
- **Real-time Progress** — GUI table updates + CLI progress bar with percentages
- **Rate Limiting** — Configurable inter-request delay to respect platform limits
- **Watermark Removal** — yt-dlp extraction for clean output

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### Launch the GUI
```bash
python app.py
```

GUI tabs:
- **Download** — single URL bar, queue table, drag-drop URLs or `.txt` files, Import/Export buttons.
- **Channel / Page** — TikTok sub-tab (yt-dlp flat playlist) and Facebook sub-tab (Playwright scraping). Each preserves URL + table state when switching.
- **History** — full record list with search, platform filter, stats, right-click actions.
- **Settings** — output folder, concurrency, delay, cookie browser, default quality, subtitles toggle, thumbnail toggle.

### Drag and drop

Drop a TikTok or Facebook URL anywhere on the Download tab to add it to the queue. Drop a `.txt` batch file to import all URLs from it. Invalid URLs are silently dropped (consistent with batch-file parsing).

### Command-line interface (CLI)

#### Download a single video
```bash
python main.py "https://www.tiktok.com/@user/video/1234567890"
```

#### Download from a batch file
Create `urls.txt` with one URL per line:
```
https://www.tiktok.com/@user1/video/1111111111
https://www.tiktok.com/@user2/video/2222222222
# Comments are ignored
```

Then run:
```bash
python main.py --batch urls.txt
```

#### Download all videos from a user profile
```bash
python main.py --user @username
```

#### Download all videos from a Facebook page
```bash
python main.py --facebook-page "https://www.facebook.com/pagename"
```

## CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `url` | Single TikTok or Facebook video URL | — |
| `--batch FILE` | Path to text file with URLs (one per line, mixed platforms) | — |
| `--user USERNAME` | TikTok username to scrape (with or without @) | — |
| `--facebook-page PAGE_URL` | Facebook page URL to scrape videos from | — |
| `--output DIR` | Output directory for downloaded videos | `./downloads` |
| `--workers N` | Number of concurrent downloads | `3` |
| `--delay N` | Delay (seconds) between downloads | `1.0` |

**Note**: Use exactly one input mode (URL, `--batch`, `--user`, or `--facebook-page`).

## Settings (GUI)

| Setting | Values | Notes |
|---------|--------|-------|
| Output Directory | path | per-uploader subfolders are created automatically |
| Concurrent Downloads | 1–10 | platform-aware pacing applies on top |
| Delay Between Downloads | 0.0–10.0 s | gaussian jitter applied per platform |
| Cookie Browser | None / chrome / firefox / edge | TikTok yt-dlp cookies — auto-extracted from your browser |
| Facebook Cookies File | path to Netscape `cookies.txt` (optional) | lifts the **10-reel cap** on anonymous FB profile scraping. Export with a browser extension like *Get cookies.txt LOCALLY* while logged in to facebook.com, then point here. Use a burner FB account if possible — scraping technically violates FB ToS |
| Default Quality | `Best`, `1080p`, `720p`, `480p`, `Audio only` | audio-only writes `.m4a` (requires ffmpeg) |
| Write subtitles (en) | on / off | sidecar `.srt` next to the video |
| Write thumbnail | on / off | sidecar `.jpg` next to the video |

All settings auto-save and propagate to in-flight engine state on change.

## Output

Videos are saved under the output directory (default: `./downloads/`) using a platform-aware tree:
```
downloads/
├── tiktok/
│   ├── @user1/
│   │   └── 1234567890_video_title.mp4
│   └── unknown_uploader/
│       └── 7234567899_orphan.mp4
└── facebook/
    └── pagename/
        └── 12345678_video.mp4
```

Filenames keep the `{video_id}_{title}.ext` shape so legacy flat-root files (from prior versions) remain dedup-recognized.

## History

`data/history.json` persists rich `HistoryRecord` rows (schema v2) including platform, uploader, quality, size, downloaded-at timestamp, and file path. Old v1 files (a list of bare IDs) are auto-migrated on first write — no data is lost.

A soft FIFO cap of **10 000** entries trims oldest metadata when exceeded; downloaded files on disk are untouched. Configurable via `AppConfig.history_max_entries`.

## Testing

Run the test suite:
```bash
pytest -v
```

## Requirements

- Python 3.10+
- yt-dlp (for video extraction)
- Rich (for CLI progress UI)
- PySide6 (for desktop GUI)
- Playwright (optional — required only for Facebook page scraping)
- pytest (for testing)
- PyInstaller (for packaging)

See `requirements.txt` for exact versions.

## Error Handling

- **Invalid URLs**: Validated before download
- **Missing batch files**: Error message with file path
- **Network failures**: Logged per video; batch continues
- **Duplicate prevention**: Already-downloaded videos skipped automatically
- **Login walls**: detected and surfaced fast on Facebook to preserve retry budget
- **Missing ffmpeg**: warned once; most non-merge downloads still succeed

## Notes

- Respects platform rate limits with platform-aware gaussian pacing (`--delay` is a mean)
- No API keys or credentials required
- Videos are downloaded without watermarks
- User profile downloads may take time depending on profile size

## License

MIT
