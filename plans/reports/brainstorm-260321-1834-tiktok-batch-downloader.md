# Brainstorm: TikTok Batch Video Downloader

**Date:** 2026-03-21
**Status:** Concluded

## Problem Statement
Build a Python CLI script to batch-download TikTok videos without watermark. Must support single URL, batch file input, and user profile scraping.

## Evaluated Approaches

### 1. yt-dlp (Python library) — SELECTED
- **How:** Use yt-dlp as Python library with built-in TikTok extractor
- **Pros:** No API keys, battle-tested, auto watermark-free preference, built-in batch/retry/rate-limiting, active community
- **Cons:** TikTok API changes can temporarily break it; watermark-free not 100% guaranteed
- **Complexity:** Low (~50-100 lines)

### 2. TikWM API (third-party)
- **How:** Call tikwm.com API for no-watermark URLs, download with requests
- **Pros:** Reliable watermark removal, simple JSON API
- **Cons:** Third-party dependency, privacy concerns, can go down anytime
- **Complexity:** Low-Medium

### 3. Browser automation (Playwright/Selenium)
- **How:** Headless browser to extract video source URLs
- **Pros:** Works even when APIs change
- **Cons:** Slow, resource-heavy, overkill
- **Complexity:** High

## Final Recommendation: yt-dlp

### Architecture
```
tiktokder/
├── main.py              # CLI entry point (argparse)
├── downloader.py        # yt-dlp wrapper, download logic
├── url-parser.py        # Parse/validate TikTok URLs, read batch files
├── requirements.txt     # yt-dlp, rich (progress bars)
└── downloads/           # Output directory
```

### Key Features
1. Single URL download: `python main.py <url>`
2. Batch from file: `python main.py --batch urls.txt`
3. Profile scrape: `python main.py --user @username`
4. Output directory control: `--output ./downloads`
5. Concurrent downloads with configurable workers
6. Progress bars (rich/tqdm)
7. Skip already-downloaded videos (by video ID)

### Dependencies
- `yt-dlp` — core download engine
- `rich` or `tqdm` — progress display

### Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| TikTok API changes break yt-dlp | Pin version, update regularly |
| Rate limiting on bulk scraping | Add configurable delays |
| Some videos watermark-only | Fallback gracefully, log failures |

## Sources
- [yt-dlp TikTok extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/tiktok.py)
- [TikTok-Video-Downloader-using-Python-and-yt-dlp](https://github.com/vgvr0/TikTok-Video-Downloader-using-Python-and-yt-dlp)
- [TikTok-Multi-Downloader](https://github.com/financiallyruined/TikTok-Multi-Downloader)
- [Ez-TikTok-Downloader (TikWM)](https://github.com/AlexRabbit/Ez-TikTok-Downloader)
- [tiktokget on PyPI](https://pypi.org/project/tiktokget/)
