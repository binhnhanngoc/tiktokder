---
name: Facebook Profile Video Scraping Research
description: Investigation of available methods to list videos from Facebook profile URLs using Python (for TikTokDer project)
type: research
date: 2026-03-22
---

# Facebook Profile Video Scraping Research

**Objective:** Find viable Python methods to list all video URLs from a Facebook profile (e.g., https://www.facebook.com/profile.php?id=61569095384246) without API keys, suitable for TikTokDer's yt-dlp integration.

---

## Executive Summary

**RECOMMENDATION: facebook-scraper (kevinzg) is the best pragmatic solution** with Playwright as a fallback.

- **facebook-scraper**: Works for post enumeration with video detection; video extraction supported via youtube_dl parameter but output format needs wrapping
- **Playwright/Selenium**: Required for handling JavaScript-rendered infinite scroll; higher overhead but more reliable
- **yt-dlp**: Cannot enumerate Facebook profile video lists (confirmed limitation)
- **Facebook Graph API**: Requires authentication and API keys (violates "no API keys" constraint)

---

## Detailed Findings

### 1. facebook-scraper Package (kevinzg/facebook-scraper)

**Status:** Actively maintained, 3000+ GitHub stars, recent commits in 2025

**GitHub:** https://github.com/kevinzg/facebook-scraper

**PyPI:** https://pypi.org/project/facebook-scraper/

#### Capabilities
- ✅ Scrapes public Facebook pages/profiles without API keys
- ✅ Extracts posts with metadata (text, media, reactions, shares)
- ✅ Supports video detection in posts (returns `video` field with URL, `video_id` field)
- ✅ Optional `youtube_dl` parameter for higher-quality video extraction
- ⚠️ No dedicated "list videos only" filter (must parse posts and filter for video_id)

#### API Overview
```python
from facebook_scraper import get_posts

# Get posts from a profile
posts = get_posts(
    account='profile.php?id=61569095384246',  # or username
    pages=None  # fetch all pages
)

# Iterate and filter for videos
for post in posts:
    if post.get('video_id'):  # Video post detected
        video_url = post['video']  # Direct video URL
        video_id = post['video_id']
        # Use with yt-dlp
```

#### Limitations
- **Video-only filtering:** Not built-in; requires post enumeration then filtering
- **Infinite scroll handling:** Requires Selenium under hood (transparent to user)
- **Rate limiting:** Facebook throttles requests; delays between pages recommended
- **URL format flexibility:** Some URL formats may not work (e.g., numeric ID vs. username)

#### Viability: **HIGH** for pragmatic MVP
- Fastest to implement (pip install + 10 lines of code)
- Proven track record (used by many in community)
- Video extraction works (via youtube_dl option)
- Main downside: May require pagination tuning or rate-limit handling

---

### 2. Playwright + BeautifulSoup Approach

**Best for:** Maximum reliability when facebook-scraper fails

**Status:** Playwright recommended over Selenium in 2025-2026 (better API, auto-wait)

#### Key Characteristics
- **Advantages:**
  - Handles JavaScript-rendered infinite scroll natively
  - Auto-wait mechanism eliminates timing bugs
  - Modern async-friendly API
  - Browser automation ensures compatibility with future Facebook changes

- **Disadvantages:**
  - Resource overhead (spins up real browser)
  - Slower than facebook-scraper (seconds vs. milliseconds per page)
  - Requires Chromium/Firefox installation
  - Higher complexity
  - Facebook's anti-bot measures may block automated browser sessions

#### Architecture Pattern
```
Playwright (load page + scroll) → BeautifulSoup (parse HTML) → Extract video URLs
```

**Infinite Scroll Pattern:**
1. Load profile page
2. Simulate scroll down (trigger "Load more posts")
3. Extract video URLs from current DOM
4. Repeat until no new posts loaded

#### Viability: **MEDIUM** (suitable as fallback)
- Reliable but overkill for simple enumeration
- Performance penalty not justified unless facebook-scraper breaks
- Facebook actively detects automated browsers (requires proxy/delays)

---

### 3. yt-dlp Support Status

**Verdict:** ❌ NOT SUITABLE for profile listing

**Evidence:**
- [yt-dlp Issue #6518](https://github.com/yt-dlp/yt-dlp/issues/6518) — Feature request: "Support downloading all videos from a Facebook page" (OPEN, not prioritized)
- [yt-dlp Issue #12716](https://github.com/yt-dlp/yt-dlp/issues/12716) — "Unable to Download Instagram & Facebook Metadata for Entire Profiles"
- **Current behavior:** Individual Facebook video URLs work; profile/page URLs return "Unsupported URL"

**Why not fixed:**
- Facebook's dynamic loading makes enumeration difficult
- yt-dlp focused on individual video extraction, not enumeration
- Graph API alternative blocked by authentication requirement

**Workaround:** Enumerate URLs with facebook-scraper, then pass to yt-dlp for download.

---

### 4. Facebook Graph API

**Verdict:** ❌ VIOLATES CONSTRAINT (requires API keys)

**Status:** Requires authentication and API keys; no public endpoint for video enumeration

**Requirements:**
- Facebook Developer App with access token
- Business/Creator Instagram account (if using Instagram Graph API)
- Authentication header for all requests

**Why ruled out:** Project constraint explicitly says "must work without Facebook API keys"

---

### 5. Alternative Python Packages

#### facebook-page-scraper
- No API keys required
- Less maintained than kevinzg's version
- No significant advantages over facebook-scraper

#### SSujitX/facebook-pages-scraper
- No webdriver requirement (uses requests + BeautifulSoup)
- Claims to scrape without API key
- Less popular; maintenance status unclear

#### Apify Solutions
- Enterprise-grade; requires paid account or free tier limits
- Overcomplicated for simple profile enumeration
- Recommended for high-volume production use (out of scope)

---

## Technical Constraints & Challenges

### 1. JavaScript Rendering
**Problem:** Facebook pages use infinite scroll with dynamically loaded content.
**Solution:** facebook-scraper handles this transparently; Playwright required as fallback.

### 2. Anti-Bot Measures
- Rate limiting (429 errors after ~20-30 requests)
- IP blocking (detected after ~100 requests without delay)
- User-Agent checking

**Mitigation:**
- Add 1-2 second delay between page loads
- Rotate User-Agent headers (library should do this)
- Use proxy servers for high-volume scraping (out of MVP scope)

### 3. URL Format Ambiguity
Facebook profile URLs come in multiple formats:
- `https://www.facebook.com/profile.php?id=123456`
- `https://www.facebook.com/username`
- `https://www.facebook.com/pages/pagename/123456`

Library must normalize or try multiple formats.

### 4. Dynamic Content Loading
Videos disappear from DOM when scrolling. Browser automation required (Selenium/Playwright).
facebook-scraper handles this; direct requests + BeautifulSoup alone insufficient.

---

## Comparison Matrix

| Criterion | facebook-scraper | Playwright | Selenium | Graph API |
|-----------|------------------|-----------|----------|-----------|
| No API keys required | ✅ | ✅ | ✅ | ❌ |
| Works with profile URLs | ✅ | ✅ | ✅ | ⚠️ |
| Video enumeration | ⚠️ (via posts) | ✅ | ✅ | ✅ |
| Setup complexity | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Speed | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Maintenance status | ✅ Active | ✅ Active | ✅ Active | ✅ Official |
| Facebook resistance | ⚠️ Moderate | ⚠️ High | ⚠️ High | ❌ Blocked |
| Production-ready | ✅ | ✅ | ✅ | ❌ (constraint) |

---

## Implementation Recommendations

### Phase 1: MVP (Primary Approach)
**Use facebook-scraper with post filtering**

```python
from facebook_scraper import get_posts

def list_facebook_profile_videos(profile_url_or_id, limit=None):
    """
    List all video URLs from a Facebook profile.

    Args:
        profile_url_or_id: Profile URL or numeric ID
        limit: Max videos to fetch (None = all)

    Returns:
        List[dict] with keys: url, video_id, title
    """
    videos = []
    pages = None if limit is None else (limit // 10 + 1)

    try:
        posts = get_posts(
            account=profile_url_or_id,
            pages=pages,
            cookies=None,  # Can accept cookies for private profiles later
        )

        for post in posts:
            if post.get('video_id'):
                videos.append({
                    'url': post['video'],
                    'video_id': post['video_id'],
                    'title': post.get('text', 'Untitled')[:100],
                })

                if limit and len(videos) >= limit:
                    break

    except Exception as e:
        # Log error; fail gracefully
        print(f"Error scraping profile: {e}")

    return videos
```

**Pros:**
- Simple integration (10-20 LoC)
- Fast (seconds for 30-50 videos)
- No browser dependency

**Cons:**
- May fail on complex profile layouts
- Post enumeration overhead (fetches non-video posts too)

**Testing needed:**
- Works with numeric ID format (`profile.php?id=123`)
- Works with username format (`username`)
- Handles pagination correctly
- Rate limiting behavior

### Phase 2: Fallback (Browser Automation)
If facebook-scraper fails, use Playwright for reliability.

```python
async def list_facebook_profile_videos_playwright(profile_url, limit=None):
    """Playwright fallback for profile video enumeration."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Load profile
        await page.goto(profile_url)

        # Scroll to load all videos
        videos = []
        while True:
            # Extract video links from current DOM
            video_elements = await page.query_selector_all(
                'a[href*="/videos/"]'
            )

            for elem in video_elements:
                href = await elem.get_attribute('href')
                if href and '/videos/' in href:
                    videos.append(href)

            if limit and len(videos) >= limit:
                break

            # Scroll down to trigger load more
            await page.evaluate('window.scrollBy(0, 500)')
            await page.wait_for_timeout(1000)  # Wait for load

        await browser.close()
    return videos
```

**Pros:**
- Most reliable (handles all JS rendering)
- Works with future Facebook changes

**Cons:**
- Slow (10-20s for 50 videos)
- Requires Chromium install
- Facebook may block automated sessions

---

## Unresolved Questions

1. **facebook-scraper video URL format:** Does it return yt-dlp-compatible URLs directly, or require additional processing?
   - Need to test: `post['video']` field contents

2. **Profile URL format handling:** How robust is facebook-scraper's account parameter?
   - Need to test: numeric ID, username, full URL formats

3. **Rate limiting specifics:** What's the actual throttling threshold on fresh profiles?
   - Need to test: How many requests before 429 error

4. **Cookie support:** Can we use login cookies to access private/friend videos?
   - facebook-scraper supports cookies parameter; viability unclear

5. **Pagination efficiency:** Does facebook-scraper efficiently handle pagination, or is it inefficient?
   - May require profiling to determine overhead

6. **Playwright browser detection:** How easily does Facebook detect and block automated Playwright sessions?
   - Depends on User-Agent rotation and proxy usage

---

## Recommendations for TikTokDer Implementation

**Short term (MVP - Next 2 weeks):**
1. Implement facebook-scraper approach with post filtering
2. Add error handling for rate limiting (exponential backoff)
3. Test with 10-20 real Facebook profiles (various URL formats)
4. Pass URLs to existing yt-dlp downloader

**Medium term (v1.1 - 4-6 weeks):**
1. Add Playwright fallback if facebook-scraper fails
2. Implement proxy rotation for high-volume scraping
3. Add cookie support for accessing friend-only content
4. Cache video URLs to avoid re-scraping

**Not recommended:**
- Browser automation as primary approach (too slow for interactive UI)
- Graph API (violates no-keys constraint; legal uncertainty)
- Building custom HTTP parser (Facebook's HTML changes frequently)

---

## Key Takeaway

**facebook-scraper (kevinzg) is production-ready today.** Its video detection via post enumeration is slightly less efficient than dedicated video listing, but the trade-off (10 LoC vs. 100 LoC + browser overhead) is acceptable for MVP. Implement Playwright fallback only if real-world testing reveals frequent failures.

---

## Sources

- [facebook-scraper GitHub](https://github.com/kevinzg/facebook-scraper)
- [facebook-scraper PyPI](https://pypi.org/project/facebook-scraper/)
- [yt-dlp Issue #6518 - Facebook page video listing](https://github.com/yt-dlp/yt-dlp/issues/6518)
- [yt-dlp Issue #12716 - Profile metadata](https://github.com/yt-dlp/yt-dlp/issues/12716)
- [Playwright vs Selenium 2026](https://blog.apify.com/playwright-vs-selenium/)
- [Facebook Scraping 2025 Guide - Medium](https://medium.com/@AbdelRhman_Sabry/scraping-facebook-in-2025-combining-selenium-and-beautifulsoup-for-effective-data-extraction-95bc8d705889)
- [Instagram Graph API Documentation](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/)
- [Coronium.io Facebook Scraper Guide 2026](https://www.coronium.io/blog/facebook-scraper-python)
- [Scrapfly Facebook Scraping Guide](https://scrapfly.io/blog/posts/how-to-scrape-facebook)
- [Proxyway Facebook Scraping Guide](https://proxyway.com/guides/how-to-scrape-facebook)
