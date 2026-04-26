"""Load Facebook session cookies from a Netscape-format cookies.txt file
and convert them into Playwright's cookie-dict shape so we can hand a logged-in
session to ``FacebookFetcher``.

Why Netscape format? It is the same on-disk shape that yt-dlp's ``--cookies``
flag consumes, so users can export once with a browser extension (e.g. "Get
cookies.txt LOCALLY") and reuse the file across both code paths.

Format reminder (tab-separated, comment lines start with ``#``):

    domain  flag  path  secure  expiration  name  value

The ``#HttpOnly_`` prefix on the domain field is a de-facto convention added by
curl/wget to mark HTTP-only cookies; we strip it and forward the flag.
"""

from __future__ import annotations

from pathlib import Path


# Subset of Playwright's cookie dict — keys we actually populate from Netscape
# fields. ``httpOnly`` and ``secure`` round-trip; ``sameSite`` is omitted
# because the Netscape format has no field for it (Playwright defaults to "Lax").
def load_netscape_cookies(path: str | Path) -> list[dict]:
    """Parse a Netscape ``cookies.txt`` file and return Playwright cookie dicts.

    Returns an empty list if the file does not exist. Malformed lines are
    skipped silently — the goal is best-effort recovery, not strict validation.
    """
    p = Path(path)
    if not p.is_file():
        return []

    cookies: list[dict] = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        cookie = _parse_line(raw)
        if cookie is not None:
            cookies.append(cookie)
    return cookies


def _parse_line(raw: str) -> dict | None:
    """Convert one Netscape line to a Playwright cookie dict, or None to skip."""
    line = raw.rstrip("\r\n")
    if not line.strip():
        return None

    # ``#HttpOnly_<domain>`` is a real data row — keep it. Any other ``#`` line
    # is a comment.
    http_only = False
    if line.startswith("#HttpOnly_"):
        http_only = True
        line = line[len("#HttpOnly_"):]
    elif line.startswith("#"):
        return None

    parts = line.split("\t")
    if len(parts) < 7:
        return None

    domain, _flag, path, secure_str, expires_str, name, value = parts[:7]
    if not domain or not name:
        return None

    try:
        expires = int(expires_str)
    except ValueError:
        expires = -1  # treat unparseable as session cookie

    cookie = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path or "/",
        "secure": secure_str.upper() == "TRUE",
        "httpOnly": http_only,
    }
    # Playwright treats expires=-1 as a session cookie. Only forward a positive
    # absolute timestamp; otherwise omit the field so PW falls back to session.
    if expires > 0:
        cookie["expires"] = expires
    return cookie


def filter_facebook(cookies: list[dict]) -> list[dict]:
    """Keep only cookies whose domain belongs to the facebook.com cookie scope.

    Lets users hand us an unfiltered cookies.txt without leaking unrelated
    cookies into the Playwright context.
    """
    out: list[dict] = []
    for c in cookies:
        d = (c.get("domain") or "").lstrip(".").lower()
        if d == "facebook.com" or d.endswith(".facebook.com"):
            out.append(c)
    return out


__all__ = ["load_netscape_cookies", "filter_facebook"]
