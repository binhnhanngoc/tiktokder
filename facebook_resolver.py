"""Pre-resolve `fb.watch` shortlinks to detect login walls before yt-dlp invocation.

`fb.watch/<id>` is a 302 → either canonical `facebook.com/watch/?v=<id>` or
`facebook.com/login/?next=...` depending on geo/cookies/asn. Resolving the
first hop ourselves saves wasted yt-dlp retry budget and surfaces a clean
`login_required` error fast.

Fail-open: any network/import error returns `(url, "unknown")` so callers
fall through to yt-dlp instead of hard-failing.
"""

import logging
import re

logger = logging.getLogger(__name__)


_SHORTLINK_PATTERN = re.compile(r"^https?://fb\.watch/", re.IGNORECASE)

# Cap body inspection at 50KB — login interstitials are tiny; large pages waste memory.
_BODY_SCAN_LIMIT = 50_000


def is_fb_shortlink(url: str) -> bool:
    """True iff `url` is an `fb.watch/...` shortlink."""
    return bool(_SHORTLINK_PATTERN.match(url.strip()))


def resolve_fb_shortlink(
    url: str, timeout: float = 5.0
) -> tuple[str, str]:
    """Resolve an `fb.watch` shortlink one hop.

    Returns `(canonical_url, status)` where `status` is:
    - `"login_required"` — redirect Location or body markers indicate login wall.
    - `"ok"` — clean redirect or 200 without markers; canonical_url is the next URL.
    - `"unknown"` — network error / timeout / unexpected status; fail-open.

    Uses `curl_cffi` chrome131 impersonation (same TLS profile yt-dlp uses
    elsewhere) to avoid creating a second fingerprint surface.
    """
    # Lazy imports keep this module load-light and tolerant of curl_cffi import failure.
    try:
        from curl_cffi import requests as cffi_requests
    except Exception:  # pragma: no cover - defensive: curl_cffi already required
        logger.debug("curl_cffi unavailable; skipping fb.watch pre-resolution")
        return (url, "unknown")

    from config import FB_LOGIN_WALL_MARKERS

    try:
        session = cffi_requests.Session(impersonate="chrome131")
        try:
            response = session.get(url, allow_redirects=False, timeout=timeout)
        finally:
            session.close()
    except Exception as exc:
        logger.debug(f"fb.watch resolve failed for {url}: {exc}")
        return (url, "unknown")

    status = getattr(response, "status_code", 0)

    if 300 <= status < 400:
        location = response.headers.get("Location", "") or ""
        if "/login" in location.lower() or "login.php" in location.lower():
            return (url, "login_required")
        return (location or url, "ok")

    if status == 200:
        body = (response.text or "")[:_BODY_SCAN_LIMIT]
        if any(marker in body for marker in FB_LOGIN_WALL_MARKERS):
            return (url, "login_required")
        return (url, "ok")

    return (url, "unknown")
