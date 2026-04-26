"""Pure helpers for computing platform-aware download paths.

Layout: ``<base_dir>/<platform>/<slug_uploader>/<id>_<title>.<ext>``.

`build_output_template` returns a fully-resolved yt-dlp ``outtmpl`` string —
platform + uploader segments are baked in by Python so empty metadata can
never produce a stray ``downloads/tiktok//...`` path. Only the per-video
fields (``%(id)s``, ``%(title).50s``, ``%(ext)s``) are left to yt-dlp.
"""

from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import urlparse

from url_parser import detect_platform

UNKNOWN_UPLOADER = "unknown_uploader"
_MAX_SLUG_LEN = 80
_RESERVED_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]+')
_PATH_SEP = re.compile(r"[\\/]+")
_WHITESPACE = re.compile(r"\s+")
_UNDERSCORE_RUN = re.compile(r"_+")
_FILENAME_TEMPLATE = "%(id)s_%(title).50s.%(ext)s"


def slugify_uploader(name: str | None) -> str:
    """Filesystem-safe slug for an uploader/channel name.

    Preserves readable Unicode (NFKC normalize), strips path separators,
    replaces reserved chars with ``_``, collapses runs, truncates to 80 chars.
    Empty / whitespace-only input → ``unknown_uploader``.
    """
    if not name:
        return UNKNOWN_UPLOADER
    s = unicodedata.normalize("NFKC", str(name))
    s = _PATH_SEP.sub("_", s)
    s = _RESERVED_CHARS.sub("_", s)
    s = _WHITESPACE.sub("_", s)
    s = _UNDERSCORE_RUN.sub("_", s)
    s = s.strip("._ ")
    s = s[:_MAX_SLUG_LEN].rstrip("._ ")
    return s or UNKNOWN_UPLOADER


def platform_slug_from_url(url: str) -> str:
    """Best-effort uploader slug extracted from URL when metadata is absent.

    TikTok ``@handle`` form → ``@handle``. Facebook page path's first
    non-empty segment → page slug. Returns ``unknown_uploader`` on
    unrecognized shapes.
    """
    if not url:
        return UNKNOWN_UPLOADER
    try:
        parsed = urlparse(url)
    except ValueError:
        return UNKNOWN_UPLOADER
    path_parts = [p for p in parsed.path.split("/") if p]
    if not path_parts:
        return UNKNOWN_UPLOADER

    # TikTok handles: /@username/...
    for part in path_parts:
        if part.startswith("@"):
            return slugify_uploader(part)

    # Facebook: skip generic prefixes like "videos", "watch", "reel".
    skip = {"videos", "video", "watch", "reel", "reels", "v", "story.php", "groups"}
    for part in path_parts:
        if part.lower() in skip:
            continue
        return slugify_uploader(part)

    return slugify_uploader(path_parts[0])


def _uploader_from_info(info: dict | None) -> str | None:
    """Extract the most useful uploader-like field from a yt-dlp info dict."""
    if not isinstance(info, dict):
        return None
    for key in ("uploader", "channel", "uploader_id", "creator"):
        val = info.get(key)
        if val:
            return str(val)
    return None


def build_output_template(
    url: str,
    info: dict | None,
    base_dir: str,
) -> str:
    """Compose a yt-dlp ``outtmpl`` string with platform/uploader baked in.

    Falls back to the URL-derived slug when the info dict carries no usable
    uploader. The trailing filename portion is always
    ``%(id)s_%(title).50s.%(ext)s`` so yt-dlp fills in per-video fields.
    """
    platform = detect_platform(url) or "unknown"
    uploader = _uploader_from_info(info) or platform_slug_from_url(url)
    slug = slugify_uploader(uploader)
    folder = os.path.join(base_dir, platform, slug)
    return os.path.join(folder, _FILENAME_TEMPLATE)
