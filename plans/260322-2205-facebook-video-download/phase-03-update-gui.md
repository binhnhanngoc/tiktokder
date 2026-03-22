# Phase 3: Update GUI for Multi-Platform Support

## Overview
- **Priority:** High
- **Status:** Complete
- **Effort:** Medium

Update GUI components to accept Facebook URLs alongside TikTok URLs.

## Related Files
- **Modify:** `gui/url_input_panel.py`, `gui/channel_browser.py`, `gui/main_window.py`

## Implementation Steps

### url_input_panel.py
1. Update placeholder text: "Paste TikTok or Facebook video/page URL..."
2. Replace `validate_tiktok_url()` / `is_channel_url()` with unified validators from phase 1:
   - Use `validate_url()` for video URLs
   - Use `is_channel_url()` OR `is_facebook_page_url()` for page/channel routing

### channel_browser.py
1. Update placeholder text: "Paste TikTok channel or Facebook page URL..."
2. No logic changes needed — `ChannelFetcher` uses yt-dlp which handles Facebook pages

### main_window.py
1. Update window title if desired (optional — "TikTokDer" is the brand name)
2. Update About dialog text to mention Facebook support
3. Update channel tab label from "Channel" to "Channel / Page" to reflect Facebook pages

## Success Criteria
- Pasting a Facebook video URL in the input triggers download
- Pasting a Facebook page URL routes to the Channel/Page browser tab
- Channel browser fetches videos from Facebook pages via yt-dlp
- All existing TikTok GUI flows unchanged
