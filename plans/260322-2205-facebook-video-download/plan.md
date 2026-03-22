# Facebook Video Download Feature

## Summary
Add Facebook page/video download support to TikTokDer. Since yt-dlp already handles Facebook extraction natively, the work is primarily extending the URL validation layer, updating UI labels, and adding a Facebook page browser tab.

## Key Insight
**yt-dlp already supports Facebook/Meta videos** — `downloader.py` needs zero changes for actual downloading. The work is in the validation/routing layer and UI.

## Architecture Decision
- Generalize `url_parser.py` to handle multiple platforms (TikTok + Facebook)
- Reuse existing `DownloadEngine`, `DownloadWorker`, `ChannelFetcher` — they're platform-agnostic via yt-dlp
- Add Facebook URL patterns alongside TikTok patterns
- Update GUI text/placeholders to reflect multi-platform support
- Keep backward compatibility — all existing TikTok functionality unchanged

## Phases

| # | Phase | Status | Priority | Effort |
|---|-------|--------|----------|--------|
| 1 | Extend URL parser for Facebook URLs | Complete | High | Small |
| 2 | Update CLI to accept Facebook URLs | Complete | High | Small |
| 3 | Update GUI for multi-platform support | Complete | High | Medium |
| 4 | Update tests | Complete | High | Medium |
| 5 | Update docs | Complete | Low | Small |

## Risk Assessment
- **Facebook auth**: Some Facebook videos require login. yt-dlp supports `--cookies-from-browser` which we already pass through. Low risk.
- **Facebook URL variety**: Facebook has many URL formats (fb.watch, facebook.com/watch, /videos/, /reel/, etc). Need comprehensive regex.
- **Rate limiting**: Facebook may block rapid requests. Existing delay mechanism handles this.

## Files to Modify
- `url_parser.py` — Add Facebook URL patterns + validation
- `main.py` — Update CLI help text and validation logic
- `gui/url_input_panel.py` — Update placeholder text and validation
- `gui/channel_browser.py` — Update placeholder text
- `gui/main_window.py` — Update window title/about text
- `test_tiktokder.py` — Add Facebook URL tests
- `README.md` — Document Facebook support
- `docs/` — Update relevant docs

## Files NOT Modified (already platform-agnostic)
- `downloader.py` — yt-dlp handles Facebook natively
- `download_engine.py` — Platform-agnostic queue manager
- `channel_fetcher.py` — yt-dlp handles Facebook page extraction
- `config.py` — No new settings needed
