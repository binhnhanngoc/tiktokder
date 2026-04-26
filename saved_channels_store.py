"""Saved-channels persistence — `data/saved_channels.json` (schema v1).

Mirrors `history_store.py` patterns: atomic write, tolerant load, never-raises.
Pure data layer — no PySide6 imports — so it stays unit-testable without Qt.

Schema v1::

    {
      "schema": 1,
      "tiktok": [SavedChannel, ...],
      "facebook": [SavedChannel, ...]
    }
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DEFAULT_MAX_PER_PLATFORM = 200
SUPPORTED_PLATFORMS = ("tiktok", "facebook")


@dataclass
class SavedChannel:
    """One saved channel/page row.

    `last_fetched_at` is ISO8601 with timezone; `last_fetched_video_ids`
    captures what the last successful Browse fetch returned (used by the
    "Download all new" filter to scope to post-cutoff videos).
    """

    url: str
    nickname: str = ""
    note: str = ""
    starred: bool = False
    last_fetched_at: str | None = None
    last_fetched_video_ids: list[str] = field(default_factory=list)


_FIELDS = {f.name for f in fields(SavedChannel)}


def _channel_from_dict(d: dict) -> SavedChannel | None:
    """Build a SavedChannel from a dict, ignoring unknown keys. Returns None if no url."""
    url = d.get("url")
    if not url or not isinstance(url, str):
        return None
    filtered = {k: v for k, v in d.items() if k in _FIELDS}
    ids = filtered.get("last_fetched_video_ids")
    if ids is not None and not isinstance(ids, list):
        filtered["last_fetched_video_ids"] = []
    return SavedChannel(**filtered)


@dataclass
class SavedChannelsStore:
    """In-memory representation of the saved-channels file."""

    tiktok: list[SavedChannel] = field(default_factory=list)
    facebook: list[SavedChannel] = field(default_factory=list)

    def get_list(self, platform: str) -> list[SavedChannel]:
        """Return the list slice for ``platform`` (mutable reference)."""
        if platform == "tiktok":
            return self.tiktok
        if platform == "facebook":
            return self.facebook
        return []

    def list_all(self, platform: str) -> list[SavedChannel]:
        """Snapshot copy of saved channels for ``platform``."""
        return list(self.get_list(platform))

    def find_by_url(self, platform: str, url: str) -> SavedChannel | None:
        for ch in self.get_list(platform):
            if ch.url == url:
                return ch
        return None


def _read_file(path: Path) -> SavedChannelsStore:
    """Tolerant loader. Malformed/missing → empty store + warning."""
    if not path.exists():
        return SavedChannelsStore()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Saved-channels file %s is malformed (%s); starting empty.", path, exc)
        return SavedChannelsStore()

    if not isinstance(data, dict):
        logger.warning("Saved-channels file %s has unrecognized shape; starting empty.", path)
        return SavedChannelsStore()

    store = SavedChannelsStore()
    for platform in SUPPORTED_PLATFORMS:
        entries = data.get(platform) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ch = _channel_from_dict(entry)
            if ch is not None:
                store.get_list(platform).append(ch)
    return store


def _atomic_write(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` via temp file + os.replace (crash-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_saved_channels(path: Path) -> SavedChannelsStore:
    """Load saved-channels store from JSON file (or return empty)."""
    return _read_file(path)


def save_saved_channels(path: Path, store: SavedChannelsStore) -> None:
    """Persist ``store`` as schema v1 atomically."""
    payload = json.dumps(
        {
            "schema": SCHEMA_VERSION,
            "tiktok": [asdict(c) for c in store.tiktok],
            "facebook": [asdict(c) for c in store.facebook],
        },
        indent=2,
        ensure_ascii=False,
    )
    _atomic_write(path, payload)


def _trim_oldest(channels: list[SavedChannel], cap: int) -> list[SavedChannel]:
    """Return a new list capped at ``cap`` by FIFO-dropping oldest by last_fetched_at.

    None sorts oldest (drops first). Stable for ties.
    """
    if cap <= 0 or len(channels) <= cap:
        return channels

    def sort_key(c: SavedChannel) -> tuple[int, str]:
        # None → (0, ""), else (1, iso) — empties sort first, oldest dates next.
        return (0, "") if c.last_fetched_at is None else (1, c.last_fetched_at)

    sorted_by_age = sorted(channels, key=sort_key)
    keep = sorted_by_age[-cap:]
    keep_urls = {c.url for c in keep}
    return [c for c in channels if c.url in keep_urls]


def add_channel(
    store: SavedChannelsStore,
    platform: str,
    channel: SavedChannel,
    cap: int = DEFAULT_MAX_PER_PLATFORM,
) -> bool:
    """Add ``channel`` to ``platform`` slice. Returns True if added (False on dup).

    Enforces ``cap`` via FIFO-trim of oldest (by last_fetched_at).
    """
    if platform not in SUPPORTED_PLATFORMS:
        return False
    target = store.get_list(platform)
    if any(c.url == channel.url for c in target):
        return False
    target.append(channel)
    trimmed = _trim_oldest(target, cap)
    if trimmed is not target:
        target[:] = trimmed
    return True


def remove_channel(store: SavedChannelsStore, platform: str, url: str) -> bool:
    """Remove channel with matching ``url``. Returns True if removed (False on missing)."""
    target = store.get_list(platform)
    for i, ch in enumerate(target):
        if ch.url == url:
            del target[i]
            return True
    return False


def update_channel(
    store: SavedChannelsStore,
    platform: str,
    url: str,
    **fields_to_update,
) -> bool:
    """Mutate fields of the matching channel. Returns True if found+updated."""
    ch = store.find_by_url(platform, url)
    if ch is None:
        return False
    for k, v in fields_to_update.items():
        if k in _FIELDS:
            setattr(ch, k, v)
    return True


def mark_fetched(
    store: SavedChannelsStore,
    platform: str,
    url: str,
    video_ids: Iterable[str],
    fetched_at: str,
) -> bool:
    """Record post-fetch state on the matching channel."""
    return update_channel(
        store,
        platform,
        url,
        last_fetched_at=fetched_at,
        last_fetched_video_ids=list(video_ids),
    )


def _iso_to_yyyymmdd(iso: str) -> str | None:
    """Convert ISO8601 (``2026-04-26T12:34:56+07:00``) → ``"20260426"``.

    Returns None when input is unparseable. Avoids dateutil — pure slicing.
    """
    if not iso or len(iso) < 10:
        return None
    try:
        return iso[0:4] + iso[5:7] + iso[8:10]
    except (TypeError, IndexError):
        return None


def select_new_videos(
    channel: SavedChannel,
    fetched_videos: list,
    history_ids: set[str],
):
    """Filter ``fetched_videos`` to "new" ones for "Download all new".

    A video is **new** when:
      * its ``video_id`` is not in ``history_ids``, AND
      * it has no ``upload_date`` (id-only fallback), OR its ``upload_date``
        (``YYYYMMDD``) is strictly greater than ``channel.last_fetched_at``
        normalised to the same form.

    When ``channel.last_fetched_at`` is None, falls back to id-only filter.
    Lexicographic comparison works because both sides are zero-padded.
    """
    cutoff = (
        _iso_to_yyyymmdd(channel.last_fetched_at)
        if channel.last_fetched_at
        else None
    )
    out = []
    for v in fetched_videos:
        vid = getattr(v, "video_id", None)
        if not vid or vid in history_ids:
            continue
        if cutoff is None:
            out.append(v)
            continue
        upload_date = getattr(v, "upload_date", None)
        if not upload_date:
            # Date missing → keep (id-only fallback for that video).
            out.append(v)
            continue
        if str(upload_date) > cutoff:
            out.append(v)
    return out


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_MAX_PER_PLATFORM",
    "SUPPORTED_PLATFORMS",
    "SavedChannel",
    "SavedChannelsStore",
    "load_saved_channels",
    "save_saved_channels",
    "add_channel",
    "remove_channel",
    "update_channel",
    "mark_fetched",
    "select_new_videos",
]
