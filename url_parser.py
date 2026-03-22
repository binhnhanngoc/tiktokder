"""TikTok URL parsing and validation utilities."""

import re
from pathlib import Path


# Matches TikTok video URLs (regular and short links)
TIKTOK_URL_PATTERN = re.compile(
    r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/(?:@[\w.]+/video/\d+|[\w]+)/?$"
)

VIDEO_ID_PATTERN = re.compile(r"/video/(\d+)")


def validate_tiktok_url(url: str) -> bool:
    """Check if URL is a valid TikTok video or profile URL."""
    return bool(TIKTOK_URL_PATTERN.match(url.strip()))


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
