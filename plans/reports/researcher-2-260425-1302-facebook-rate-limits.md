# Facebook/Meta Video Scraping: Detection, Rate Limits & Access Patterns

**Researcher:** researcher-2
**Date:** 2026-04-25
**Scope:** Facebook video scraping for project tiktokder (yt-dlp based downloader)

---

## 1. Executive Summary

Facebook is the **hardest of mainstream video platforms** to scrape reliably. Unlike TikTok, FB has aggressively pushed video content behind login walls since 2023; anonymous access is now narrow, fragile, and degrading further:

- **mbasic.facebook.com** (long-time anonymous escape hatch) was **deprecated by Meta in Oct 2024** for "security reasons". No longer a viable downloader path.
- **m.facebook.com** still partially works but increasingly redirects to `/login/` for video pages; yt-dlp issues from 2025 confirm "Cannot parse data" failures driven by login-wall HTML being returned.
- **fb.watch** shortlinks resolve to login-redirected URLs without cookies in many regions.
- Meta does not publish scraping rate limits. Empirical floor from third-party scrapers: **~1000 video/post requests per anon IP** before login wall hardens; **200 req/hour** typical "safe" ceiling for authenticated GraphQL.
- Detection is **multi-signal** (TLS+UA+headers+IP+behavioral), not just request count. A clean residential IP with browser-like fingerprint can survive far longer than a pristine cookie set on a datacenter IP.
- Cookie-only auth works for downloads but cookies expire in **7-30 days** and trigger checkpoint if account login pattern looks unusual.

**Bottom line for tiktokder:** Treat FB as best-effort. Public-only mode using `facebookexternalhit/1.1` UA + low concurrency for fb.watch / public pages. Optional cookie injection for users who provide their own cookies.txt. **Do not** attempt programmatic login.

---

## 2. Key Findings With Evidence

### 2.1 yt-dlp facebook extractor (current state)

Source: `yt_dlp/extractor/facebook.py` master branch.

- Supports URL patterns: `facebook.com`, `m.facebook.com`, localized subdomains, onion mirror, `/video/video.php`, `/photo.php`, `/watch`, `/reel/`, `/posts/`, `/groups/`, `/events/`, `/watchparty/`, `/plugins/video.php`, `/ads/library/?id=`, query forms `?v=`, `?video_id=`, `?story_fbid=`.
- **Rate-limit workaround built in:** uses UA `facebookexternalhit/1.1` for actual media chunk download; chunk size capped at 250MB. Comment in code: *"Downloads with browser's User-Agent are rate limited. Working around with non-browser User-Agent."*
- Login detection patterns checked in HTML: `">You must log in to continue"`, `id="login_form"`, `id="loginbutton"`, `class="uiInterstitialContent"`. Triggers `raise_login_required()`.
- Primary GraphQL endpoint: `/api/graphql/`.
- `fb_dtsg` token extracted from page HTML for POSTs (not used for read-only video extraction in most paths).

### 2.2 Login wall has tightened in 2024-2025

Issue threads (yt-dlp #15161, #12846, #11151 series) report:
- yt-dlp 2025.11.12 with 2,614 Firefox cookies still hitting "Cannot parse data" on newer videos; older videos and Reels often still work.
- April 2025 issue: `facebook.com/share/r/...` redirects through `web.facebook.com` then `m.facebook.com/watch` and dies at parse stage — login-wall HTML returned.
- Apify/Scrapfly 2025 guides: *"most content is locked behind authentication"*, *"most practical Facebook scraping involves authenticated browser sessions"*.

### 2.3 GraphQL request structure (replay difficulty)

To replay a working GraphQL POST you need *all* of: `fb_dtsg`, `jazoest`, `lsd` (sent as `x-fb-lsd` header), `__user` (= `c_user` cookie), `__a`, `__req`, `__rev`, `__hsi`, `dpr`, `fb_api_caller_class`, `fb_api_req_friendly_name`, `variables` (URL-encoded JSON), `server_timestamps`, `doc_id`. Sources extract each from page bootstrap JSON:
- `jazoest` → `SprinkleConfig` object
- `fb_dtsg` → `DTSGInitialData` token (rotates roughly daily for logged-in sessions)
- `lsd` → `LSD` module
- `doc_id` → per-friendly_name persisted query ID, changes across releases

**Replay note from third-party scrapers:** *"Even switching the field order can get it rejected"*. Field-order sensitivity makes naive request replication brittle.

### 2.4 mbasic deprecated

Multiple 2025 reports: Meta phased out `mbasic.facebook.com` in **October 2024**. Old "swap www → mbasic, right-click save" trick is dead. Confirmed by vivaldi/techtalk forum threads.

### 2.5 Public anonymous threshold

Most concrete number observed across third-party scrapers/community:
- **~1000 anonymous post views per IP** before persistent login modal appears. (Source: facebook-scraper README + scraper community guides.)
- After that: login wall + IP soft-ban (typically minutes to hours).
- Aggressive request rate (>10/sec) compresses this dramatically.

Scrapfly recommended "safe" production rates: **10-30 req/IP before rotation**, **5-10 min sticky sessions**, **1.5-5 sec randomized inter-request delay**.

### 2.6 facebookexternalhit UA bypass (still works, narrow)

The `facebookexternalhit/1.1` UA is Meta's own link-preview crawler. Used for OpenGraph metadata fetch. yt-dlp uses it for media chunk fetch (less rate-limited than browser UA). It does **not** bypass login walls for HTML pages — still 302s to login when content is gated. Useful only after the video URL is already known.

---

## 3. Detection Threshold Table

| Scenario | Threshold (empirical) | Outcome | Recovery |
|---|---|---|---|
| Anon IP, public posts | ~1000 req | Login modal hardens | Rotate IP or login |
| Anon IP, >10 req/s | ~50-200 req | Login modal + IP soft-ban | Wait 15min-2h |
| Anon, datacenter IP | First request | 403 / immediate login redirect | Switch to residential |
| Anon, residential IP, slow (1 req / 3-5s) | Hours-long sessions | Stays anon longer | n/a |
| Logged-in (cookies), normal browser fingerprint | ~200 req/hour | 429 or login re-challenge | Backoff + reuse same session |
| Logged-in, fast (>1 req/s burst) | Minutes | Checkpoint ("Confirm identity") | Manual recovery only |
| Logged-in, multiple IPs same account | Quick | Checkpoint or session invalidation | Re-login |
| Multiple accounts same IP | 10+ logins | Mass-checkpoint, IP blacklist | Burn IP, burn accounts |
| Graph API (official) | 200 calls/user/hour, 600/app/min | HTTP 429 | Hourly reset |

**Notes:**
- Numbers are floors, not ceilings. FB uses ML scoring; a clean fingerprint extends limits, a dirty one collapses them.
- Account-based limits stack with IP-based limits independently.
- "Temporarily blocked" message = soft rate-limit, *not* permanent ban. Brute-forcing extends ban duration (multiple sources confirm).

---

## 4. Cookie / Session Table

### 4.1 Cookie reference

| Cookie | Purpose | Required for video access? |
|---|---|---|
| `c_user` | User ID. Presence = logged in | Yes for private/gated videos. Equals `__user` in GraphQL |
| `xs` | Session auth token (paired with `c_user`) | Yes for authenticated requests |
| `datr` | Browser-fingerprint cookie. Set on first page load. Persists across logout. Used for security/integrity scoring | Strongly recommended even anon — its absence flags as bot |
| `sb` | Browser identifier (similar role to datr) | Helpful, increases legitimacy |
| `fr` | Tracking/ad cookie tied to session+browser | Helpful for logged-in legitimacy |
| `dpr` | Device pixel ratio | Decorative. Some endpoints check |
| `locale` | UI language | Decorative |
| `wd` | Window size | Decorative; reinforces browser-like fingerprint |
| `presence` | Online presence | Optional, indicates active session |

### 4.2 Combinations that work

| Goal | Minimum cookies | Notes |
|---|---|---|
| Public video on www.facebook.com (when login wall not triggered) | None | Increasingly rare in 2025. `datr` improves success |
| Public video via `facebookexternalhit/1.1` UA | None | Works for OpenGraph + direct media URL fetch |
| fb.watch shortlink resolution | `datr` only | Often fine if anon-allowed. Else needs `c_user`+`xs` |
| Logged-in download (private, friends-only, age-gated) | `c_user` + `xs` + `datr` | Minimum viable. Add `sb`+`fr` for less suspicion |
| GraphQL POST (any) | `c_user` + `xs` + `datr` + valid `fb_dtsg`/`lsd`/`jazoest` from current page | Tokens must match the rendered page session |

### 4.3 Session token table

| Token | Source | Lifespan | Required for |
|---|---|---|---|
| `fb_dtsg` | HTML bootstrap (`DTSGInitialData`) | Per session, ~daily rotation logged-in | Any POST/GraphQL write |
| `jazoest` | HTML (`SprinkleConfig`); deterministic from `fb_dtsg` | Same as fb_dtsg | Anti-CSRF companion |
| `lsd` | HTML (`LSD` module). Sent as `x-fb-lsd` header on GraphQL | Per page load | All GraphQL requests |
| `__spin_r`, `__spin_b`, `__spin_t` | HTML; identifies code release | Per release (~hourly) | Optional but improves replay |
| `doc_id` | Per `friendly_name` GraphQL operation | Per release | Persisted-query GraphQL requires it |

---

## 5. Video Access Patterns

### 5.1 URL forms in the wild

| Pattern | Status (2025) |
|---|---|
| `https://www.facebook.com/{user}/videos/{id}/` | Often login-walled |
| `https://www.facebook.com/watch/?v={id}` | Often login-walled |
| `https://www.facebook.com/reel/{id}` | Reels often still anon |
| `https://fb.watch/{shortcode}/` | Resolves via 302 to canonical; gated content → login |
| `https://m.facebook.com/watch/?v={id}` | Mobile UA improves anon success |
| `https://www.facebook.com/share/v/{id}/`, `/share/r/{id}/` | Newer share format; redirect chain often dies at m.facebook.com login |
| `mbasic.facebook.com/...` | Deprecated Oct 2024. Dead |
| `https://www.facebook.com/plugins/video.php?href=...` | OG/embed plugin; yt-dlp uses this. Public videos still extractable |

### 5.2 HTTP responses on block

| Code | Meaning in FB context |
|---|---|
| **302** to `/login/` or `/login.php` | Anon hitting gated content. Most common block signal |
| **302** to `/checkpoint/` | Logged-in account flagged. Manual identity confirmation required |
| **404** | Video deleted, private, or geo-restricted (FB returns 404 for many privacy denials) |
| **429** | Rate-limited. Rare with anon — FB usually 302s instead. Common on Graph API |
| **403** | IP blacklisted (datacenter ranges) or hard ban |
| **200** with login-wall HTML | The yt-dlp "Cannot parse data" path. HTML returned but no video JSON inline |
| **200** with `class="uiInterstitialContent"` | Age-gated / sensitivity interstitial |

### 5.3 Public vs login-required (current as of late 2025/early 2026)

- **Usually public:** Reels from public Pages; videos shared to public groups; pages of large public figures; videos embedded via `/plugins/video.php`.
- **Usually login-required:** Profile videos from individual users; "Watch" tab personalized feed; group-restricted; age-gated; videos with location/audience restrictions; *anything* once anon view counter trips.
- **Always login-required:** Private profile videos; private group content; live streams during/after with audience restrictions.

### 5.4 Checkpoint flow (account-level)

Triggers (combined): rapid requests, unfamiliar device fingerprint, geo jump, known-bad IP, password leaked in breach DB, automation API patterns. Result: full UI block, redirect to `/checkpoint/`, requires:
1. Email/SMS code (sometimes), or
2. Photo ID upload (selfie or government), or
3. Trusted contact verification.

**Cannot be programmatically bypassed.** Once an account checkpoints, the cookies are dead until manual recovery.

---

## 6. Recommended Mitigations (Ranked)

For tiktokder integration. Ranked by effort/value ratio.

### Tier 1 — Apply now (cheap, high value)
1. **Use `facebookexternalhit/1.1` UA for media chunk downloads.** Already done by yt-dlp. Verify project not overriding it.
2. **Inter-request delay 2-5s with jitter** for any FB calls (project already exposes `--delay`; default 1.0s is too aggressive for FB — bump per-platform default).
3. **Detect login-wall HTML early** (`id="login_form"`, `"You must log in"`, redirect to `/login/`) and surface to user as "login required" rather than retrying. yt-dlp already does this; ensure GUI/CLI wrap doesn't re-attempt.
4. **Cookie file support (read-only).** Allow user to supply `cookies.txt` (Netscape format) via `--cookies` / GUI setting; pass through to yt-dlp `--cookies` flag. **Do not** automate login.
5. **Drop datacenter IPs.** If users report blanket failures, document residential connection / VPN as workaround.

### Tier 2 — Worth considering
6. **Per-platform rate-limit config.** Separate `delay`, `workers`, `max_per_session` for TikTok vs FB. FB needs lower concurrency (workers=1 safest, 2 max).
7. **Session warmup.** Before first video extraction, do one GET to `https://www.facebook.com/` to acquire `datr`/`sb` cookies in the same session jar; reuses across video calls. Reduces "cold first request" detection.
8. **Backoff on 302 to login or 429.** Exponential backoff capped at ~30min; do not retry indefinitely (will compound the IP penalty).
9. **fb.watch resolver.** Pre-resolve shortlinks via HEAD/GET with redirect-follow disabled; if 302 location contains `/login`, fail fast with clear message. Avoids wasting yt-dlp parse cycles.
10. **Browser cookie import** (`--cookies-from-browser firefox|chrome`) if users have FB logged in locally. yt-dlp supports natively.

### Tier 3 — Higher effort, optional
11. **Browser fingerprint impersonation** via `curl_cffi` / yt-dlp `--impersonate chrome` (added 2024 in yt-dlp). Helps when TLS fingerprint is the block reason. Already supported by yt-dlp; expose flag.
12. **Proxy rotation hooks.** Allow user to plug in proxy URL; rotate per-session (not per-request, FB tracks session continuity). Document residential providers; do not bundle.
13. **Page-video discovery split.** For `--facebook-page` mode, the page listing scrape and per-video extract have different risk profiles. Listing benefits from longer warmup; per-video can use external_hit UA. Currently bundled — separating allows finer rate control.

### Anti-patterns — Do not implement
- Programmatic login (CSRF, captcha, checkpoint risk; 2FA breaks it; user account jeopardy).
- Multi-account rotation (mass-checkpoint risk; ToS-hostile).
- Aggressive parallel downloads from same IP (compresses anon threshold).
- Token re-signing without page bootstrap (replay rejected; field-order sensitive).
- Hard-coding `fb_dtsg` / `doc_id` (rotates; will silently break).
- Retrying past 429/302 without backoff (extends ban).

---

## 7. Quick-Reference: Suggested Defaults for tiktokder

```python
FACEBOOK_DEFAULTS = {
    "delay_seconds": 3.0,            # vs TikTok ~1.0
    "delay_jitter": 1.5,             # +/- random
    "max_workers": 1,                # serial safest; 2 with caution
    "request_timeout": 30,
    "ua_for_media": "facebookexternalhit/1.1",
    "ua_for_html": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36",  # match real browser
    "warmup_url": "https://www.facebook.com/",
    "max_retries_per_video": 2,      # not 5+; FB compounds penalty
    "backoff_initial_s": 30,
    "backoff_max_s": 1800,
    "login_wall_markers": [
        'id="login_form"',
        'id="loginbutton"',
        'You must log in to continue',
        'class="uiInterstitialContent"',
    ],
}
```

---

## 8. Unresolved Questions

1. **Current empirical anon threshold for fb.watch shortlinks specifically** — community quotes 1000 posts/IP, but no recent (2025) measurement isolated to video-only flows. Worth a controlled experiment if FB downloads become the project's heavy path.
2. **`--impersonate` flag effectiveness against FB specifically** — yt-dlp supports curl_cffi-based TLS impersonation. Issue #15161 *title* says "impersonation needed" but no comments confirm it as the fix. Test required.
3. **Per-region behavior** — login-wall aggressiveness varies by region (EU stricter due to GDPR/DSA). Project users' geographic distribution unknown; could affect default tuning.
4. **GraphQL persisted-query rotation cadence** — `doc_id` values rotate; need monitoring strategy if project ever moves beyond yt-dlp to direct GraphQL.
5. **Reels API stability** — Reels were the last reliable anon-accessible video type. Anecdotally still working as of late 2025; may erode in 2026 as FB unifies feeds.
6. **fb_dtsg lifetime for cookie-only sessions** — varies; some sources say per-session, others ~daily. Matters only if project ever does GraphQL POSTs (currently doesn't).

---

**Status:** DONE
**Summary:** FB scraping is auth-walled, multi-signal detected, and degrading. yt-dlp's existing extractor handles most public cases via `facebookexternalhit` UA trick. Recommended: per-platform conservative defaults (delay 3s, workers 1, no login automation), cookie-file passthrough only, login-wall fast-fail, residential-IP guidance.
**Concerns/Blockers:** None. Empirical thresholds are floors not ceilings — production tuning should monitor actual block rates.
