"""JSON-based settings persistence for TikTokDer."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path


CONFIG_DIR = Path.home() / ".tiktokder"
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "history.json"


@dataclass
class AppConfig:
    """Application configuration."""

    output_dir: str = "./downloads"
    workers: int = 3
    delay: float = 0.5
    cookie_browser: str | None = None
    window_width: int = 900
    window_height: int = 600
    window_x: int | None = None
    window_y: int | None = None


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
