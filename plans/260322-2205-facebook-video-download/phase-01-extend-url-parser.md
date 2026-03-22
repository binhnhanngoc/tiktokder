# Phase 1: Extend URL Parser for Facebook URLs

## Overview
- **Priority:** High
- **Status:** Complete
- **Effort:** Small

Add Facebook URL validation patterns to `url_parser.py` while keeping all existing TikTok logic intact.

## Key Insights
- Facebook video URLs come in many formats: facebook.com/watch, /videos/, /reel/, fb.watch short links
- yt-dlp handles all Facebook URL formats — we just need to validate them enough to route correctly
- Don't over-validate — yt-dlp will reject truly invalid URLs. We just need to distinguish Facebook from garbage.

## Related Files
- **Modify:** `url_parser.py`

## Implementation Steps

1. Add Facebook URL regex patterns:
   ```python
   FACEBOOK_URL_PATTERN = re.compile(
       r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.watch|fb\.com)"
       r"(?:/[\w.]+)?(?:/(?:videos?|watch|reel|posts|story)/?\S*)?",
       re.IGNORECASE
   )
   FACEBOOK_PAGE_PATTERN = re.compile(
       r"https?://(?:www\.|m\.)?facebook\.com/[\w.]+/?$",
       re.IGNORECASE
   )
   ```

2. Add validation functions:
   ```python
   def validate_facebook_url(url: str) -> bool
   def is_facebook_page_url(url: str) -> bool
   ```

3. Add a unified validation function:
   ```python
   def validate_url(url: str) -> bool  # accepts TikTok OR Facebook
   def detect_platform(url: str) -> str | None  # returns "tiktok", "facebook", or None
   ```

## Success Criteria
- All existing TikTok URL tests still pass
- Facebook video URLs validated correctly
- Facebook page URLs detected correctly
- Platform detection works for both TikTok and Facebook
