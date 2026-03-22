# Phase 2: Update CLI for Facebook Support

## Overview
- **Priority:** High
- **Status:** Complete
- **Effort:** Small

Update `main.py` CLI to accept Facebook URLs and add `--facebook-page` argument.

## Related Files
- **Modify:** `main.py`

## Implementation Steps

1. Update `parse_args()`:
   - Change description to "TikTok & Facebook Batch Video Downloader"
   - Update `url` help text to mention Facebook
   - Add `--facebook-page PAGE_URL` argument (similar to `--user` for TikTok profiles)

2. Update URL validation in `main()`:
   - Replace `validate_tiktok_url()` with `validate_url()` (from phase 1)
   - Add `--facebook-page` handling that passes URL to `download_batch`

3. Update help text and error messages to mention Facebook support

## Success Criteria
- `python main.py "https://facebook.com/user/videos/123"` works
- `python main.py --facebook-page "https://facebook.com/pagename"` works
- All existing TikTok CLI flows unchanged
- Help text reflects multi-platform support
