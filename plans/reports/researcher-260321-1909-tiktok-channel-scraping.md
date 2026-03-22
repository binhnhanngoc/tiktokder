# TikTok Channel Scraping with yt-dlp: Research Report

**Date:** 2026-03-21 | **CWD:** D:\Projects\tiktokder

## Executive Summary

yt-dlp has **native TikTok profile support** but with caveats: pagination is unreliable, pagination support is still in development, and TikTok blocks unauthenticated scraping. Best approach: browser-based URL extraction + yt-dlp for downloading.

---

## Findings

### 1. yt-dlp TikTok Profile Support

**Native support exists but incomplete:**
- Direct profile URLs work: `yt-dlp 'https://www.tiktok.com/@chg12.movie'`
- Downloads only **visible videos** (limited by initial page load)
- Pagination via JavaScript infinite scroll not reliably captured
- Playlist extraction **not officially supported** (open GitHub issue #7804)

**Status:** Issue #7804 remains open; draft PR #14152 for playlist support pending.

### 2. Extracting Video URLs Without Download

**Recommended approach: Browser-based extraction**

```python
# Use DevTools console on TikTok profile page
javascript_extractor = """
let videos = [];
let lastHeight = document.body.scrollHeight;
const scrollSpeed = 500; // ms between scrolls

async function scrollToBottom() {
  while (true) {
    document.querySelectorAll('a[href*="/video/"]').forEach(el => {
      videos.push(el.href);
    });
    window.scrollBy(0, window.innerHeight);
    await new Promise(r => setTimeout(r, scrollSpeed));

    if (document.body.scrollHeight === lastHeight) break;
    lastHeight = document.body.scrollHeight;
  }
}

scrollToBottom().then(() => {
  let unique = [...new Set(videos)];
  download('tiktok_urls.txt', unique.join('\\n'));
});
"""
```

**Then download with yt-dlp:**
```bash
yt-dlp -a tiktok_urls.txt -o "%(title)s-%(id)s.%(ext)s"
```

### 3. Pagination Handling

**TikTok limitations:**
- Infinite scroll pagination via JavaScript (not HTTP-based)
- Initial load shows ~20-30 videos
- yt-dlp's `--flat-playlist` doesn't work with TikTok profiles
- Browser automation (Selenium/Playwright) can solve this

**Python pagination workaround:**
```python
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()
driver.get("https://www.tiktok.com/@chg12.movie")

videos = set()
last_count = 0

while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    current_videos = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/video/"]')
    for video in current_videos:
        videos.add(video.get_attribute('href'))

    if len(videos) == last_count:
        break
    last_count = len(videos)

with open('tiktok_urls.txt', 'w') as f:
    f.write('\n'.join(sorted(videos)))

driver.quit()
```

### 4. Rate Limiting Concerns

**TikTok API:** Official API has 1000 req/min limit (429 HTTP status)

**yt-dlp workaround risks:**
- TikTok blocks unauthenticated requests → use browser cookies
- Aggressive scrolling triggers IP bans
- Mitigation: Add delays, rotate user-agents, use residential proxies

**Recommended delays:**
```python
# In selenium script
time.sleep(random.uniform(1, 3))  # Between scrolls
time.sleep(random.uniform(5, 10)) # Between batches
```

### 5. Metadata Extraction

**Available via yt-dlp:**
```bash
# Extract metadata to JSON without downloading
yt-dlp --dump-json -a urls.txt > metadata.json

# Fields available: title, id, upload_date, view_count, like_count,
# comment_count, share_count, duration, uploader, uploader_id
```

**Example output parsing:**
```python
import json
with open('metadata.json') as f:
    for line in f:
        video = json.loads(line)
        print(f"{video['title']} - Views: {video.get('view_count', 'N/A')}")
```

### 6. Alternative Approaches

**Option A: tiktok-to-ytdlp (Browser Extension)**
- Automates JavaScript URL collection
- Exports TXT/JSON
- Supports: profiles, likes, sounds
- Lacks rate-limit control

**Option B: TikTok Unofficial API** (Not recommended)
- APIs frequently break, need maintenance
- TikTok actively blocks reverse-engineered endpoints
- yt-dlp more stable long-term

**Option C: Hybrid Approach** (BEST)
```python
# 1. Use Selenium for pagination + URL collection
# 2. Pass URLs to yt-dlp for downloading
# 3. Extract metadata via yt-dlp JSON
# 4. Add delays to avoid rate limits
```

---

## Practical Implementation Summary

```python
import subprocess
import json
from selenium import webdriver
import time

# Step 1: Collect URLs via browser automation
urls = collect_tiktok_urls("https://www.tiktok.com/@chg12.movie")

# Step 2: Extract metadata
cmd = ["yt-dlp", "--dump-json"] + urls
result = subprocess.run(cmd, capture_output=True, text=True)
metadata = [json.loads(line) for line in result.stdout.strip().split('\n')]

# Step 3: Download videos with 2-3s delay between
for url in urls:
    subprocess.run(["yt-dlp", "-o", "%(title)s.%(ext)s", url])
    time.sleep(2)
```

---

## Unresolved Questions

1. Does `@chg12.movie` profile have authentication requirements or region blocking?
2. Exact pagination limit (max videos yt-dlp captures in one run)?
3. Should we implement cookie-based auth for robustness?
4. Storage plan for hundreds of videos (directory structure)?

---

## Sources

- [Downloading every video for a TikTok account | Simon Willison's TILs](https://til.simonwillison.net/tiktok/download-all-videos)
- [tiktok-to-ytdlp Browser Extension](https://github.com/dinoosauro/tiktok-to-ytdlp)
- [yt-dlp TikTok Playlist Support Issue #7804](https://github.com/yt-dlp/yt-dlp/issues/7804)
- [TikTok API Rate Limiting Documentation](https://developers.tiktok.com/doc/tiktok-api-v2-rate-limit)
- [How to Build a TikTok Video Downloader Using Laravel and yt-dlp](https://dev.to/faheem_zia_b90650328482a7/how-to-build-a-tiktok-video-downloader-using-laravel-and-yt-dlp-49jf)
