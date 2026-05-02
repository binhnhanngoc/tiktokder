"""Internal signal functions for ``health_check.compute_health``.

Each ``_check_*`` is pure: takes channels/records/config/cache + injectable
``now``, returns ``list[HealthIssue]``. Helpers here are module-private —
public types come from ``health_check``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from health_check import FixActionKind, HealthIssue, Severity

logger = logging.getLogger(__name__)

PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
PYPI_CACHE_TTL = timedelta(hours=24)
RELEASES_URL = "https://github.com/yt-dlp/yt-dlp/releases"
_HANDLE_RE = re.compile(r"@([A-Za-z0-9._-]+)")


# ── helpers ───────────────────────────────────────────────────────────────


def _parse_iso(s: str | None) -> datetime | None:
    """ISO8601 → aware datetime; tolerates trailing ``Z``. ``None`` on bad input."""
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _ensure_utc(dt: datetime) -> datetime:
    """Naive → UTC; aware → converted to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_handle(url: str) -> str:
    """Best-effort uploader handle from a saved-channel URL (lowercase, no @).

    Only the URL **path** is searched so query-string ``@``s (tracking
    params, share refs) cannot poison the handle. Returns empty string
    when the path has no recognizable handle.
    """
    if not url:
        return ""
    try:
        path = urlparse(url).path
    except (ValueError, TypeError):
        return ""
    match = _HANDLE_RE.search(path)
    if match:
        return match.group(1).lower()
    stripped = path.strip("/")
    if not stripped:
        return ""
    return stripped.split("/")[-1].lower()


def _has_at_handle(url: str) -> bool:
    """True only when the URL path carries a TikTok-style ``@username`` token."""
    try:
        return bool(_HANDLE_RE.search(urlparse(url or "").path))
    except (ValueError, TypeError):
        return False


def _all_channels(channels: Any) -> list[Any]:
    """Accept SavedChannelsStore, list, or any iterable; flatten to a list."""
    if hasattr(channels, "tiktok") and hasattr(channels, "facebook"):
        return list(channels.tiktok) + list(channels.facebook)
    return list(channels) if channels else []


def _is_facebook(url: str) -> bool:
    return "facebook.com" in (url or "").lower()


def _channel_cookies_set(config: Any, channel: Any) -> bool:
    """True when the user has configured cookies for the channel's platform."""
    url = getattr(channel, "url", "") or ""
    if _is_facebook(url):
        return bool(getattr(config, "facebook_cookies_file", None))
    return bool(
        getattr(config, "tiktok_cookies_file", None)
        or getattr(config, "cookie_browser", None)
    )


def _cookies_path_for_channel(config: Any, channel: Any) -> str:
    """Return the cookies file path relevant to the channel's platform (or '')."""
    url = getattr(channel, "url", "") or ""
    if _is_facebook(url):
        return getattr(config, "facebook_cookies_file", None) or ""
    return getattr(config, "tiktok_cookies_file", None) or ""


def _pypi_calver_to_date(version: str) -> datetime | None:
    """Parse yt-dlp ``YYYY.MM.DD`` into a UTC datetime; ``None`` on malformed."""
    parts = (version or "").split(".")
    if len(parts) < 3:
        return None
    try:
        return datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def _fetch_pypi_version() -> str | None:
    """One-shot HTTPS fetch of yt-dlp's PyPI version. Swallows all errors."""
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None
    info = data.get("info") if isinstance(data, dict) else None
    if isinstance(info, dict):
        version = info.get("version")
        if isinstance(version, str):
            return version
    return None


# ── signal functions ──────────────────────────────────────────────────────


def _check_stale(channels: list[Any], now: datetime) -> list[HealthIssue]:
    """Channels not refreshed in ≥14d (info) or ≥30d (warn)."""
    out: list[HealthIssue] = []
    for ch in channels:
        last = _parse_iso(getattr(ch, "last_fetched_at", None))
        if last is None:
            continue
        days = (now - _ensure_utc(last)).days
        if days >= 30:
            sev: Severity = "warn"
        elif days >= 14:
            sev = "info"
        else:
            continue
        nick = (getattr(ch, "nickname", "") or "").strip()
        label = nick or _extract_handle(getattr(ch, "url", "")) or ch.url
        out.append(HealthIssue(
            id=f"stale_fetch:{ch.url}",
            severity=sev,
            title=f"{label} hasn't been refreshed in {days}d",
            detail="Run Refresh on the channel to re-check for new uploads.",
            fix_action_kind="refresh_channel",
            fix_action_arg=ch.url,
        ))
    return out


def _check_auth_wall(
    channels: list[Any], config: Any, now: datetime
) -> list[HealthIssue]:
    """Recent fetch returned zero rows despite cookies being set."""
    out: list[HealthIssue] = []
    for ch in channels:
        last = _parse_iso(getattr(ch, "last_fetched_at", None))
        if last is None or (now - _ensure_utc(last)).days > 7:
            continue
        ids = getattr(ch, "last_fetched_video_ids", None) or []
        if ids:
            continue
        if not _channel_cookies_set(config, ch):
            continue
        cookies_path = _cookies_path_for_channel(config, ch)
        kind: FixActionKind = "open_path" if cookies_path else "none"
        out.append(HealthIssue(
            id=f"auth_wall:{ch.url}",
            severity="warn",
            title=f"{_extract_handle(ch.url) or ch.url}: empty result despite cookies",
            detail="Cookies may have expired. Re-export and replace the file.",
            fix_action_kind=kind,
            fix_action_arg=cookies_path,
        ))
    return out


def _check_no_new_downloads(
    channels: list[Any], records: Iterable[Any], now: datetime
) -> list[HealthIssue]:
    """Saved channel previously downloaded from, but no recent activity (info)."""
    out: list[HealthIssue] = []
    if not channels:
        return out

    # Build latest-download map keyed by lowercased uploader handle.
    latest: dict[str, datetime] = {}
    for r in records or []:
        uploader = (getattr(r, "uploader", "") or "").lower().lstrip("@")
        if not uploader:
            continue
        dt = _parse_iso(getattr(r, "downloaded_at", None))
        if dt is None:
            continue
        dt = _ensure_utc(dt)
        if uploader not in latest or dt > latest[uploader]:
            latest[uploader] = dt

    cutoff = now - timedelta(days=30)
    for ch in channels:
        url = getattr(ch, "url", "") or ""
        # Skip URLs without an explicit `@handle` to avoid false matches
        # against generic path tokens like ``profile.php`` or numeric IDs.
        if not _has_at_handle(url):
            continue
        handle = _extract_handle(url)
        key = handle.lstrip("@")
        if not key:
            continue
        last = latest.get(key)
        if last is None or last >= cutoff:
            # No history → not a "stopped downloading" signal. Recent → healthy.
            continue
        days = (now - last).days
        out.append(HealthIssue(
            id=f"no_new_downloads:{ch.url}",
            severity="info",
            title=f"{handle} — no new downloads in {days}d",
            detail="Channel may be inactive or filters skipped recent uploads.",
            fix_action_kind="refresh_channel",
            fix_action_arg=ch.url,
        ))
    return out


def _check_login_required(
    channels: list[Any], config: Any, cache: dict[str, Any]
) -> list[HealthIssue]:
    """Channel marked ``LoginRequired`` on its last fetch (error)."""
    out: list[HealthIssue] = []
    outcomes = cache.get("fetch_outcomes", {}) or {}
    for ch in channels:
        url = getattr(ch, "url", "")
        if outcomes.get(url) != "LoginRequired":
            continue
        cookies_path = _cookies_path_for_channel(config, ch)
        kind: FixActionKind = "open_path" if cookies_path else "none"
        out.append(HealthIssue(
            id=f"login_required:{url}",
            severity="error",
            title=f"{_extract_handle(url) or url}: login wall on last fetch",
            detail="Refresh cookies — yt-dlp could not load this channel without login.",
            fix_action_kind=kind,
            fix_action_arg=cookies_path,
        ))
    return out


def _check_cookies_age(config: Any, now: datetime) -> list[HealthIssue]:
    """``cookies.txt`` mtime ≥60d (warn) or ≥120d (error), per platform."""
    out: list[HealthIssue] = []
    targets = (
        ("TikTok", "tiktok_cookies_file"),
        ("Facebook", "facebook_cookies_file"),
    )
    for label, attr in targets:
        path = getattr(config, attr, None)
        if not path:
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        age_days = (now - datetime.fromtimestamp(mtime, tz=timezone.utc)).days
        if age_days >= 120:
            sev: Severity = "error"
        elif age_days >= 60:
            sev = "warn"
        else:
            continue
        out.append(HealthIssue(
            id=f"cookies_old:{attr}",
            severity=sev,
            title=f"{label} cookies file is {age_days}d old",
            detail="Re-export cookies if logins start failing.",
            fix_action_kind="open_path",
            fix_action_arg=path,
        ))
    return out


def _check_yt_dlp(
    cache: dict[str, Any],
    now: datetime,
    *,
    online: bool,
    frozen: bool,
) -> list[HealthIssue]:
    """Compare installed yt-dlp version vs cached PyPI latest (24h cache).

    ``online=True`` triggers a fresh PyPI fetch when the cache is stale or
    empty. Network failures are silent — caller should not assume the cache
    was updated.
    """
    try:
        from yt_dlp.version import __version__ as installed
    except Exception:
        return []

    pypi = cache.get("yt_dlp_pypi_version")
    checked = _parse_iso(cache.get("yt_dlp_checked_at"))
    needs_refresh = online and (
        checked is None or (now - _ensure_utc(checked)) > PYPI_CACHE_TTL
    )
    if needs_refresh:
        fetched = _fetch_pypi_version()
        if fetched is not None:
            pypi = fetched
            cache["yt_dlp_pypi_version"] = fetched
            cache["yt_dlp_checked_at"] = now.isoformat()
    if not pypi or installed == pypi:
        return []
    inst_d = _pypi_calver_to_date(installed)
    pypi_d = _pypi_calver_to_date(pypi)
    if inst_d is None or pypi_d is None or pypi_d <= inst_d:
        return []
    delta_days = (pypi_d - inst_d).days
    sev: Severity = "warn" if delta_days >= 60 else "info"
    if frozen:
        kind: FixActionKind = "open_url"
        arg = RELEASES_URL
        detail = "Open the releases page to download the latest build."
    else:
        kind = "none"
        arg = ""
        detail = "Run `pip install -U yt-dlp` in your environment."
    return [HealthIssue(
        id="yt_dlp_outdated",
        severity=sev,
        title=f"yt-dlp {installed} → latest {pypi} ({delta_days}d behind)",
        detail=detail,
        fix_action_kind=kind,
        fix_action_arg=arg,
    )]
