"""JSON-based settings persistence for TikTokDer."""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


def _is_portable() -> bool:
    """True when running as a PyInstaller-frozen bundle (portable mode)."""
    return getattr(sys, "frozen", False)


def _portable_root() -> Path:
    """Folder containing the frozen exe. Used as the portable data root."""
    return Path(sys.executable).resolve().parent


def _default_config_dir() -> Path:
    """`<exe_dir>/data` in portable builds, `~/.tiktokder` in source runs."""
    if _is_portable():
        return _portable_root() / "data"
    return Path.home() / ".tiktokder"


def _default_output_dir() -> str:
    """`<exe_dir>/downloads` in portable builds, `./downloads` in source runs."""
    if _is_portable():
        return str(_portable_root() / "downloads")
    return "./downloads"


CONFIG_DIR = _default_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "history.json"


@dataclass
class AppConfig:
    """Application configuration."""

    output_dir: str = field(default_factory=_default_output_dir)
    workers: int = 3
    delay: float = 0.5
    cookie_browser: str | None = None
    window_width: int = 900
    window_height: int = 600
    window_x: int | None = None
    window_y: int | None = None


@dataclass(frozen=True)
class PlatformDefaults:
    """Per-platform pacing/retry presets used as fallback when user has not overridden."""

    delay_mean: float
    delay_std: float
    delay_floor: float
    workers: int
    retries: int


# TikTok tolerates faster pacing and more concurrency than Facebook.
TIKTOK_DEFAULTS = PlatformDefaults(
    delay_mean=1.5, delay_std=0.5, delay_floor=0.2, workers=3, retries=10
)

# Facebook is far stricter — slower mean, wider jitter, serial downloads, fewer retries.
FACEBOOK_DEFAULTS = PlatformDefaults(
    delay_mean=3.0, delay_std=1.5, delay_floor=0.5, workers=1, retries=2
)


# Tenacity outer retry budget (separate from yt-dlp's inner retries).
MAX_RETRY_ATTEMPTS_TIKTOK = 3
MAX_RETRY_ATTEMPTS_FACEBOOK = 2


# Login-wall HTML markers used to fast-fail FB requests before consuming retry budget.
# Substring matches; extend this tuple if FB changes its login interstitial markup.
FB_LOGIN_WALL_MARKERS: tuple[str, ...] = (
    'id="login_form"',
    'id="loginbutton"',
    'You must log in to continue',
    'class="uiInterstitialContent"',
    'login.php',
)


def get_platform_defaults(url: str) -> PlatformDefaults:
    """Return per-platform defaults; falls back to TikTok defaults for unknown URLs."""
    # Lazy import to avoid circular dependency (url_parser is independent).
    from url_parser import detect_platform

    platform = detect_platform(url)
    if platform == "facebook":
        return FACEBOOK_DEFAULTS
    return TIKTOK_DEFAULTS


def get_max_retry_attempts(url: str) -> int:
    """Return tenacity outer-layer max attempts based on platform."""
    from url_parser import detect_platform

    if detect_platform(url) == "facebook":
        return MAX_RETRY_ATTEMPTS_FACEBOOK
    return MAX_RETRY_ATTEMPTS_TIKTOK


def load_config() -> AppConfig:
    """Load config from JSON file, returning defaults if missing."""
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        # Filter to only known fields
        known = {f.name for f in AppConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return AppConfig(**filtered)
    except (json.JSONDecodeError, TypeError):
        return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save config to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )


def load_history() -> set[str]:
    """Load downloaded video IDs from history file."""
    if not HISTORY_PATH.exists():
        return set()
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except (json.JSONDecodeError, TypeError):
        return set()


def save_history(ids: set[str]) -> None:
    """Save downloaded video IDs to history file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(sorted(ids), indent=2),
        encoding="utf-8",
    )
