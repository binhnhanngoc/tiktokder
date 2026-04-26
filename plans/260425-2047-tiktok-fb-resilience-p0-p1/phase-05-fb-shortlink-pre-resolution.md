# Phase 05 — Facebook Shortlink Pre-Resolution (`fb.watch`)

## Context Links
- Synthesis: `plans/reports/research-summary-260425-1302-tiktok-fb-rate-limits.md` §4 (P1 item 7)
- FB research: `plans/reports/researcher-2-260425-1302-facebook-rate-limits.md` §login-walls
- Code: `url_parser.py:25-33` (`FACEBOOK_URL_PATTERN`), `downloader.py:86-107`

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** ~30 min
- **Description:** Before invoking yt-dlp on a `fb.watch/...` shortlink, perform an HTTP HEAD/GET-no-body request via `curl_cffi` (already-installed dep) with `chrome131` impersonation and `allow_redirects=False`. If 3xx Location contains `/login` or marker text appears in body, raise `LoginRequired` *before* yt-dlp is touched. Saves wasted retry budget and surfaces clean error fast.

## Key Insights
- `fb.watch/<id>` is a 302 → either canonical `facebook.com/watch/?v=<id>` *or* `facebook.com/login/?next=...` depending on geo/cookies/asn.
- yt-dlp follows the redirect itself and surfaces a generic `DownloadError` after multiple attempts. We can short-circuit at the first hop.
- `curl_cffi` already in `requirements.txt` — no new dep, and it gives us the same TLS profile yt-dlp uses (consistent classification).
- Resolved canonical URL can also be returned to the caller for normalization (future logging benefit), but not required for v1.
- Fail-open: if HEAD/GET fails for non-FB reasons (network down), proceed to yt-dlp. Don't add a hard dependency on the pre-resolve step succeeding.

## Requirements
**Functional**
- New module `facebook_resolver.py` exposing:
  - `is_fb_shortlink(url: str) -> bool` — True for `fb.watch/...`.
  - `resolve_fb_shortlink(url: str, timeout: float = 5.0) -> tuple[str, str]` — returns `(canonical_url, status)` where status is one of `"ok"`, `"login_required"`, `"unknown"`. On network/timeout error → `(url, "unknown")` (fail-open).
- `download_video` consults `is_fb_shortlink`; if True, calls `resolve_fb_shortlink`. If status is `"login_required"`, raise `LoginRequired` immediately (consumed by Phase 04 tenacity predicate → no retry → maps to `DownloadResult(error="login_required")`). If `"ok"`, replace URL with canonical and proceed. If `"unknown"`, proceed with original URL.
- HTTP request uses `curl_cffi.requests` with `impersonate="chrome131"`, `allow_redirects=False`, `timeout=5.0`.
- Reuses `FB_LOGIN_WALL_MARKERS` from Phase 03 to scan response body when redirect is ambiguous.

**Non-functional**
- Timeout strictly bounded (5s) — must not hang the worker.
- Single round-trip per URL; do not chain redirects manually (rely on the first 3xx hop signal).
- Pure stdlib + curl_cffi (no new deps).
- Thread-safe (each call creates its own session).

## Architecture
```
facebook_resolver.py
├── _SHORTLINK_PATTERN = re.compile(r"^https?://fb\.watch/", re.I)
├── is_fb_shortlink(url) -> bool
└── resolve_fb_shortlink(url, timeout=5.0) -> tuple[str, str]
     1. session = curl_cffi.requests.Session(impersonate="chrome131")
     2. r = session.get(url, allow_redirects=False, timeout=timeout)
     3. if 300 <= r.status_code < 400:
          loc = r.headers.get("Location", "")
          if "/login" in loc.lower() or "login.php" in loc.lower():
              return (url, "login_required")
          return (loc, "ok")
     4. if r.status_code == 200:
          body = r.text[:50_000]  # cap
          if any(m in body for m in FB_LOGIN_WALL_MARKERS):
              return (url, "login_required")
          return (url, "ok")
     5. except (curl_cffi.requests.RequestsError, TimeoutError):
          return (url, "unknown")  # fail-open

downloader.py
└── _do_download(...)
     if is_fb_shortlink(url):
         canonical, status = resolve_fb_shortlink(url)
         if status == "login_required":
             raise LoginRequired("fb.watch redirects to login")
         url = canonical
     # ... existing yt-dlp call ...
```

**Data flow:**
```
download_video(fb.watch/abc)
  -> is_fb_shortlink? yes
  -> resolve_fb_shortlink
       -> HEAD/GET via curl_cffi chrome131
       -> 302 Location: /login/?next=...
       -> return (url, "login_required")
  -> raise LoginRequired
  -> tenacity predicate _is_retryable -> False -> propagate
  -> download_video catches -> DownloadResult(error="login_required")
```

## Related Code Files
**Modify**
- `D:\Projects\tiktokder\downloader.py` — call `is_fb_shortlink` + `resolve_fb_shortlink` at top of `_do_download`.

**Create**
- `D:\Projects\tiktokder\facebook_resolver.py` — module described above.

**Delete** — none.

## Implementation Steps

1. **Create `facebook_resolver.py`** with the module-level pattern, `is_fb_shortlink`, and `resolve_fb_shortlink` per Architecture.
2. **Import `FB_LOGIN_WALL_MARKERS` from `config`** inside `resolve_fb_shortlink` to avoid eager module-level import cycle.
3. **Inside `_do_download` in `downloader.py`** (the post-Phase-04 internal function), before invoking yt-dlp:
   ```python
   from facebook_resolver import is_fb_shortlink, resolve_fb_shortlink
   if is_fb_shortlink(url):
       canonical, status = resolve_fb_shortlink(url)
       if status == "login_required":
           raise LoginRequired(f"fb.watch shortlink redirects to login: {url}")
       url = canonical  # use canonical for yt-dlp
   ```
4. **Add a debug log** when shortlink resolves successfully: `logger.debug(f"Resolved shortlink {url} -> {canonical}")`.
5. **Compile-check** `python -c "from facebook_resolver import is_fb_shortlink; print(is_fb_shortlink('https://fb.watch/abc/'))"` — expect `True`.
6. **Smoke test (optional, requires real FB shortlink):** run with a fresh `fb.watch` URL and confirm logs show resolution before yt-dlp invocation.

## Todo List
- [ ] Create `facebook_resolver.py` with `is_fb_shortlink`
- [ ] Implement `resolve_fb_shortlink` with curl_cffi chrome131 + 5s timeout
- [ ] Body-marker fallback using `FB_LOGIN_WALL_MARKERS` from `config`
- [ ] Wire pre-resolve into `_do_download` before yt-dlp call
- [ ] Fail-open on network errors
- [ ] Debug-log canonical URL on success
- [ ] Compile-check imports
- [ ] Manual smoke test against a real fb.watch URL (best-effort)

## Success Criteria
- `is_fb_shortlink("https://fb.watch/abc/")` returns `True`.
- `is_fb_shortlink("https://www.facebook.com/watch?v=123")` returns `False`.
- `resolve_fb_shortlink("https://fb.watch/abc/")` returns within 5s for any input (including network errors).
- A login-walled `fb.watch` URL surfaces `DownloadResult(error="login_required")` without yt-dlp ever being instantiated.
- A valid `fb.watch` URL is rewritten to canonical form before yt-dlp sees it; download proceeds normally.
- Existing tests pass.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `curl_cffi` import fails on edge Python build | Low | High | Already in `requirements.txt`, used by yt-dlp's impersonate already. If import fails at module load, fall back to `is_fb_shortlink → False` (skip pre-resolve) |
| 5s timeout too tight on slow networks | Medium | Low | Configurable via param; default 5s; fail-open returns `unknown` and proceeds to yt-dlp |
| Resolved canonical URL has tracking params yt-dlp dislikes | Low | Low | yt-dlp normalizes most FB URLs internally; if issues found, strip query params before passing |
| Pre-resolve adds 1 round-trip even for non-login-walled URLs | High | Low | Only triggers for `fb.watch` (subset); ~200ms median; net savings dominate |
| 200 OK with no login marker but actually login-walled (silent block) | Medium | Medium | Body-marker scan catches most cases; rare misses fall through to yt-dlp's own classifier (Phase 03) |

## Security Considerations
- HEAD/GET request sends only the URL — no cookies passed by default in this pre-resolve. (Cookies still flow through yt-dlp via `cookiesfrombrowser`.)
- Body capped at 50 KB to avoid memory blow-up on large FB pages.
- TLS profile matches yt-dlp's chrome131 impersonation — no new fingerprint introduced.

## Next Steps
- Phase 06 covers unit tests with mocked HTTP responses (302 → /login, 200 with marker, network error).
