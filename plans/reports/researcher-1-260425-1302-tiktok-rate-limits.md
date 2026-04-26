---
name: tiktok-rate-limits-research
description: TikTok scraping rate limits, signature systems, detection thresholds, and mitigation tactics — researcher-1 report 2026-04-25
type: report
---

# TikTok Rate Limits & Detection Research

**Date:** 2026-04-25
**Author:** researcher-1
**Sources consulted:** 18+ (yt-dlp source, davidteather/TikTok-Api issues, Scrapfly, ScrapeOps, justbeluga reverse-engineering, official TikTok dev docs, prior internal report)

---

## 1. Executive Summary

TikTok enforces multi-layered scraping defenses: **infrastructure rate limiting (~3 req/min/IP at CDN level)**, **TLS/HTTP2 fingerprint validation (Akamai Bot Manager, 9/10 difficulty)**, and **dynamic signature systems (msToken, X-Bogus, X-Gnarly)** that change every few months. Web API and mobile API (`api16-normal-c-useast1a.tiktokv.com`) have separate signing pipelines. Bans are predominantly behavioral (TLS/HTTP2 mismatch, request cadence, datacenter IP) rather than count-based — a perfectly-impersonated client (Chrome 131 TLS) with valid cookies and 1–3s spacing rarely hits limits, while a plain `requests` client gets blocked within ~3–10 calls. Most reliable mitigations rank: (1) `curl_cffi --impersonate chrome-131`, (2) residential proxy rotation, (3) headless-browser msToken refresh, (4) exponential backoff, (5) login cookies for higher quotas.

## 2. Key Findings (with evidence)

### 2.1 Rate limit reality
- **CDN-level: ~3 req/min/IP** — confirmed in prior internal CDN throttling report (2026-03-21) and replicated by yt-dlp issue #6400. Exceeding triggers progressive throttling → 403 → temp IP block.
- **Behavioral, not absolute** — ScrapeOps/ScrapeCreators consensus: TikTok analyzes patterns (cadence variance, header order, TLS fingerprint, navigation graph) rather than enforcing fixed counts. Same IP can pass 100s of requests if "human-like", or fail at 5 if not.
- **Official Research/Display API**: 1000 req/day across endpoints, 100k records/day, 1-min sliding window, returns 429 + `error_code=rate_limit_exceeded` (developers.tiktok.com/doc/tiktok-api-v2-rate-limit). Not relevant to scraping but baseline reference.

### 2.2 Signature systems (web)
- **msToken**: server-validated session token, present in cookies after visiting tiktok.com. Lifetime ~few hours; expires → captcha. Without msToken, sessions self-fetch but unreliable (TikTokApi v7 docs).
- **X-Bogus**: URL-param signature. Algo = double-MD5(params+body) → RC4(UA, salt+timestamp) → shifted base64. Required on most `/api/post/*`, `/api/recommend/*`, `/api/comment/*` endpoints.
- **X-Gnarly** (latest, since 2025): replaces/supplements X-Bogus. Object containing XOR ops, env code, MD5(query), MD5(body), UA hash, Unix ts, SDK version → encoded. Versions: 5.1.0 (May 2025), 5.1.1 (Jun 2025), 5.1.2 (Sep 2025), 5.1.3 (Nov 2025) — rotates every ~3 months (justbeluga, justscrapeme repos).
- **_signature** (legacy): being phased out, still seen on some web endpoints.
- **Generation cost**: requires headless browser running TikTok's obfuscated JS VM, OR reverse-engineered native re-impl (fragile, breaks per version).

### 2.3 Signature systems (mobile/api.tiktokv.com)
- yt-dlp uses `/aweme/v1/multi/aweme/detail` on `api16-normal-c-useast1a.tiktokv.com` with app version `35.1.3` / manifest `2023501030`.
- **X-Argus**: protobuf + SM3 + SIMON + AES — significantly harder than web signatures.
- **X-Gorgon**: legacy header, paired with X-Khronos timestamp.
- **X-Ladon**, **X-Helios**: additional layers in newer mobile builds.
- Mobile API requires `iid` (install ID) but **no user authentication for /aweme/ endpoints** — explains why yt-dlp prefers it.

### 2.4 Required cookies (web scraping)
- **ttwid**: device tracking, persistent. Set on first visit, required for nearly all API calls.
- **msToken**: see §2.2.
- **tt_webid_v2 / tt_webid**: device ID; tt_webid_v2 binds to videoUrl in some endpoints.
- **tt_csrf_token**: CSRF for write/auth endpoints; appears in error responses.
- **sessionid / sid_tt / sid_guard**: only when logged in. Logged-in sessions get higher rate limits + access to private content.
- **odin_tt**: yt-dlp generates random 160-char hex per request (mobile API).
- **s_v_web_id / verifyFp**: legacy/deprecated per davidteather issue #724; setting manually now often *triggers* captcha rather than bypassing it.

### 2.5 HTTP status codes & TikTok custom codes
| Code | Meaning | Source |
|------|---------|--------|
| 200 + `status_code=0` | Success | yt-dlp tiktok.py |
| 200 + `status_code=10204` | IP blocked at app layer | yt-dlp tiktok.py |
| 200 + `status_code=10216/10222` | Private/auth required | yt-dlp tiktok.py |
| 403 | TLS/header fingerprint reject, CDN | prior CDN report, scrapfly |
| 429 | Rate limit (rare on scraping endpoints; common on official API) | dev docs |
| 451 | Geo block — **not confirmed for TikTok specifically** in sources |
| Captcha challenge page | Behavioral suspicion threshold reached | davidteather issues #946, #421, #864 |

### 2.6 IP ban patterns
- **Datacenter IPs**: aggressively blocked; davidteather discussion #438 confirms residential bans only "started recently" — datacenter has always been hit hard.
- **Ban duration**: temporary (minutes–hours) for cadence violations; days for repeated offense; effectively permanent for known bad ASNs (AWS, GCP, OVH ranges).
- **Recovery**: rotate IP. No "unban" mechanism — burned IPs stay flagged.

### 2.7 Captcha triggers
- Slider/puzzle captcha shown via embedded script. Triggered by: missing msToken, expired msToken, mismatched UA/TLS, datacenter IP, request cadence anomaly, missing tt_csrf_token on write paths.
- Once triggered: persists until solved or session rotated. Cannot be bypassed by retry alone.
- Solving requires CAPTCHA-solver service (CapSolver, BrightData) or human intervention.

### 2.8 Web vs Mobile API
| Aspect | Web (`tiktok.com/api/*`) | Mobile (`api16-*.tiktokv.com/aweme/v1/*`) |
|---|---|---|
| Signing | X-Bogus + X-Gnarly + msToken | X-Argus + X-Gorgon + X-Ladon |
| Auth required | Cookies (ttwid min) | iid only, no user auth |
| Difficulty (sign) | Moderate (JS VM) | High (native protobuf+SM3+AES) |
| Rate limit | Stricter, aggressive captcha | More forgiving but stricter app-layer codes (10204) |
| Used by | Scrapfly, TikTokApi | yt-dlp, gallery-dl |

### 2.9 Regional differences
- US/EU/SEA endpoints route via different `apiX-normal-c-{region}.tiktokv.com` hosts. yt-dlp default `useast1a`; alternates `useast2a`, `c-alisg`, `c-h2`.
- EU may require GDPR cookie consent flow before ttwid is set.
- TikTok US (after 2024 ban legislation) has additional verification but is still scrapeable.
- No confirmed 451 responses; geo-blocks return content-not-available or redirect.

## 3. Detection Thresholds Table

| Event | Approx Threshold | Server Response | Notes |
|-------|-----------------|-----------------|-------|
| Plain `requests` lib (no impersonation) | 3–10 calls | 403 + TLS reject | TLS fingerprint mismatch |
| Spoofed UA only (no TLS impersonation) | 5–20 calls | 403 or captcha | HTTP/2 settings frame mismatch |
| Chrome impersonation, no cookies | 10–30 calls | Captcha challenge | Missing ttwid/msToken |
| Chrome impersonation + ttwid + msToken | 50–200 calls/IP/hour | Captcha or app code 10204 | Behavior-dependent |
| Anonymous CDN media fetch | ~3 req/min/IP | Throttle → 403 | CDN-level limit |
| Logged-in session | Higher (estimated 5–10×) | App code 10216 if scope exceeded | Tied to account, not IP |
| Mobile API `/aweme/v1/*` | ~30–60 req/min/iid | code 10204 | iid rotation extends |
| Official Research API | 1000/day | 429 `rate_limit_exceeded` | Hard limit |

*Thresholds are observational ranges from community reports — TikTok does not publish them and adjusts dynamically.*

## 4. Cookie/Token Requirements Table

| Cookie/Token | Required For | Source | Lifetime | Risk if Missing |
|---|---|---|---|---|
| ttwid | Almost all web API | Auto-set on first GET tiktok.com | ~1 year | Captcha immediately |
| msToken | `/api/post/*`, `/api/recommend/*` | JS sets after page load | Hours | Captcha on call |
| tt_csrf_token | Write endpoints, comments | Page meta tag | Session | 403/401 |
| tt_webid_v2 | Some video URL bindings | Auto-set | ~1 year | URL invalid |
| sessionid | Authenticated calls only | Login flow | ~30 days | Anonymous mode (lower quota) |
| sid_tt / sid_guard | Logged-in API | Login flow | ~30 days | Falls back to anonymous |
| odin_tt | Mobile API | Client-generated random hex | Per-request | Mild — yt-dlp regenerates |
| iid (install ID) | Mobile API | Device-assigned | Persistent | App code 10204 |
| device_id | Both APIs | Generated, hex 19-digit | Persistent | Captcha |

## 5. Recommended Mitigations (Ranked by Effectiveness)

| Rank | Mitigation | Impact | Cost | Notes |
|------|-----------|--------|------|-------|
| 1 | `curl_cffi --impersonate chrome-131` | **Eliminates 403 from TLS** | Free | Already in prior CDN plan |
| 2 | Residential proxy rotation (e.g. BrightData, ProxyEmpire) | Eliminates IP bans | $$$ | Datacenter mostly burned |
| 3 | Headless-browser msToken+ttwid acquisition (Playwright) | Bypasses captcha | Moderate compute | Refresh every ~30 min |
| 4 | Cookie-from-browser (logged-in session) | Higher quota, private content | User must login | Increases fingerprint risk |
| 5 | Request cadence: 1–3s jitter, max 3 concurrent | Stays under CDN limit | Free | Combine with #1 |
| 6 | Exponential backoff on 403/429 (1s→2→4→8, max 60s) | Recovers from transient throttle | Free | Standard pattern |
| 7 | Mobile API (yt-dlp pathway) over web | Avoids X-Bogus complexity | Free | yt-dlp handles it |
| 8 | App version pool rotation (yt-dlp `_APP_INFO_POOL`) | Survives single-version bans | Free | Already in yt-dlp |
| 9 | Tor (zzzjano/TikTok-API approach) | Free IP rotation | Slow, often blocked | Last resort |
| 10 | Paid third-party APIs (Apify, ScrapFly, EnsembleData, TikAPI) | Outsource problem entirely | $$$$ | Skip for personal-use tool |

### Architectural fit for tiktokder
Project is local desktop downloader (PySide6 + yt-dlp). Recommended stack:
- **Default path**: yt-dlp + `curl_cffi` impersonate chrome-131 + cookies-from-browser (already in prior plan).
- **No proxy** by default (out of scope, user-paid).
- **Backoff**: implement on top of yt-dlp's built-in retries — use `--sleep-requests 1 --sleep-interval 1 --max-sleep-interval 3 --retries 5` per CDN throttling report.
- **Skip web API entirely** — yt-dlp uses mobile API, avoiding X-Bogus/X-Gnarly maintenance burden. Don't reinvent.
- **Captcha**: out of scope for offline tool. If hit, surface error to user and suggest cookie refresh.

## 6. Sources

- [Engineering TikTok Downloaders (earezki, 2026-02)](https://earezki.com/ai-news/2026-02-22-every-tiktok-downloader-quirk-i-hit-building-dltkkto-and-how-i-fixed-them/)
- [yt-dlp tiktok extractor source](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/tiktok.py)
- [yt-dlp tiktok issue #10213 — new info path](https://github.com/yt-dlp/yt-dlp/issues/10213)
- [yt-dlp tiktok issue #14859 — extraction failures](https://github.com/yt-dlp/yt-dlp/issues/14859)
- [davidteather/TikTok-Api issue #946 — captcha](https://github.com/davidteather/TikTok-Api/issues/946)
- [davidteather/TikTok-Api discussion #438 — IP bans](https://github.com/davidteather/TikTok-Api/discussions/438)
- [davidteather/TikTok-Api issue #724 — verifyFp deprecation](https://github.com/davidteather/TikTok-Api/issues/724)
- [TikTokApi v7 docs — ms_token](https://davidteather.github.io/TikTok-Api/TikTokApi.html)
- [justbeluga tiktok-web-reverse-engineering — X-Bogus/X-Gnarly](https://github.com/justbeluga/tiktok-web-reverse-engineering)
- [int4444 tiktok-api — security algo overview](https://github.com/int4444/tiktok-api)
- [Scrapfly TikTok scraping guide](https://scrapfly.io/blog/posts/how-to-scrape-tiktok-python-json)
- [ScrapeOps TikTok teardown — Akamai Bot Manager 9/10](https://scrapeops.io/websites/tiktok/)
- [ScrapeCreators platform-by-platform guide](https://scrapecreators.com/blog/what-happens-when-social-media-companies-catch-you-scraping-a-platform-by-platform-guide)
- [TikTok official rate limit docs](https://developers.tiktok.com/doc/tiktok-api-v2-rate-limit)
- [WebScraping.AI — IP ban recovery](https://webscraping.ai/faq/tiktok-scraping/what-to-do-if-my-ip-gets-banned-while-scraping-tiktok)
- [WebScraping.AI — detection signs](https://webscraping.ai/faq/tiktok-scraping/what-are-the-signs-that-tiktok-has-detected-my-scraping-activity)
- [Internal CDN throttling report (2026-03-21)](D:\Projects\tiktokder\plans\reports\research-260321-1955-tiktok-cdn-throttling.md)

## 7. Unresolved Questions

1. Exact lifetime of msToken in 2026 — varies by report (30 min–4 h). Empirical test needed.
2. Does Vietnam/SEA region have stricter or looser limits than US? (project user is in VN per git config)
3. Is X-Gnarly 5.1.3 (Nov 2025) still current in April 2026, or has 5.2.x shipped?
4. yt-dlp's `_APP_INFO_POOL` rotation — current pool size and rotation cadence not visible in fetched excerpt.
5. Whether tiktokder needs any web-API path at all, or yt-dlp's mobile API path is sufficient for all use cases (channel listing, etc.) — likely yes since yt-dlp handles `/users/{user}` listings via the same `/aweme/v1/*` endpoints.
6. Captcha recovery in headless context — Playwright + manual solver vs surface-to-user tradeoff for desktop app.

---

**Status:** DONE
**Summary:** TikTok scraping defended by ~3 req/min/IP CDN limit + behavioral fingerprinting (TLS/HTTP2/cookies) + rotating signatures (msToken, X-Bogus, X-Gnarly v5.1.3). yt-dlp with `curl_cffi` chrome-131 impersonation + ttwid/msToken cookies + 1–3s jitter is the optimal local-desktop approach; tiktokder should not reimplement signing.
