"""UI state persistence — Download queue + Channel/Page browse snapshots.

Kept separate from ``config.py`` because state mutates on every close, may be
large (hundreds of VideoInfo rows), and a corrupt state file shouldn't take
the user's settings down with it. Loads are tolerant: malformed JSON, missing
keys, or unknown fields all fall back to empty defaults rather than raising.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class QueueItemState:
    """One persisted Download-tab row."""

    url: str
    status: str = "Queued"
    title: str | None = None


@dataclass
class VideoInfoState:
    """One persisted Channel/Page-tab video row.

    Mirrors ``channel_fetcher.VideoInfo`` minus runtime-only fields. Kept as
    its own dataclass (rather than reusing VideoInfo) so the persistence
    schema is decoupled from internal model evolution.
    """

    url: str
    title: str = ""
    duration: int | None = None
    view_count: int | None = None
    upload_date: str | None = None
    video_id: str = ""
    quality: str | None = None


@dataclass
class BrowserPanelState:
    """Persisted state of one platform sub-panel (TikTok or Facebook)."""

    url: str = ""
    videos: list[VideoInfoState] = field(default_factory=list)
    # Facebook only — None for TikTok (panel ignores it).
    max_scrolls: int | None = None


@dataclass
class AppState:
    """Top-level snapshot of UI volatile state."""

    active_tab_index: int = 0
    channel_active_sub_tab: int = 0
    download_queue: list[QueueItemState] = field(default_factory=list)
    tiktok_browser: BrowserPanelState = field(default_factory=BrowserPanelState)
    facebook_browser: BrowserPanelState = field(default_factory=BrowserPanelState)
    library_active_uploader_tiktok: str | None = None
    library_active_uploader_facebook: str | None = None


_QUEUE_FIELDS = {f.name for f in fields(QueueItemState)}
_VIDEO_FIELDS = {f.name for f in fields(VideoInfoState)}


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_str(value) -> str | None:
    """Tolerant string coercion — None passes through; empty string → None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return None


def _load_queue_item(d: dict) -> QueueItemState | None:
    if not isinstance(d, dict):
        return None
    url = d.get("url")
    if not isinstance(url, str) or not url:
        return None
    filtered = {k: v for k, v in d.items() if k in _QUEUE_FIELDS}
    try:
        return QueueItemState(**filtered)
    except TypeError:
        return None


def _load_video(d: dict) -> VideoInfoState | None:
    if not isinstance(d, dict):
        return None
    url = d.get("url")
    if not isinstance(url, str) or not url:
        return None
    filtered = {k: v for k, v in d.items() if k in _VIDEO_FIELDS}
    try:
        return VideoInfoState(**filtered)
    except TypeError:
        return None


def _load_panel(d) -> BrowserPanelState:
    if not isinstance(d, dict):
        return BrowserPanelState()
    videos_raw = d.get("videos") or []
    videos: list[VideoInfoState] = []
    if isinstance(videos_raw, list):
        for entry in videos_raw:
            v = _load_video(entry)
            if v is not None:
                videos.append(v)
    max_scrolls = d.get("max_scrolls")
    if max_scrolls is not None:
        try:
            max_scrolls = int(max_scrolls)
        except (TypeError, ValueError):
            max_scrolls = None
    return BrowserPanelState(
        url=str(d.get("url", "") or ""),
        videos=videos,
        max_scrolls=max_scrolls,
    )


def load_state(path: Path) -> AppState:
    """Read state file at ``path``; return defaults on missing/malformed."""
    if not path.exists():
        return AppState()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("State file %s is malformed (%s); starting empty.", path, exc)
        return AppState()
    if not isinstance(data, dict):
        return AppState()

    queue_raw = data.get("download_queue") or []
    queue: list[QueueItemState] = []
    if isinstance(queue_raw, list):
        for entry in queue_raw:
            item = _load_queue_item(entry)
            if item is not None:
                queue.append(item)

    return AppState(
        active_tab_index=_coerce_int(data.get("active_tab_index"), 0),
        channel_active_sub_tab=_coerce_int(data.get("channel_active_sub_tab"), 0),
        download_queue=queue,
        tiktok_browser=_load_panel(data.get("tiktok_browser")),
        facebook_browser=_load_panel(data.get("facebook_browser")),
        library_active_uploader_tiktok=_coerce_optional_str(
            data.get("library_active_uploader_tiktok")
        ),
        library_active_uploader_facebook=_coerce_optional_str(
            data.get("library_active_uploader_facebook")
        ),
    )


def save_state(path: Path, state: AppState) -> None:
    """Write ``state`` to ``path`` as pretty JSON. Creates parent dir if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(state), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def clear_state_section(path: Path, *, clear_queue: bool = False) -> None:
    """Mutate the on-disk state file in place — used by Clear All to wipe queue
    immediately rather than waiting for app close. No-op if file absent."""
    if not path.exists():
        return
    state = load_state(path)
    if clear_queue:
        state.download_queue = []
    save_state(path, state)


__all__ = [
    "AppState",
    "BrowserPanelState",
    "QueueItemState",
    "VideoInfoState",
    "clear_state_section",
    "load_state",
    "save_state",
]
