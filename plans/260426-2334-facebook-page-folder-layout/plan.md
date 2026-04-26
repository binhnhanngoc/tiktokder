# Facebook downloads: page-name folder layout (parity with TikTok)

**Status:** in-progress
**Scope:** Bug fix in `path_builder.py` + migration of existing FB folders.

## Problem

`downloads/facebook/` currently has one folder per video, named after the numeric video id (e.g. `1438416620945910/1438416620945910_<title>.mp4`). README and TikTok layout say it should be `<page_name>/<id>_<title>.mp4`.

## Root cause (path_builder.py)

1. `_uploader_from_info` accepts numeric `uploader_id` blindly — yt-dlp's FB extractor often fills only `uploader_id` (numeric page id) for `/reel/` URLs.
2. `platform_slug_from_url` skips reserved words (`reel`, `videos`, …) then returns the next path part; for `/reel/<digits>` that next part is the numeric video id.

## Fix

Update `path_builder.py`:
- Treat purely-numeric strings as IDs, not names — skip them in `_uploader_from_info` and `platform_slug_from_url`.
- Fallback chain after the rejection: `uploader_url`/`channel_url` → URL path → `unknown_uploader`.
- Parse trailing path segment of `uploader_url` (e.g. `https://facebook.com/NeonNewZealand` → `NeonNewZealand`).

## Migration

Existing folders are video-id named with no recoverable page metadata. Strategy:
- Detect any `downloads/facebook/<numeric>/` folder containing one numeric-prefixed file.
- Move contents into a target folder chosen by the user (e.g. `NeonNewZealand`, the single saved page they have) or `unknown_uploader` if unsure.
- Remove emptied numeric folders.

## Phases

- **Phase 1** — code fix + tests (path_builder)
- **Phase 2** — migration script + run (one-shot, kept under `scripts/`)

## Files

- `path_builder.py` (modify)
- `test_path_builder.py` (extend)
- `scripts/migrate_facebook_folders.py` (new, one-shot)

## Success

- New FB downloads land in `downloads/facebook/<page_name>/`.
- All existing tests pass + new cases (numeric uploader_id rejected, `/reel/` URL falls back, `uploader_url` parsed).
- Existing FB folders consolidated under page folder(s).
