"""URL parsing and validation utilities for TikTok and Facebook."""

import re
from pathlib import Path


# --- TikTok patterns ---

# Matches TikTok video URLs (regular and short links)
TIKTOK_URL_PATTERN = re.compile(
    r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/(?:@[\w.]+/video/\d+|[\w]+)/?$"
)

VIDEO_ID_PATTERN = re.compile(r"/video/(\d+)")

# Matches TikTok channel/profile URLs: tiktok.com/@username (no /video/ suffix)
CHANNEL_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?tiktok\.com/@[\w.]+/?$"
)

# --- Facebook patterns ---

# Matches Facebook video/content URLs (watch, videos, reel, posts, story, short links)
# Also matches profile.php?id= with query parameters
FACEBOOK_URL_PATTERN = re.compile(
    r"https?://(?:"
    r"(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.com)"
    r"(?:/(?:profile\.php|[\w.]+))?(?:[?&][\w=&%.+-]*)?"
    r"(?:/(?:videos?|watch|reel|posts|story)/?\S*)?"
    r"|fb\.watch/[\w./?=&-]+"
    r")/?$",
    re.IGNORECASE,
)

# Matches Facebook page/profile URLs (no video/watch/reel path suffix)
# Includes profile.php?id= format and vanity URLs
FACEBOOK_PAGE_PATTERN = re.compile(
    r"https?://(?:www\.|m\.|web\.)?facebook\.com/"
    r"(?:profile\.php\?id=\d+(?:&[\w=&%.+-]*)?|[\w.]+/?)"
    r"$",
    re.IGNORECASE,
)


def validate_tiktok_url(url: str) -> bool:
    """Check if URL is a valid TikTok video or profile URL."""
    return bool(TIKTOK_URL_PATTERN.match(url.strip()))


def validate_facebook_url(url: str) -> bool:
    """Check if URL is a valid Facebook video or page URL."""
    return bool(FACEBOOK_URL_PATTERN.match(url.strip()))


def validate_url(url: str) -> bool:
    """Check if URL is a valid TikTok or Facebook URL (video OR channel/page).

    Channel/profile URLs (e.g. ``https://www.tiktok.com/@user``) must pass so
    paste/drop/import flows can route them — downstream code uses
    ``detect_platform`` and ``is_page_or_channel_url`` to dispatch.
    """
    return (
        validate_tiktok_url(url)
        or validate_facebook_url(url)
        or is_page_or_channel_url(url)
    )


def is_channel_url(url: str) -> bool:
    """Check if URL is a TikTok channel/profile URL (not a video URL)."""
    return bool(CHANNEL_URL_PATTERN.match(url.strip()))


def is_facebook_page_url(url: str) -> bool:
    """Check if URL is a Facebook page/profile URL (no video path)."""
    return bool(FACEBOOK_PAGE_PATTERN.match(url.strip()))


def is_page_or_channel_url(url: str) -> bool:
    """Check if URL is a TikTok channel or Facebook page URL."""
    return is_channel_url(url) or is_facebook_page_url(url)


def detect_platform(url: str) -> str | None:
    """Detect platform from URL. Returns 'tiktok', 'facebook', or None."""
    url = url.strip()
    if TIKTOK_URL_PATTERN.match(url) or CHANNEL_URL_PATTERN.match(url):
        return "tiktok"
    if FACEBOOK_URL_PATTERN.match(url) or FACEBOOK_PAGE_PATTERN.match(url):
        return "facebook"
    return None


def extract_video_id(url: str) -> str | None:
    """Extract video ID from a TikTok video URL."""
    match = VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else None


def read_batch_file(filepath: str) -> list[str]:
    """Read URLs from a text file, skipping empty/comment lines and duplicates."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Batch file not found: {filepath}")

    seen = set()
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            seen.add(line)
            urls.append(line)
    return urls


def build_user_url(username: str) -> str:
    """Construct TikTok profile URL from @username."""
    username = username.lstrip("@")
    # Only allow alphanumeric, dots, underscores in usernames
    if not re.match(r"^[\w.]+$", username):
        raise ValueError(f"Invalid username: @{username}")
    return f"https://www.tiktok.com/@{username}"
