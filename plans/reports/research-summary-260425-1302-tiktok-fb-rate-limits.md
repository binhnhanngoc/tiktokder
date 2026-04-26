---
name: research-summary-tiktok-fb-rate-limits
description: Synthesized research on TikTok/Facebook scraping rate limits, detection, backoff, and IP/cookie/fingerprint mitigation for tiktokder
type: synthesis
date: 2026-04-25
sources:
  - researcher-1-260425-1302-tiktok-rate-limits.md
  - researcher-2-260425-1302-facebook-rate-limits.md
  - researcher-3-260425-1302-backoff-strategies.md
  - researcher-4-260425-1304-proxy-fingerprinting.md
---

# Research Summary — TikTok/Facebook Scraping Rate Limits, Throttling, IP/Cookie Restrictions

**Date:** 2026-04-25
**Project:** tiktokder (PySide6 + yt-dlp local desktop downloader, Windows)
**Team:** 4 parallel researchers (TikTok, Facebook, backoff strategies, proxy/fingerprinting)

---

## 1. Executive Summary

Modern detection on both platforms is **multi-signal and behavioral**, not count-based. A pristine cookie set on a datacenter IP fails fast; a clean residential IP with browser-faithful TLS fingerprint can survive far longer than published "limits" suggest. Counting requests is the wrong frame — fingerprint correctness, request cadence variance, and cookie/TLS continuity dominate.

**Single highest-leverage change for tiktokder:** wrap yt-dlp HTTP layer in `curl_cffi` chrome-131 impersonation. This alone eliminates instant-403 from TLS fingerprint mismatch — the dominant first-request block reason on both platforms.

**Asymmetry to remember:** TikTok blocks **loud** (captcha pages, 403, custom app codes 10204/10216). Facebook blocks **silent** (302→login, shadow-bans, account flags surfacing days later). Debugging strategy must differ per platform.

**Scope guidance:** tiktokder is a single-user desktop tool. Cookie-pool rotation, captcha-solver subscriptions, and multi-account flows are **out of scope**. Proxy support stays optional/off-by-default. Concentrate effort on the P0+P1 changes: fingerprint impersonation, jittered pacing, per-platform defaults, login-wall fast-fail.

---

## 2. Key Findings — Comparative Analysis

### 2.1 Rate-limit reality (both platforms)

| Aspect | TikTok | Facebook |
|---|---|---|
| Stated limit | None (only Research API: 1000/day) | None (Graph API: 200/user/hr) |
| CDN-level cap | ~3 req/min/IP (CDN throttle → 403) | No fixed cap; behavioral collapse on >10 req/s |
| Anonymous "safe" budget | 30–60 req/min/IP soft, 5–10 sustained | ~1000 req/IP before login wall hardens; 10–30 before rotate is safer |
| Authenticated "safe" budget | 5–10× anonymous, tied to account | ~200 req/hr/session |
| Block recovery | Minutes–hours (cadence) to days (repeated) | Minutes–hours (soft) to manual checkpoint (account) |
| Detection model | Behavioral + signature validity | Multi-signal ML scoring |

**Numbers are floors not ceilings.** Both platforms ML-score and adjust dynamically. Same IP can pass 100s of requests if "human-like" or fail at 5 if not.

### 2.2 Detection vector → response map (consolidated)

| Vector | TikTok | Facebook |
|---|---|---|
| Datacenter ASN | Instant 403/captcha | Instant 302→login or 403 |
| Mismatched TLS (JA4) vs UA | Slider captcha | `/checkpoint/` redirect |
| HTTP/2 settings hash mismatch | Empty `itemList` (shadow) | Empty graph response |
| Missing `Sec-Fetch-*` / Client Hints | Captcha or 403 | Login challenge |
| Cookie replayed across IPs | `msToken` invalidated | Forced re-auth/2FA |
| Velocity excess | 429 → progressive ban (10min/1hr/IP) | 429 → `temporary_blocked` flag |
| Signature mismatch (X-Bogus invalid) | 401/403 | N/A |
| Headless browser flags | Captcha or shadow-ban | Captcha or login required |

### 2.3 Signature / token systems

**TikTok web** (avoid reimplementing — yt-dlp uses mobile path):
- `msToken` (session, hours TTL) — required for `/api/post/*`, `/api/recommend/*`
- `X-Bogus` (URL-param sig: 2×MD5 → RC4 → b64)
- `X-Gnarly` 5.1.x (post-2025, rotates ~quarterly; 5.1.3 confirmed Nov 2025)
- `_signature` (legacy, phasing out)

**TikTok mobile** (yt-dlp path):
- `X-Argus` (protobuf + SM3 + SIMON + AES — very high effort)
- `X-Gorgon` + `X-Khronos` (legacy, paired)
- `X-Ladon`, `X-Helios` (newer builds)
- `iid` (install ID) replaces user auth

**Facebook GraphQL** (out of scope for read-only video):
- `fb_dtsg`, `jazoest`, `lsd` (CSRF triad)
- `doc_id` (rotates per release, persisted-query ID)
- Field-order-sensitive — naive replay rejected

### 2.4 Required cookies (consolidated)

| Cookie | Platform | Purpose | Required for |
|---|---|---|---|
| `ttwid` | TikTok | Device tracking | All TikTok web API |
| `msToken` | TikTok | Session token | Most `/api/*` |
| `tt_csrf_token` | TikTok | CSRF | Write paths |
| `sessionid` / `sid_tt` | TikTok | Auth | Higher quota, private content |
| `c_user` + `xs` | Facebook | Auth | Private/gated video |
| `datr` | Facebook | Browser fingerprint | Strongly recommended even anon |
| `sb`, `fr` | Facebook | Browser/session | Logged-in legitimacy |
| `wd`, `dpr`, `locale` | Facebook | Decorative | Reinforces browser-like fingerprint |

**Critical insight (researcher-4):** Cookies are **TLS-bound**. Cookies captured in real Chrome and replayed via `python-requests` fail ~80% of the time on login-walled endpoints. Capture and replay must occur within the same TLS impersonation profile (matching JA4).

### 2.5 Proxy / IP recommendations

| Type | TikTok | Facebook | Cost | tiktokder fit |
|---|---|---|---|---|
| Datacenter | Burned | Burned | $0.20–1/GB | Avoid |
| ISP static | Limited | Limited | $1.50–5/IP | Edge cases |
| Residential rotating | Good | Good | $1.75 (IPRoyal) – $8 (Oxylabs)/GB | **Optional flag** |
| Mobile/4G | Best | Best (whitelisted carriers) | $4–20/GB; 3–10× residential | Out of scope |

**For tiktokder:** keep proxy optional (off by default), document IPRoyal/BrightData with sticky 10-min session pattern. Don't bundle a provider.

### 2.6 Fingerprint defeat hierarchy

Detection layers (strongest → weakest defeat):

1. **TLS (JA4)** — `requests`/`httpx`/`aiohttp` all leak; only `curl_cffi`/`tls-client`/`primp` defeat
2. **HTTP/2 (Akamai hash)** — same fix; pure-Python clients can't match browser frame ordering
3. **Headers (UA ↔ Sec-CH-UA consistency)** — copy real DevTools header dict; don't generate
4. **Cookies (origin-bound)** — capture and replay within same impersonation profile
5. **JS challenges** — only headless browser fallback (`nodriver`, `camoufox`) defeats

**Library matrix (Python):**

| Library | Layer defeated | Maturity | Verdict |
|---|---|---|---|
| `curl_cffi` (chrome131) | TLS+HTTP/2+headers | Mature, 6k+ stars | **Default for tiktokder** |
| `tls-client` | TLS+HTTP/2 | Mature, sneaker-bot adoption | Alternative; cgo on Windows is painful |
| `primp` | TLS+HTTP/2 | Newer, fastest perf | Skip for v1 |
| `nodriver` | Full browser, async, CDP-direct | Active (UC successor) | Optional `--browser` fallback |
| `camoufox` | Full browser, 0% CreepJS detection | Active, Firefox-based, heavy | Overkill for tiktokder |
| `patchright` | Patched Playwright | Active | Mid-tier; skip |
| `undetected-chromedriver` | Legacy | Detected on modern WAFs | Avoid |

### 2.7 Backoff / rate-limiting / retry strategies

**Ranked algorithm picks:**
1. **Decorrelated jitter** (AWS/Polly default) — `min(cap, rand(base, prev*3))` — best at smoothing retry herds; minor "clamping flaw" at cap
2. **Retry-After honoring** — both platforms emit it on 429/503; mandatory to parse
3. **Per-host token bucket** (`pyrate-limiter`) — pre-throttles so retries are exception, not rule
4. **Circuit breaker** — open after 3 consecutive 429/captcha; cooldown 5–15 min

**Pacing distribution:**
- Constant `time.sleep(d)` → highly detectable, flat cadence
- `random.uniform(a, b)` → moderate, flat histogram
- **`random.gauss(mu, sigma)` truncated** → mimics human variance, **recommended**

**Library picks:**
- `tenacity` (primary) — sync+async, decorator API, `wait_exponential_jitter`, custom `wait_func` for decorrelated jitter
- `pyrate-limiter` (rate) — token bucket, sync+async
- Inline `CircuitBreaker` class — `pybreaker` overkill for 2 hosts
- Skip `backoff` (unmaintained 2022)

**yt-dlp config tuning:**
```python
opts.update({
    "retries": 10,                  # was 5
    "extractor_retries": 5,         # default 3
    "fragment_retries": 10,
    "file_access_retries": 3,
    "retry_sleep_functions": {
        "http": lambda n: min(60, 2**n + random.uniform(0, 1)),
        "fragment": lambda n: min(30, 2**n),
        "extractor": lambda n: min(120, 5 * (2**n)),
    },
    "sleep_interval_requests": 0.75,
    "sleep_interval": 2.0,
    "max_sleep_interval": 8.0,      # yt-dlp picks uniform(min, max)
    "socket_timeout": 30,
})
```
**Avoid:** `--retries infinite` (broken in some versions, yt-dlp #10109).

---

## 3. Per-Platform Default Recommendations for `tiktokder`

```python
TIKTOK_DEFAULTS = {
    "delay_seconds": 1.5,            # gaussian mean
    "delay_jitter_std": 0.5,
    "delay_floor": 0.2,
    "max_workers": 3,
    "request_timeout": 30,
    "impersonate": "chrome131",      # via curl_cffi
    "max_retries_per_video": 5,
    "backoff_initial_s": 2,
    "backoff_max_s": 60,
    "rate_limit_per_min": 30,        # safe ceiling
}

FACEBOOK_DEFAULTS = {
    "delay_seconds": 3.0,            # mean — FB needs slower
    "delay_jitter_std": 1.5,
    "delay_floor": 0.5,
    "max_workers": 1,                # serial safest; 2 max
    "request_timeout": 30,
    "ua_for_media": "facebookexternalhit/1.1",
    "impersonate": "chrome131",      # for HTML fetch
    "warmup_url": "https://www.facebook.com/",  # seeds datr cookie
    "max_retries_per_video": 2,      # NOT 5+; FB compounds penalty
    "backoff_initial_s": 30,
    "backoff_max_s": 1800,
    "login_wall_markers": [
        'id="login_form"',
        'id="loginbutton"',
        'You must log in to continue',
        'class="uiInterstitialContent"',
    ],
    "rate_limit_per_min": 15,
}
```

---

## 4. Recommended Migration Plan (Ranked P0 → P4)

| Priority | Change | Files | Effort | Impact |
|---|---|---|---|---|
| **P0** | Replace `time.sleep(delay)` with gaussian-jittered helper | `downloader.py` (single-line site) | 5 min | High — kills timing pattern |
| **P0** | Per-platform defaults (TikTok vs FB delay/workers/retries) | `config.py`, `downloader.py` | 30 min | High — FB needs slower |
| **P0** | Add `sleep_interval_requests`, `sleep_interval`, `max_sleep_interval`, `extractor_retries=5`, `file_access_retries=3` to `get_ydl_opts` | `downloader.py` | 10 min | High — adds yt-dlp randomization |
| **P0** | Bump `retries` 5 → 10 with custom `retry_sleep_functions` | `downloader.py` | 15 min | High — exp+jitter at HTTP layer |
| **P0** | Detect login-wall HTML early (FB) and fail-fast with clear UX message | `downloader.py` | 20 min | High — stops compounding penalty |
| **P1** | Wire `curl_cffi` impersonation via yt-dlp `--impersonate chrome-131` flag | `downloader.py`, `config.py` | 30 min | **Highest** — eliminates TLS-fingerprint 403 |
| **P1** | Wrap `download_video` in `tenacity` with Retry-After awareness | `downloader.py` | 30 min | Medium — server-honored backoff |
| **P1** | Cookie-file passthrough (`--cookies` / `--cookies-from-browser`) | `config.py`, `downloader.py` | 30 min | High — unlocks gated content (user-supplied) |
| **P1** | Pre-resolve fb.watch shortlinks; fast-fail if 302→login | `downloader.py` | 20 min | Medium — saves wasted yt-dlp cycles |
| **P2** | Per-host token bucket via `pyrate-limiter` | new `rate_limiter.py` | 1 hr | Medium — preventive, smooths bursts |
| **P2** | Inline circuit breaker class, gate downloads on consecutive failures | `downloader.py` + new module | 1 hr | Medium — prevents retry storms |
| **P2** | Optional `--proxy` flag with sticky-session URL convention | `config.py`, `downloader.py` | 1 hr | Low (out-of-scope by default; user-paid) |
| **P3** | Session warmup pre-flight for FB (GET facebook.com → seed `datr`) | new `warmup.py` | 2 hr | Low–medium (helps FB only) |
| **P4** | Optional `--browser` flag (nodriver) for endpoints failing HTTP-only | new `browser_fallback.py` | 4+ hr | Low — last-resort, Windows stability TBD |

**Recommended initial scope: all P0 + P1 (~3 hrs total).** Adds ~80% of detection-evasion lift without new heavy deps. Only new requirement is `tenacity`.

**Out of scope for v1 (single-user desktop):**
- Cookie-pool rotation (single profile = no rotation possible)
- CapSolver/captcha-solving fallback (paid API key)
- Multi-account flows
- Programmatic FB login

---

## 5. Anti-Patterns — Do Not Implement

- **Reverse-engineer X-Bogus / X-Gnarly / X-Argus** — quarterly schema rotation makes this a maintenance trap. yt-dlp's mobile API path avoids this entirely.
- **Programmatic FB login** — CSRF, captcha, checkpoint risk; 2FA breaks it; jeopardizes user account.
- **Hardcode `fb_dtsg` / `doc_id`** — rotates; will silently break.
- **`--retries infinite`** — broken in some yt-dlp versions (#10109).
- **Retry past 429/302→login without backoff** — compounds ban duration.
- **Aggressive parallel downloads from same IP** — compresses anonymous threshold.
- **Set deprecated cookies (`verifyFp`, `s_v_web_id`)** — now triggers captcha rather than bypassing it.
- **Use `httpx`/`requests`/`aiohttp` for direct TikTok or FB outbound** — instant TLS classification.

---

## 6. Cross-Researcher Consensus Points

All 4 researchers independently converged on:

1. **`curl_cffi` chrome-131 impersonation is the correct HTTP-layer baseline.** Drop-in `requests` API, mature, defeats TLS+HTTP/2+headers in one dep.
2. **yt-dlp's mobile API path is the right TikTok approach.** Don't reimplement web signing.
3. **Per-platform defaults required.** FB needs ~3× the delay and ~⅓ the concurrency of TikTok.
4. **Gaussian-jittered pacing beats uniform beats fixed.** The current `time.sleep(delay)` pattern is the single worst code smell for evasion.
5. **Login-wall detection should fast-fail, not retry.** Compounds penalty on FB; useless on TikTok captcha.
6. **Don't reverse-engineer signatures.** TikTok rotates X-Gnarly quarterly; FB rotates `doc_id` per release. Maintenance burden is a trap for a hobby project.
7. **Proxy support stays optional + user-supplied.** Don't bundle a provider; document IPRoyal residential or BrightData sticky-session as recommended options.

---

## 7. Unresolved Questions (consolidated)

**Empirical / measurement gaps:**
1. Exact `msToken` lifetime in 2026 (sources vary 30 min – 4 hr)
2. VN/SEA regional rate-limit differences (project user is in Vietnam per git config)
3. Current X-Gnarly version (5.1.3 Nov 2025 confirmed; 5.2.x possibly shipped)
4. Per-IP vs per-cookie rate scope on TikTok — sources inconsistent
5. yt-dlp `--impersonate` effectiveness against FB specifically — issue title suggests it but no confirmed fix in comments
6. Per-region FB tuning (EU stricter due to GDPR/DSA)
7. Decorrelated-jitter cap value — empirical telemetry not feasible for v1

**Architectural decisions:**
8. Async migration timing — current code is `ThreadPoolExecutor`-based; token bucket fits sync but is clunky vs `asyncio + aiolimiter`
9. Captcha budget — CapSolver costs $0.001–0.003/solve; acceptable cost ceiling for v1?
10. Single-cookie-source means cookie pool rotation is moot — confirmed scope question

**Platform-specific:**
11. Does TikTok signed-URL CDN (`*.tiktokcdn.com`) require matching JA4 to the URL-acquiring request?
12. Does FB fbcdn video URL require matching `Referer`+cookies, or is the time-limited token sufficient alone?
13. `nodriver` Windows stability (project targets Windows; nodriver tested mostly on Linux)

---

## 8. Source Reports

- `plans/reports/researcher-1-260425-1302-tiktok-rate-limits.md` — TikTok rate limits, signatures, cookies, captcha
- `plans/reports/researcher-2-260425-1302-facebook-rate-limits.md` — FB rate limits, login walls, cookies, GraphQL
- `plans/reports/researcher-3-260425-1302-backoff-strategies.md` — Backoff algorithms, tenacity, pyrate-limiter, yt-dlp tuning
- `plans/reports/researcher-4-260425-1304-proxy-fingerprinting.md` — Proxy types, TLS/HTTP2/header fingerprinting, library matrix
