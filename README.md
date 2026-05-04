# TikTok & Facebook Batch Video Downloader

A Python desktop and CLI tool for batch-downloading videos from TikTok and Facebook without watermarks. Dual interface: PySide6 GUI or CLI with Rich progress UI.

**v1.9.0** | Python 3.10+ | Cross-platform (Windows/macOS/Linux)

## Features

- **Dual Interface** — Desktop GUI (PySide6) and CLI (Rich + Argparse)
- **Multi-platform** — TikTok videos and Facebook videos in single batch
- **Download Modes** — Single URL, batch files, user profiles, Facebook pages
- **Platform-First UI** — Top-level **TikTok** and **Facebook** tabs, each with Channels (saved list) / Queue / Library sub-tabs; persistent global URL bar auto-routes pasted URLs by platform; status bar shows per-platform queue + done badges
- **Saved Channels** — Save channels/pages with optional nicknames; right-click for `Download all new` (filters out already-downloaded and pre-cutoff videos)
- **Library View** — Per-platform 3-pane: uploader sidebar (★ marks saved channels), sortable/filterable history table with a thumbnail column, and a right-side preview pane showing the large thumbnail, metadata, and full description; filter by quality / date range / size / file status; search box matches title, uploader, URL, and description text; right-click rows to open file, open folder, re-download, copy URL, or remove
- **Channel Browse Filters** — TikTok and Facebook channel browse tables include a search box, Quality dropdown, From/To date range, sortable headers, plus a Downloaded filter (`All` / `New only` / `Downloaded only`) and a sortable `✓` marker column with download-timestamp tooltip. The combo state persists per platform across relaunches and refreshes live as new downloads complete. Select All / Download Selected respect the active filter — hidden rows are never queued by accident
- **Quality Selector** — Default Quality setting (`Best`, `1080p`, `720p`, `480p`, `Audio only`) plus optional subtitle (`en`) downloads (thumbnails are always written as sidecars next to each video so the Library can show previews)
- **Concurrent Downloads** — ThreadPoolExecutor with configurable workers (default: 3)
- **Per-uploader Folder Layout** — Output organized as `downloads/{platform}/{uploader}/{title} [{short_id}].{ext}`. The 6-char ID suffix uniquifies same-title videos; legacy `{id}_{title}.{ext}` files from prior versions remain dedup-recognized.
- **Drag-and-drop** — Drop URLs or `.txt` files onto the global URL bar or platform tabs to queue downloads
- **Duplicate Detection** — Recursive filesystem scan; auto-skip already-downloaded videos (works across the new tree and any legacy flat-root files)
- **Real-time Progress** — GUI table updates + CLI progress bar with percentages
- **Rate Limiting** — Configurable inter-request delay to respect platform limits
- **Watermark Removal** — yt-dlp extraction for clean output
- **In-App Help** — `Help` menu (or `F1`) opens a tabbed manual: getting started, cookie export/configure walkthroughs, channels & library, troubleshooting, keyboard shortcuts, and about. Non-modal so you can follow steps while your browser is open.

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
- **TikTok** — Channels (saved list + browser), Queue (TikTok-only download table), Library (uploader sidebar + filtered history).
- **Facebook** — same composite for Facebook pages/profiles, with Playwright scraping under the hood. Scrolls spinbox (1–50, default 10) for Playwright scrape budget; "Load more" button to resume.
- **Settings** — Global / TikTok / Facebook sections (output folder, concurrency, default quality, cookie browser, TikTok + FB cookies.txt, FB default scrolls, etc.).

A persistent global URL bar at the top (above tabs) accepts pasted URLs or `.txt` drops; URLs auto-route to the matching platform's queue. The status bar shows per-platform queue counts and total completed downloads.

### Drag and drop

Drop a TikTok or Facebook URL on the global URL bar (above tabs) to add it to the queue. Drop a `.txt` batch file to import all URLs from it; mixed-platform files split correctly. You can also drag URLs onto a specific platform tab to load them into that tab's queue. Invalid URLs are silently dropped (consistent with batch-file parsing).

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

Settings are split into three groups: **Global**, **TikTok**, **Facebook**. All settings auto-save and propagate to in-flight engine and UI state on change.

| Group | Setting | Values | Notes |
|-------|---------|--------|-------|
| Global | Appearance | System / Light / Dark | applies immediately |
| Global | Output Directory | path | per-uploader subfolders created automatically |
| Global | Concurrent Downloads | 1–10 | platform-aware pacing applies on top (TT default 3, FB default 1) |
| Global | Delay Between Downloads | 0.0–10.0 s | gaussian jitter applied per platform (TT 1.5s, FB 3.0s mean) |
| Global | Default Quality | Best / 1080p / 720p / 480p / Audio only | audio-only requires ffmpeg; writes `.m4a` |
| Global | Write subtitles (en) | on / off | sidecar `.srt` next to video |
| TikTok | Cookie Browser | None / chrome / firefox / edge | auto-extracts session cookies from your browser |
| TikTok | Cookies File | path to Netscape `cookies.txt` | optional; **overrides Cookie Browser** when set. Lifts anonymous rate limits on profile scrapes/downloads. Export via *Get cookies.txt LOCALLY* extension while logged in |
| Facebook | Cookies File | path to Netscape `cookies.txt` | optional; lifts **10-reel cap** on anon profile scraping. Export via *Get cookies.txt LOCALLY* extension while logged in |
| Facebook | Default Max Scrolls | 1–50 | Playwright scroll budget in Channels/Browser sub-tab |

_Note: Thumbnails are always written as sidecar `.jpg`/`.webp` next to each video so the Library can show previews. The toggle was removed in v1.4.0._

## Output

Videos are saved under the output directory (default: `./downloads/`) using a platform-aware tree:
```
downloads/
├── tiktok/
│   ├── @user1/
│   │   └── video title [aB3xY9].mp4
│   └── unknown_uploader/
│       └── orphan clip [c1d2e3].mp4
└── facebook/
    └── pagename/
        └── reel description [f4g5h6].mp4
```

Filenames lead with the title and append a 6-char bracketed ID suffix to uniquify same-title videos. Legacy `{video_id}_{title}.ext` files from prior versions remain dedup-recognized via filename regex; new files are dedup-recognized via `history.json`.

## History

`data/history.json` persists rich `HistoryRecord` rows (schema v3) including platform, uploader, quality, size, downloaded-at timestamp, file path, and the new **description** + **thumbnail_path** fields surfaced in the Library preview pane. Old v1 (list of bare IDs) and v2 files are auto-migrated on first write — no data is lost.

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
