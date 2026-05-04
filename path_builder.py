"""Pure helpers for computing platform-aware download paths.

Layout: ``<base_dir>/<platform>/<slug_uploader>/<title> [<id6>].<ext>``.

`build_output_template` returns a fully-resolved yt-dlp ``outtmpl`` string —
platform + uploader segments are baked in by Python so empty metadata can
never produce a stray ``downloads/tiktok//...`` path. Only the per-video
fields (``%(title).80s``, ``%(id).6s``, ``%(ext)s``) are left to yt-dlp.

The 6-char bracketed ID suffix uniquifies same-title downloads (silent
overwrites would be data loss) while keeping the title visually dominant.
Legacy ``<id>_<title>.<ext>`` files on disk stay readable to the dedup
scanner — see ``downloader.LEGACY_ID_RE`` and ``downloader.get_downloaded_ids``.
"""

from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import parse_qs, urlparse

from url_parser import detect_platform

UNKNOWN_UPLOADER = "unknown_uploader"
_MAX_SLUG_LEN = 80
_RESERVED_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]+')
_PATH_SEP = re.compile(r"[\\/]+")
_WHITESPACE = re.compile(r"\s+")
_UNDERSCORE_RUN = re.compile(r"_+")
_NUMERIC_ONLY = re.compile(r"^\d+$")
# Title-leading shape: title cap at 80 chars (yt-dlp truncates to keep paths
# under Windows MAX_PATH); 6-char bracketed ID uniquifies same-title videos.
FILENAME_TEMPLATE = "%(title).80s [%(id).6s].%(ext)s"


def _looks_like_id(value: str | None) -> bool:
    """True if ``value`` is purely numeric — i.e. a Facebook/TikTok ID, not a name."""
    if not value:
        return True
    return bool(_NUMERIC_ONLY.match(str(value).strip()))


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
    non-empty segment → page slug. Purely-numeric segments are skipped
    so ``/reel/<digits>`` and ``/videos/<digits>`` don't get mistaken
    for a page name. Facebook ``profile.php?id=<digits>`` URLs return
    ``profile_<digits>`` so each numeric profile gets its own folder
    instead of all collapsing into ``profile.php/``. Returns
    ``unknown_uploader`` on unrecognized shapes.
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

    # Facebook profile.php?id=<digits> — only stable identifier is the id;
    # prefix with ``profile_`` so the slug reads as a name and dodges the
    # numeric-id rejection on any round-trip through `_uploader_from_info`.
    if any(p.lower() == "profile.php" for p in path_parts):
        ids = parse_qs(parsed.query).get("id", [])
        if ids and _NUMERIC_ONLY.match(ids[0].strip()):
            return f"profile_{ids[0].strip()}"

    # Facebook: skip generic prefixes and numeric IDs (video/reel ids).
    skip = {"videos", "video", "watch", "reel", "reels", "v", "story.php", "groups", "profile.php"}
    for part in path_parts:
        if part.lower() in skip:
            continue
        if _looks_like_id(part):
            continue
        return slugify_uploader(part)

    return UNKNOWN_UPLOADER


def _uploader_from_info(info: dict | None) -> str | None:
    """Extract the most useful uploader-like field from a yt-dlp info dict.

    Purely-numeric values are skipped — yt-dlp's Facebook extractor often
    fills only ``uploader_id`` with a numeric page id, which would otherwise
    produce folders like ``downloads/facebook/1438416620945910/`` instead of
    the human-readable page name. ``uploader_url``/``channel_url`` are
    parsed as a last resort to recover the page slug from the profile URL.
    """
    if not isinstance(info, dict):
        return None
    for key in ("uploader", "channel", "uploader_id", "creator"):
        val = info.get(key)
        if val and not _looks_like_id(val):
            return str(val)
    for key in ("uploader_url", "channel_url"):
        val = info.get(key)
        if val:
            slug = platform_slug_from_url(str(val))
            if slug != UNKNOWN_UPLOADER:
                return slug
    return None


def build_output_template(
    url: str,
    info: dict | None,
    base_dir: str,
    *,
    page_hint: str | None = None,
) -> str:
    """Compose a yt-dlp ``outtmpl`` string with platform/uploader baked in.

    Resolution priority for the uploader segment:
    1. ``page_hint`` — caller-provided page URL or slug (e.g. the source FB
       page from which a ``/reel/<id>`` was scraped). Authoritative because
       it reflects user intent; FB reel metadata is unreliable.
    2. yt-dlp ``info`` (uploader/channel/uploader_id/creator) — purely-numeric
       values are skipped.
    3. ``info`` URL fields (uploader_url/channel_url) parsed for a slug.
    4. URL path slug (TikTok handle / Facebook page segment).
    5. ``unknown_uploader``.

    The trailing filename portion is always ``FILENAME_TEMPLATE`` so yt-dlp
    fills in per-video fields.
    """
    platform = detect_platform(url) or "unknown"
    uploader = (
        _uploader_from_hint(page_hint)
        or _uploader_from_info(info)
        or platform_slug_from_url(url)
    )
    slug = slugify_uploader(uploader)
    folder = os.path.join(base_dir, platform, slug)
    return os.path.join(folder, FILENAME_TEMPLATE)


def _uploader_from_hint(hint: str | None) -> str | None:
    """Normalize a page hint to a usable slug, or None if unusable.

    Accepts either a full URL (``https://www.facebook.com/PageName``) or a
    bare slug. URLs are routed through ``platform_slug_from_url``; bare
    strings pass through after numeric-id rejection.
    """
    if not hint:
        return None
    h = hint.strip()
    if not h:
        return None
    if "://" in h or h.startswith("//") or h.startswith("www."):
        slug = platform_slug_from_url(h if "://" in h else f"https://{h}")
        return None if slug == UNKNOWN_UPLOADER else slug
    if _looks_like_id(h):
        return None
    return h
