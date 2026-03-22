# TikTok Batch Video Downloader

A Python CLI tool to batch-download TikTok videos without watermarks using `yt-dlp`.

## Features

- **Single URL downloads**: Download a video directly from a TikTok link
- **Batch file input**: Download multiple videos from a text file
- **User profile scraping**: Download all videos from a TikTok profile
- **Concurrent downloads**: Parallel processing with configurable worker threads
- **Skip duplicates**: Automatically skips already-downloaded videos
- **Rich progress UI**: Real-time download progress with color-coded status
- **Watermark removal**: Extracts clean video files via yt-dlp

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### Download a single video
```bash
python main.py "https://www.tiktok.com/@user/video/1234567890"
```

### Download from a batch file
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

### Download all videos from a user profile
```bash
python main.py --user @username
```

## CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `url` | Single TikTok video URL | — |
| `--batch FILE` | Path to text file with URLs (one per line) | — |
| `--user USERNAME` | TikTok username to scrape (with or without @) | — |
| `--output DIR` | Output directory for downloaded videos | `./downloads` |
| `--workers N` | Number of concurrent downloads | `3` |
| `--delay N` | Delay (seconds) between downloads | `1.0` |

**Note**: Use exactly one input mode (URL, `--batch`, or `--user`).

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

1. **URL Validation**: Validates TikTok URLs using regex patterns
2. **Batch Processing**: Reads files, removes duplicates and comments
3. **Skip Check**: Scans output directory to avoid re-downloading
4. **Concurrent Download**: Uses ThreadPoolExecutor for parallel downloads
5. **Progress Tracking**: Displays real-time progress with Rich library
6. **Clean Output**: Video filenames include video ID and title

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
- pytest (for testing)

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
