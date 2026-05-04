"""JSON-based settings persistence for TikTokDer."""

import json
import os
import shutil
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

from history_store import (
    DEFAULT_MAX_ENTRIES,
    HistoryRecord,
    add_history_record as _add_history_record,
    load_history_ids,
    load_history_records as _load_history_records,
    save_history_ids,
    save_history_records as _save_history_records,
)


def _is_portable() -> bool:
    """True when running as a PyInstaller-frozen bundle (portable mode)."""
    return getattr(sys, "frozen", False)


def _portable_root() -> Path:
    """Folder containing the frozen exe. Used as the portable data root."""
    return Path(sys.executable).resolve().parent


def _source_root() -> Path:
    """Folder containing config.py — i.e., the project root in source runs."""
    return Path(__file__).resolve().parent


def _default_config_dir() -> Path:
    """`<app_root>/data` — exe dir when frozen, project root in source runs."""
    root = _portable_root() if _is_portable() else _source_root()
    return root / "data"


def _default_output_dir() -> str:
    """`<exe_dir>/downloads` in portable builds, `./downloads` in source runs."""
    if _is_portable():
        return str(_portable_root() / "downloads")
    return "./downloads"


CONFIG_DIR = _default_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "history.json"
STATE_PATH = CONFIG_DIR / "state.json"
SAVED_CHANNELS_PATH = CONFIG_DIR / "saved_channels.json"


def _migrate_legacy_data_dir() -> None:
    """Move config.json/history.json from `~/.tiktokder/` to the new app-folder
    location. Idempotent: only moves files that don't already exist at the new
    path, then removes the legacy folder if empty.
    """
    legacy = Path.home() / ".tiktokder"
    if not legacy.exists() or legacy == CONFIG_DIR:
        return
    moved = False
    for name in ("config.json", "history.json"):
        src = legacy / name
        dst = CONFIG_DIR / name
        if src.exists() and not dst.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved = True
    if moved:
        try:
            legacy.rmdir()  # only succeeds if empty — leave non-empty dirs alone
        except OSError:
            pass


_migrate_legacy_data_dir()


@dataclass
class AppConfig:
    """Application configuration."""

    output_dir: str = field(default_factory=_default_output_dir)
    workers: int = 3
    delay: float = 0.5
    cookie_browser: str | None = None
    # Path to a Netscape-format cookies.txt — consumed by the Facebook scraper
    # (Playwright injection) and the FB yt-dlp path. None = no cookies.
    facebook_cookies_file: str | None = None
    # TikTok counterpart: path to Netscape cookies.txt fed to yt-dlp via
    # `cookiefile`. Takes precedence over `cookie_browser` when both are set.
    tiktok_cookies_file: str | None = None
    window_width: int = 900
    window_height: int = 600
    window_x: int | None = None
    window_y: int | None = None
    quality_default: str = "best"        # one of best|1080p|720p|480p|audio
    write_subtitles: bool = False
    write_thumbnail: bool = False
    history_max_entries: int = DEFAULT_MAX_ENTRIES
    theme_mode: str = "system"           # one of system|light|dark
    facebook_max_scrolls_default: int = 10
    # Channel-browse Downloaded filter — persisted per platform.
    # One of: "all" | "new" | "downloaded".
    tiktok_browse_downloaded_filter: str = "all"
    facebook_browse_downloaded_filter: str = "all"
    # ── update checker (Phase 02) ──
    last_update_check_at: float = 0.0       # epoch seconds, 0 = never
    skipped_update_version: str = ""        # "1.10.1" if user clicked Skip
    update_check_enabled: bool = True       # opt-out flag (default ON)


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
    """Load config from JSON file, returning defaults if missing.

    Migrates legacy `cookies_file` key to `facebook_cookies_file` on read so
    pre-rename configs keep working. The new key wins when both are present.
    """
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if "cookies_file" in data and "facebook_cookies_file" not in data:
            data["facebook_cookies_file"] = data["cookies_file"]
        # Filter to only known fields (drops legacy `cookies_file` after migration).
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
    """Load downloaded video IDs from history file (v1 or v2)."""
    return load_history_ids(HISTORY_PATH)


def save_history(ids: set[str]) -> None:
    """Save downloaded video IDs to history file (writes v2 with bare records)."""
    save_history_ids(HISTORY_PATH, ids)


def load_history_records() -> list[HistoryRecord]:
    """Return full HistoryRecord list (empty if file absent or v1 minimal)."""
    return _load_history_records(HISTORY_PATH)


def save_history_records(records: list[HistoryRecord]) -> None:
    """Persist HistoryRecord list as schema v2 atomically."""
    _save_history_records(HISTORY_PATH, records)


def add_history_record(record: HistoryRecord, max_entries: int | None = None) -> None:
    """Append a record; FIFO-trim to ``max_entries`` (defaults to AppConfig limit)."""
    cap = max_entries if max_entries is not None else DEFAULT_MAX_ENTRIES
    _add_history_record(HISTORY_PATH, record, max_entries=cap)


__all__ = [
    "AppConfig",
    "HistoryRecord",
    "PlatformDefaults",
    "TIKTOK_DEFAULTS",
    "FACEBOOK_DEFAULTS",
    "MAX_RETRY_ATTEMPTS_TIKTOK",
    "MAX_RETRY_ATTEMPTS_FACEBOOK",
    "FB_LOGIN_WALL_MARKERS",
    "CONFIG_DIR",
    "CONFIG_PATH",
    "HISTORY_PATH",
    "STATE_PATH",
    "SAVED_CHANNELS_PATH",
    "get_platform_defaults",
    "get_max_retry_attempts",
    "load_config",
    "save_config",
    "load_history",
    "save_history",
    "load_history_records",
    "save_history_records",
    "add_history_record",
]
