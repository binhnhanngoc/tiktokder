# TikTok & Facebook Batch Video Downloader

A Python desktop and CLI tool for batch-downloading videos from TikTok and Facebook without watermarks. Dual interface: PySide6 GUI or CLI with Rich progress UI.

**v1.1.0** | Python 3.10+ | Cross-platform (Windows/macOS/Linux)

## Features

- **Dual Interface** — Desktop GUI (PySide6) and CLI (Rich + Argparse)
- **Multi-platform** — TikTok videos and Facebook videos in single batch
- **Download Modes** — Single URL, batch files, user profiles, Facebook pages
- **Channel Browsing** — Discover and download from TikTok channels via GUI
- **Concurrent Downloads** — ThreadPoolExecutor with configurable workers (default: 3)
- **Duplicate Detection** — Filesystem scan; auto-skip already-downloaded videos
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

## Examples

Download 5 videos concurrently to a custom folder:
```bash
python main.py --batch urls.txt --output ./my_videos --workers 5
```

Download a user's profile with 2-second delay between requests:
```bash
python main.py --user @tiktok --delay 2.0
```

## How It Works

1. **URL Validation**: Validates TikTok and Facebook URLs using regex patterns
2. **Platform Detection**: Automatically detects whether URL is TikTok or Facebook
3. **Batch Processing**: Reads files, removes duplicates and comments, supports mixed platforms
4. **Skip Check**: Scans output directory to avoid re-downloading
5. **Concurrent Download**: Uses ThreadPoolExecutor for parallel downloads via yt-dlp
6. **Progress Tracking**: Displays real-time progress with Rich library
7. **Clean Output**: Video filenames include video ID and title

## Output

Videos are saved to the output directory (default: `./downloads/`) with filenames like:
```
1234567890_video_title.mp4
```

## Testing

Run the test suite:
```bash
pytest test_tiktokder.py -v
```

## Requirements

- Python 3.10+
- yt-dlp (for video extraction)
- Rich (for CLI progress UI)
- PySide6 (for desktop GUI)
- pytest (for testing)
- PyInstaller (for packaging)

See `requirements.txt` for exact versions.

## Error Handling

- **Invalid URLs**: Validated before download
- **Missing batch files**: Error message with file path
- **Network failures**: Logged per video; batch continues
- **Duplicate prevention**: Already-downloaded videos skipped automatically

## Notes

- Respects TikTok's rate limits with configurable `--delay`
- No API keys or credentials required
- Videos are downloaded without watermarks
- User profile downloads may take time depending on profile size

## License

MIT
