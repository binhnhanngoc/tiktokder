# Debug Report — FB Reel "Cannot parse data" on download

**Date:** 2026-04-26 22:05 +07
**Branch:** main
**Reporter:** ck-debug
**Scope:** GUI/CLI Facebook reel download path (yt-dlp)

## Symptom

```
ERROR: [facebook] <REEL_ID>: Cannot parse data; please report this issue ...
```

Multiple FB reel IDs (1378124144082524, 1164465825674079, 1224344083217488,
26127897033519107, 26353551294281468, 922438393706165, 939486595244169,
911105704885647, …) fail at extract time. yt-dlp redirects the reel URL to
`m.facebook.com/watch/?v=<id>&_rdr` then errors out at parse.

## Root Cause

**yt-dlp downloads the FB reel page anonymously even when the user has
configured a `cookies.txt` in Settings.** Anonymous mobile reel HTML is
either a login wall or a stripped variant; the FB extractor then fails the
`Cannot parse data` guard at `yt_dlp/extractor/facebook.py:828`.

The cookies.txt field is wired only into the **Playwright scraper**
(`FacebookFetcher`) which lists reels on a page. The actual download path
never sees it:

- `downloader.get_ydl_opts()` (`downloader.py:195-251`) accepts
  `cookie_browser` (yt-dlp `cookiesfrombrowser`) but has **no
  `cookiefile` parameter** — Netscape file is never passed.
- `DownloadEngine.__init__` (`download_engine.py:92-123`) has no
  `cookies_file` field; settings panel propagation skips it.
- `DownloadWorker.run()` (`download_engine.py:56-75`) deliberately
  zeroes `cookie_browser` for FB ("public reels don't need them") —
  comment is now wrong since FB tightened anonymous reel HTML.

### Reproduction (verified)

```bash
# Without cookies — fails (matches user report)
python -c "import yt_dlp; yt_dlp.YoutubeDL({'skip_download':True}).extract_info(
    'https://www.facebook.com/reel/1378124144082524', download=False)"
# -> ERROR: Cannot parse data

# Same URL, with cookiefile pointing at user's cookies.txt — succeeds
python -c "import yt_dlp; yt_dlp.YoutubeDL({
    'skip_download':True,
    'cookiefile':'D:/Projects/tiktokder/data/www.facebook.com_cookies.txt'
}).extract_info('https://www.facebook.com/reel/1378124144082524', download=False)"
# -> OK title=Video id=1378124144082524
```

User's `data/config.json` already stores
`cookies_file = D:/Projects/tiktokder/data/www.facebook.com_cookies.txt`,
so the fix needs no new UX — just wire the existing setting into yt-dlp.

## Fix

Thread the cookies.txt path into yt-dlp for FB downloads. Minimal edits:

1. **`downloader.get_ydl_opts`** — add `cookies_file: str | None = None`;
   when set, populate `opts["cookiefile"]`. Order rule: `cookies_file`
   takes precedence over `cookiesfrombrowser` for the same request.

2. **`downloader._do_download` / `download_video`** — forward
   `cookies_file` to `get_ydl_opts`.

3. **`DownloadEngine`** — add `cookies_file` ctor arg + attribute; pass
   it to `DownloadWorker`. `_apply_settings` already runs on settings
   change; also assign `self.engine.cookies_file = config.cookies_file`.

4. **`DownloadWorker`** — accept `cookies_file`; for FB URLs send it on
   to `download_video` (TikTok keeps `cookiesfrombrowser`). Drop the
   stale "public reels don't need cookies" comment.

5. **`gui/main_window.py`** — pass `cookies_file=config.cookies_file`
   to `DownloadEngine(...)` constructor; mirror in `_apply_settings`.

CLI (`main.py`) is out of scope — no `--cookies` flag exists yet; that
can be a follow-up.

## Validation Plan

1. Restart GUI with cookies.txt configured.
2. Re-queue one of the failing reels (e.g. `reel/1378124144082524`).
3. Expect: download completes; file appears under
   `downloads/facebook/<uploader>/<id>_<title>.mp4`.
4. Re-run `pytest -q` — existing tests must stay green.

## Notes / Side Issues

- The "Cannot parse data" path is also raised by yt-dlp for region-locked
  or deleted reels even with cookies. Post-fix, any residual failures
  should be classified into `not_found` / `private` instead of bubbling
  up as `unknown`. Consider extending `_classify_error` (`downloader.py:93`)
  with a `cannot parse data` → `not_found` mapping if false-negatives
  remain after the cookie fix.
- yt-dlp version 2026.03.17 is installed; upgrading further does not fix
  this — upstream extractor *needs* auth cookies for current reel HTML.

## Open Questions

- Should TikTok also fall back to `cookies_file` when `cookie_browser`
  is unset? (Currently no.) Probably yes for parity, but defer until
  TikTok shows the same anonymous-block symptom.
