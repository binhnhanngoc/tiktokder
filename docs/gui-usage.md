# GUI Usage Guide

## Launching the GUI

```bash
python app.py
```

The TikTokDer desktop application opens with a tabbed interface. Supports TikTok and Facebook videos.

## Interface Overview

### Main Window
- **Tabs:** URL Input, Channel/Page Browser, Settings
- **Window Persistence:** Position and size automatically saved on close
- **Default Size:** 900x600 pixels

### Tab 1: URL Input

Download a single TikTok or Facebook video.

**Usage:**
1. Paste a video URL (TikTok or Facebook) into the input field
2. Click "Download"
3. Watch progress in the Download Table below

**Supported URLs:**
- TikTok video: `https://www.tiktok.com/@user/video/1234567890`
- TikTok short: `https://vt.tiktok.com/XXXXXX`
- Facebook video: `https://www.facebook.com/watch/?v=1234567890`
- Facebook reel: `https://www.facebook.com/reel/1234567890`

**Note:** Platform is auto-detected; no need to specify TikTok vs. Facebook.

### Tab 2: Channel/Page Browser

Browse and download videos from TikTok channels or Facebook pages.

**Usage:**
1. Enter a TikTok channel name (e.g., `@username`) or Facebook page name
2. Click "Search Channel"
3. View results in the table
4. Select videos and click "Download Selected"

**Features:**
- Auto-detect platform from input
- Channel/page metadata display (followers, bio)
- Video list with titles and descriptions
- Multi-select with checkboxes for batch download
- Supports mixed TikTok/Facebook in same batch

### Tab 3: Settings

Configure application behavior and rate limiting.

**Options:**
- **Output Directory** — Where videos are saved (default: `./downloads`)
- **Concurrent Workers** — Number of parallel downloads (default: 3, range: 1-10)
- **Delay Between Downloads** — Seconds between requests to avoid rate limiting (default: 1.0)
- **Cookie Browser** — (Placeholder for future authentication support)

**Tips:**
- Increase `Delay` if TikTok or Facebook blocks your requests
- Higher `Workers` speeds up batches but may trigger rate limiting
- Output directory can point to external drive for large collections

All settings persist to `~/.tiktokder/config.json` and sync between GUI and CLI.

## Download Progress Display

The Download Table shows real-time progress:
- Video ID and title
- Download status: "Pending", "Downloading", "Complete", "Failed"
- Progress percentage
- File size

Click the table row to view detailed information in the status bar.

## Error Handling

- **Invalid URL** — Error dialog with explanation
- **Network Error** — Download marked as "Failed"; continue with other videos
- **Permission Denied** — Check output directory permissions
- **Duplicate Download** — Video skipped if already in output directory

## Configuration Files

Settings are stored in: `~/.tiktokder/config.json`

Example:
```json
{
  "output_dir": "./downloads",
  "workers": 3,
  "delay": 1.0,
  "cookie_browser": null,
  "window_width": 900,
  "window_height": 600,
  "window_x": 100,
  "window_y": 100
}
```

## Keyboard Shortcuts

- **Ctrl+Q** — Quit application
- **Ctrl+S** — Open Settings tab
- **Enter** — Submit URL input (when focused)

## Tips & Troubleshooting

**Rate Limiting Issues:**
- If downloads fail with "access denied", increase `Delay` to 2.0+ seconds
- TikTok and Facebook may block rapid requests from same IP
- Reduce `Workers` if rate limiting persists

**Performance Optimization:**
- `Workers: 3` is default and balanced (5+ may trigger blocks)
- `Delay: 1.0` is safe for most platforms
- Check network speed for single-video downloads (5-30s typical)

**File Management:**
- Output directory must have write permissions
- Duplicate videos automatically skipped (filesystem-based)
- Filenames: `{video_id}_{title}.mp4`

**Multi-platform Batching:**
- Channel Browser auto-detects TikTok vs. Facebook from input
- Single batch can mix TikTok and Facebook URLs
- All videos saved to same output directory
