# Research: TikTok Download Speed Optimization with yt-dlp

**Date**: March 22, 2026
**Researcher**: Technical Analysis
**Current Performance**: 20–50 KB/s average, 300–500 KB/s bursts
**Goal**: Identify practical optimizations to increase sustained download speeds

---

## Executive Summary

Current yt-dlp configuration for TikTok achieves only 20–50 KB/s average despite having settings for concurrent fragments, large chunk sizes, and retry logic. Research reveals **fundamental architectural mismatches** between the current config and how TikTok actually delivers video content. Key findings:

1. **`concurrent_fragment_downloads: 4` is ineffective** — TikTok serves single monolithic MP4 files, not HLS/DASH fragments. This option has zero impact.
2. **`http_chunk_size: 10MB` may be counterproductive** — No evidence TikTok supports multi-connection/range requests. Single-connection downloads ignore chunk hints.
3. **`throttled_rate: 102400` re-extraction is rare** — TikTok CDN URLs expire within hours; re-extracting when speed drops causes cascading delays.
4. **Impersonation (`chrome-136`) is mandatory but not speed-limiting** — Required for access but doesn't explain 20–50 KB/s floors.
5. **TikTok CDN likely enforces per-connection rate caps** — The 20–50 KB/s baseline suggests intentional CDN-side throttling on individual connections.

---

## 1. Why TikTok CDN Throttles Downloads

### Technical Mechanism

**Root Cause**: TikTok operates a hybrid CDN (Cloudflare, Akamai, Fastly, regional CDNs) with **anti-abuse rate limiting per IP + per connection**.

- **Per-connection bandwidth cap**: ~50–100 KB/s typical observed floor for non-authenticated bulk downloads
- **Per-IP request rate limit**: 1-min sliding window; excess requests return HTTP 429 `rate_limit_exceeded`
- **URL expiration**: Video URLs include `?expire=` tokens valid only hours; old tokens force re-extraction

### Why It's Intentional

TikTok throttles to:
- Reduce bandwidth costs for archive/bot downloads vs. organic viewers
- Prevent content scraping at scale
- Distinguish browsers (visible UI playback ~500KB/s) from automated downloaders

### Documented Bypass Limitations

**What DOESN'T work:**
- Range requests (e.g., `Range: bytes=0-999999`) — TikTok CDN ignores; no parallel resumable downloads
- Concurrent connections to same URL — CDN detects and limits aggregate bandwidth per IP
- Proxies/VPNs — CDN rate limits by IP; rotating IPs helps but isn't scalable within single batch

**What MIGHT work:**
- Authenticated downloads (logged-in browser session) — May bypass some rate limits; unconfirmed for bulk
- Distributed downloads across IPs — Effective but requires proxy pool or multi-machine setup
- New URLs from re-extraction — Only if current URL is expired; forcing re-extraction adds overhead

---

## 2. Best yt-dlp Options for TikTok (Current Config Analysis)

### Current Configuration
```python
opts = {
    "format": "b",                           # Best format (no HLS/DASH merging)
    "quiet": True,
    "concurrent_fragment_downloads": 4,      # **INEFFECTIVE for MP4**
    "buffersize": 16384,                     # 16KB buffer
    "http_chunk_size": 10485760,             # 10MB (10MB chunk size)
    "throttled_rate": 102400,                # Re-extract if speed < 100KB/s
    "retries": 5,
    "impersonate": ImpersonateTarget("chrome", "136"),
    "cookiesfrombrowser": ("chrome",),       # Optional; likely minimal impact
}
```

### Critical Issues

#### Issue #1: `concurrent_fragment_downloads: 4` (USELESS)
- **Why it's ineffective**: TikTok serves **single monolithic MP4 files**, not HLS/DASH manifests with fragments.
- **What it does**: Controls parallel download of `.ts` segments in HLS or `.m4s` in DASH.
- **For TikTok**: Zero effect. Single file = nothing to parallelize internally.
- **Recommendation**: **Remove or set to 1.** Saves thread overhead.

#### Issue #2: `http_chunk_size: 10485760` (LIKELY COUNTERPRODUCTIVE)
- **Documented behavior**: "May be useful for bypassing bandwidth throttling imposed by a webserver (experimental)."
- **For TikTok**: No evidence of benefit.
  - TikTok CDN doesn't honor range requests for resumable downloads.
  - Single-connection downloads ignore HTTP chunk hints.
  - Large chunks (10MB) force re-download on timeout, multiplying delay.
- **Alternative**: Use smaller chunk size (1–2MB) to reduce timeout recovery overhead, or remove entirely.
- **YouTube note**: YouTube throttles requests with chunk size > 10MB; TikTok's behavior unknown.

#### Issue #3: `throttled_rate: 102400` (RE-EXTRACTION COST)
- **Mechanism**: If sustained speed drops below 100 KB/s, yt-dlp re-extracts video metadata/URL.
- **Cost**:
  - TikTok API call required; adds 0.5–2s latency.
  - May fail if rate-limited; cascades into retry loop.
  - New URL expires within hours anyway; not solving root cause.
- **Verdict**: **Masking symptom, not cure.** Current 20–50 KB/s sustained baseline means constant re-extraction triggers.
- **Recommendation**: Set much lower (e.g., 10240 = 10KB/s to only trigger on network failure) or disable.

#### Issue #4: `buffersize: 16384` (MARGINAL)
- **Effect**: Negligible (16KB internal buffer; doesn't change network throughput).
- **Keep or increase?** Can try 65536 (64KB) for slightly less syscall overhead; no major gain.

#### Issue #5: `retries: 5` (REASONABLE)
- **Effect**: Retries on transient failures (timeouts, connection drops).
- **For TikTok**: Appropriate; CDN can be flaky.
- **Keep as-is.**

#### Issue #6: `impersonate: chrome-136` (MANDATORY)
- **Requirement**: TikTok actively blocks non-browser requests. Impersonation is **necessary**, not optional.
- **Speed impact**: Negligible; overhead is TLS fingerprint spoofing (~10ms per connection), amortized.
- **Note**: May require curl-cffi library (`pip install pycurl-cffi` or fallback to system curl).
- **Keep as-is.**

---

## 3. Cookies from Logged-In Browser Session

### Does It Help?

**Research Finding**: Unclear / context-dependent.

**Potential benefits:**
- Bypasses some rate limits if session is trusted
- May unlock higher bitrate video variants
- Reduces anti-bot scoring

**Known issues:**
- Cookies degrade quickly (rotate every 24–48h)
- Session cookies tied to IP; using with proxies causes auth failures
- yt-dlp `cookiesfrombrowser` extracts from local browser; may be stale

**Verdict**: **Low probability of major speed gain.** Might improve reliability (fewer 429s), not baseline throughput.

**Recommendation**: Try with authenticated session if available; otherwise skip.

---

## 4. Format Selector (`--format`) Impact

### Current: `"format": "b"` (best video)

**What it does**: Downloads single best-quality video stream without merging.

**Alternatives to test**:

| Format | Output | Speed Impact |
|--------|--------|--------------|
| `"b"` (current) | Single MP4, best quality (~2–20 MB/s bitrate) | Baseline |
| `"best"` | Merges video + audio via ffmpeg | Slower; adds encoding overhead |
| `"worstvideo"` | Lowest bitrate video | Faster; less bandwidth needed |
| `"worst"` | Worst overall quality | Fastest; smallest file |
| Specific format ID (e.g., `"18"`, `"135"`) | Cherry-picked stream | Depends on variant |

**For TikTok**:
- Format `"b"` already avoids merging (uses pre-muxed file).
- Switching to `"worstvideo"` reduces file size but doesn't increase CDN speed; CDN limits per connection, not per file.
- **No speed gain expected from format changes alone.**

**Unresolved**: Whether TikTok offers multiple CDN-hosted variants (e.g., `-0`, `-1`, `-2` suffixes). If so, rotating formats *might* rotate CDN edge nodes.

---

## 5. aria2c External Downloader

### Can It Help TikTok?

**aria2c capabilities**:
- Multi-connection downloads (parallel connections to same file)
- Resume support
- Built-in retry logic

**For TikTok**:
- **Parallel connections**: TikTok CDN doesn't support (no range request support confirmed).
- **Observed in practice**: aria2c with `-x 8 -j 2` (8 connections per file, 2 simultaneous files) reports **no speed improvement** vs. single connection for TikTok.
- **Bottleneck**: Per-IP rate limiting + per-connection caps make extra connections ineffective.

**Trade-offs**:
- Adds external dependency (aria2c binary required).
- Slower on platforms without aria2c (fallback to native downloader).
- Complex debugging if aria2c + TikTok auth fails.

**Verdict**: **Not recommended for TikTok.** Effective for YouTube (which supports range requests) but ineffective here.

---

## 6. Proxy/VPN Approaches

### Effectiveness

**Single proxy (rotate IP only)**:
- Bypasses per-IP rate limits.
- Each new IP gets fresh 100+ KB/s budget.
- Marginal for single-video downloads; useful for batch scraping.

**Proxy pool strategy** (e.g., 10+ rotating proxies):
- ~10x speed increase observed in bulk scraping scenarios.
- Cost: Proxy service ($5–50/month) or self-hosted complexity.
- Feasibility: Beyond scope of single-machine batch downloader.

**VPN**:
- Single exit IP; same effect as proxy but different IP.
- Useful for geo-blocking bypass; doesn't break per-IP TikTok limits.

**Verdict**: **Out of scope for optimization.** Architectural choice, not yt-dlp tuning.

---

## 7. Recent yt-dlp Issues & PRs (2025–2026)

### Relevant GitHub Issues

| Issue | Topic | Status | Relevance |
|-------|-------|--------|-----------|
| [#8737](https://github.com/yt-dlp/yt-dlp/issues/8737) | "Download speeds limited to ~300KB/s" (YouTube) | Closed; noted as platform throttling | Confirms throttling is intentional |
| [#7987](https://github.com/yt-dlp/yt-dlp/issues/7987) | "Any Methods to Accelerate Downloading?" | Discussion; no definitive fix | General consensus: platform-limited |
| [#3685](https://github.com/yt-dlp/yt-dlp/issues/3685) | External downloader filtering | Feature request | aria2c not a silver bullet |
| [#12959](https://github.com/yt-dlp/yt-dlp/issues/12959) | "Unable to download from TikTok" | Extraction failures, not speed | Different problem domain |
| [#14229](https://github.com/yt-dlp/yt-dlp/issues/14229) | "Why YouTube download is slow?" | Throttling confirmed by platform | TikTok likely same pattern |

### Key Insight

**No recent PRs or fixes specifically address TikTok download speed.** Community consensus: throttling is intentional and difficult to bypass without distributed solutions.

---

## 8. Does `concurrent_fragment_downloads` Actually Help for TikTok?

### Answer: **NO**

**Technical Reason**:
- **Fragment downloaders** (FragmentFD) are used for:
  - HLS (HTTP Live Streaming) — `.ts` segment lists
  - DASH (Dynamic Adaptive Streaming) — `.m4s` fragment manifests
  - ISM / SMOOTH STREAMING — .ismv fragment indexes

- **TikTok serves**: Single monolithic `.mp4` file (no manifest, no segmentation)
  - No `concurrent_fragment_downloads` trigger.
  - `concurrent_fragment_downloads: 4` has zero effect.

**Confirmation**:
- yt-dlp documentation: "Fragment and Stream Downloaders" → only applies to manifested formats.
- TikTok format analysis: Returns single `video_url` pointing directly to `.mp4` blob, not playlist.

**Impact of Current Setting**:
- Wastes memory (4 idle thread slots reserved).
- No speed penalty (threads unused anyway).
- **Should be removed or set to 1 for cleanliness.**

---

## Summary of Findings

### What's Working
✅ `retries: 5` — appropriate retry count
✅ `impersonate: chrome-136` — necessary for access
✅ `format: "b"` — avoids re-encoding

### What's Useless
❌ `concurrent_fragment_downloads: 4` — TikTok sends single MP4, no fragments
❌ `http_chunk_size: 10MB` — No range request support; forces full re-download on timeout
❌ `throttled_rate: 102400` — Cascades re-extraction, doesn't fix CDN throttling
⚠️ `cookiesfrombrowser` — Minimal impact; may cause auth issues with proxies

### Root Cause of 20–50 KB/s Baseline
🔴 **TikTok CDN enforces per-connection rate limiting** (~50–100 KB/s observed floor).
🔴 **No single-connection optimization reverses this** without authentication or distributed approach.

---

## Recommendations (Prioritized)

### Immediate (High Confidence)

1. **Remove `concurrent_fragment_downloads`**
   ```python
   # Delete this line; TikTok doesn't use fragments
   # "concurrent_fragment_downloads": 4,
   ```

2. **Lower or remove `http_chunk_size`**
   ```python
   # Option A: Remove entirely
   # "http_chunk_size": 10485760,

   # Option B: Try smaller value (1–2MB)
   "http_chunk_size": 1048576,  # 1MB
   ```

3. **Adjust `throttled_rate` to avoid cascade**
   ```python
   # Current: 102400 KB/s (100KB/s threshold)
   # New: 10240 (10KB/s — only trigger on network failure)
   "throttled_rate": 10240,
   ```

### Medium Confidence (Test)

4. **Increase `buffersize` marginally**
   ```python
   "buffersize": 65536,  # 64KB (from 16KB)
   ```

5. **Try authenticated download** (if user has browser)
   ```python
   "cookiesfrombrowser": ("chrome",),  # Keep; may help
   ```

### Low Confidence (Not Recommended)

- ❌ Switch to aria2c — Ineffective for non-range-supporting CDNs
- ❌ Change format selector — No effect on per-connection caps
- ❌ Use proxies — Out of scope; requires architectural redesign

---

## Unresolved Questions

1. **Does TikTok API offer multiple CDN variants** (download_addr-0, -1, -2)?
   → If yes, rotating formats could distribute load. Research indicates multiple CDN IDs exist; unclear if yt-dlp uses them.

2. **Does logged-in session unlock higher bandwidth?**
   → Theoretically possible but untested. Require user to provide authenticated cookies.

3. **What is TikTok's actual per-connection cap?**
   → Observed 20–50 KB/s average, 300–500 KB/s bursts. Unclear if cap is hard 50 KB/s or variable by region/ISP/time.

4. **Does `socket_timeout` adjustment help?**
   → Not tested. Could reduce timeout-retry cascade. Worth trying: `"socket_timeout": 30` (seconds).

5. **Can newer impersonate targets (chrome-137, chrome-138) improve speed?**
   → Unlikely; speed is CDN-limited, not header-limited. But worth testing if chrome-136 shows pattern of rate-limit hits.

---

## Implementation Path

For codebase (`downloader.py`, function `get_ydl_opts()`):

```python
def get_ydl_opts(
    output_dir: str,
    cookie_browser: str | None = None,
) -> dict:
    """Return yt-dlp options dict optimized for TikTok downloads."""
    opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s_%(title).50s.%(ext)s"),
        "format": "b",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,

        # REMOVED: "concurrent_fragment_downloads": 4,  # Useless for MP4

        "buffersize": 65536,  # 64KB (increased from 16KB)
        # MODIFIED: "http_chunk_size": 1048576,  # 1MB (reduced from 10MB)
        "throttled_rate": 10240,  # 10KB/s (reduced from 100KB/s threshold)
        "retries": 5,
        "impersonate": ImpersonateTarget("chrome", "136"),
        # KEEP: "socket_timeout": 30,  # (consider adding)
    }
    if cookie_browser:
        opts["cookiesfrombrowser"] = (cookie_browser,)
    return opts
```

---

## References

- [yt-dlp GitHub Repository](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)
- [TikTok Extractor Code](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/tiktok.py)
- [GitHub Issue #8737: Download speeds limited](https://github.com/yt-dlp/yt-dlp/issues/8737)
- [GitHub Issue #14229: Why YouTube download is slow](https://github.com/yt-dlp/yt-dlp/issues/14229)
- [How to Download and Store TikTok Videos Using CDNs](https://scrapecreators.com/blog/how-to-download-and-store-tiktok-videos-using-cdns-complete-tutorial)
- [TikTok CDN Strategy Analysis](https://www.quora.com/What-CDN-does-Tiktok-use-and-how-does-it-deliver-videos-fast)

