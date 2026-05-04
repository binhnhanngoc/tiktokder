"""Stdlib-only check-for-updates probe against the TikTokDer GitHub repo.

Pure logic — no Qt, no threads, never raises. Imports only stdlib so unit
tests run cleanly without a display server. The module exposes a tiny
public surface (``ReleaseInfo``, ``latest_release``, ``is_newer``,
``should_check_now``) consumed by the GUI's update worker.

Network strategy:
    1. Try ``GET /repos/{repo}/releases/latest``. On 200, parse ``tag_name``.
    2. On 404 (no Release object yet, even if tags exist), fall back to
       ``GET /repos/{repo}/tags?per_page=10``. Filter by strict
       ``^v\\d+\\.\\d+\\.\\d+$`` (no pre-release tags), pick max tuple.
    3. On any other failure (timeout, garbage JSON, network down) → return
       ``None``. The caller decides whether to surface the failure.
"""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from version import __version__

_GITHUB_REPO = "binhnhanngoc/tiktokder"
_RELEASES_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
_TAGS_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/tags?per_page=10"
_SEMVER_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_USER_AGENT = f"TikTokDer/{__version__}"
_ACCEPT = "application/vnd.github+json"


@dataclass(frozen=True)
class ReleaseInfo:
    """A parsed remote release. Tag-fallback path leaves ``body`` empty."""

    version: tuple[int, int, int]
    version_str: str
    html_url: str
    body: str
    is_tag_fallback: bool


def _http_get_json_or_404(
    url: str, timeout: float
) -> tuple[str, Any]:
    """Fetch JSON. Returns ``("ok", data)``, ``("404", None)``, or ``("err", None)``.

    404 is split out so ``latest_release`` can decide to fall back to ``/tags``.
    Every other error class is collapsed into a single ``"err"`` sentinel.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": _ACCEPT},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return ("ok", json.loads(raw.decode("utf-8")))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ("404", None)
        return ("err", None)
    except (
        urllib.error.URLError,
        socket.timeout,
        TimeoutError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
    ):
        return ("err", None)
    except Exception:
        # Belt-and-braces — the public contract is "never raise".
        return ("err", None)


def _parse_release_payload(data: Any) -> ReleaseInfo | None:
    """Parse a ``/releases/latest`` JSON dict into ``ReleaseInfo``, or ``None``."""
    if not isinstance(data, dict):
        return None
    tag_name = data.get("tag_name")
    if not isinstance(tag_name, str):
        return None
    m = _SEMVER_TAG_RE.match(tag_name)
    if m is None:
        return None
    version = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    version_str = f"{version[0]}.{version[1]}.{version[2]}"
    html_url = data.get("html_url") or (
        f"https://github.com/{_GITHUB_REPO}/releases/tag/{tag_name}"
    )
    body = data.get("body") or ""
    if not isinstance(body, str):
        body = str(body)
    if not isinstance(html_url, str):
        html_url = f"https://github.com/{_GITHUB_REPO}/releases/tag/{tag_name}"
    return ReleaseInfo(
        version=version,
        version_str=version_str,
        html_url=html_url,
        body=body,
        is_tag_fallback=False,
    )


def _parse_tags_payload(data: Any) -> ReleaseInfo | None:
    """Pick the highest stable ``vX.Y.Z`` tag from a ``/tags`` JSON list."""
    if not isinstance(data, list):
        return None
    versions: list[tuple[int, int, int]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        m = _SEMVER_TAG_RE.match(name)
        if m is None:
            continue
        versions.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if not versions:
        return None
    best = max(versions)
    version_str = f"{best[0]}.{best[1]}.{best[2]}"
    return ReleaseInfo(
        version=best,
        version_str=version_str,
        html_url=f"https://github.com/{_GITHUB_REPO}/releases/tag/v{version_str}",
        body="",
        is_tag_fallback=True,
    )


def latest_release(timeout: float = 5.0) -> ReleaseInfo | None:
    """Probe GitHub for the latest published release. Never raises.

    Returns ``None`` for every failure mode (network down, garbage payload,
    no stable tags, etc.). The caller treats ``None`` as "checked, nothing
    to report" — the cache timestamp gets updated regardless.
    """
    status, data = _http_get_json_or_404(_RELEASES_URL, timeout)
    if status == "ok":
        return _parse_release_payload(data)
    if status == "404":
        tag_status, tag_data = _http_get_json_or_404(_TAGS_URL, timeout)
        if tag_status == "ok":
            return _parse_tags_payload(tag_data)
        return None
    return None


def is_newer(
    latest: tuple[int, int, int], current: tuple[int, int, int]
) -> bool:
    """Strict ``>`` on ``(major, minor, patch)`` tuples."""
    return latest > current


def should_check_now(last_check_ts: float, interval_h: float = 24.0) -> bool:
    """``True`` when at least ``interval_h`` hours have passed since the last probe.

    A fresh install / never-checked state is signalled by ``last_check_ts == 0.0``,
    which always returns ``True``.
    """
    return (time.time() - last_check_ts) >= interval_h * 3600.0


__all__ = [
    "ReleaseInfo",
    "latest_release",
    "is_newer",
    "should_check_now",
]
