# Phase 5: Update Documentation

## Overview
- **Priority:** Low
- **Status:** Complete
- **Effort:** Small

Update README and docs to reflect Facebook support.

## Related Files
- **Modify:** `README.md`, `docs/system-architecture.md`, `docs/code-standards.md`

## Implementation Steps

1. **README.md**:
   - Update title/description to mention Facebook
   - Add Facebook examples to CLI usage
   - Add `--facebook-page` to arguments table
   - Update "How It Works" to mention multi-platform support

2. **docs/system-architecture.md**:
   - Update `url_parser.py` section to include Facebook patterns
   - Note that `downloader.py` / `channel_fetcher.py` are platform-agnostic via yt-dlp

3. **docs/code-standards.md**:
   - Update `url_parser.py` module responsibilities with new functions

## Success Criteria
- Docs accurately reflect Facebook support
- No stale TikTok-only references in docs
