"""History persistence — schema v2 records with v1 migration.

Schema v1: top-level JSON list of video-id strings (legacy).
Schema v2: ``{"schema": 2, "entries": [HistoryRecord, ...]}``.

Read paths transparently accept both. Writes always emit v2.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
DEFAULT_MAX_ENTRIES = 10000


@dataclass
class HistoryRecord:
    """One downloaded-video metadata row (schema v2)."""

    video_id: str
    platform: str | None = None        # "tiktok" | "facebook" | None
    uploader: str | None = None
    title: str | None = None
    url: str | None = None
    quality: str | None = None         # e.g. "1080p", "audio"
    file_path: str | None = None       # absolute path; relative also accepted
    size_bytes: int | None = None
    downloaded_at: str | None = None   # ISO8601 with tz


_RECORD_FIELDS = {f.name for f in fields(HistoryRecord)}


def _record_from_dict(d: dict) -> HistoryRecord | None:
    """Build a HistoryRecord from a dict, ignoring unknown keys. Returns None if no video_id."""
    vid = d.get("video_id")
    if not vid or not isinstance(vid, str):
        return None
    filtered = {k: v for k, v in d.items() if k in _RECORD_FIELDS}
    return HistoryRecord(**filtered)


def _read_history_file(path: Path) -> tuple[int, list[HistoryRecord]]:
    """Return ``(schema_version, records)``. Schema 0 = empty / malformed.

    Accepts both legacy v1 (list of id strings) and v2 (dict with entries).
    Never raises; logs a warning on malformed JSON and returns ``(0, [])``.
    """
    if not path.exists():
        return 0, []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("History file %s is malformed (%s); starting empty.", path, exc)
        return 0, []

    if isinstance(data, list):
        # v1 — list of bare id strings.
        records = [HistoryRecord(video_id=str(x)) for x in data if isinstance(x, str) and x]
        return 1, records

    if isinstance(data, dict) and data.get("schema") == SCHEMA_VERSION:
        entries = data.get("entries") or []
        records = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rec = _record_from_dict(entry)
            if rec is not None:
                records.append(rec)
        return SCHEMA_VERSION, records

    logger.warning("History file %s has unrecognized shape; starting empty.", path)
    return 0, []


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


def load_history_ids(path: Path) -> set[str]:
    """Return the set of video IDs from history (v1 or v2)."""
    _, records = _read_history_file(path)
    return {r.video_id for r in records}


def load_history_records(path: Path) -> list[HistoryRecord]:
    """Return the full record list (empty for v1 minimal entries when file absent)."""
    _, records = _read_history_file(path)
    return records


def save_history_records(path: Path, records: list[HistoryRecord]) -> None:
    """Persist ``records`` as schema v2 atomically."""
    payload = json.dumps(
        {"schema": SCHEMA_VERSION, "entries": [asdict(r) for r in records]},
        indent=2,
        ensure_ascii=False,
    )
    _atomic_write(path, payload)


def add_history_record(
    path: Path,
    record: HistoryRecord,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    """Append ``record``; FIFO-trim metadata to ``max_entries``; persist atomically."""
    _, records = _read_history_file(path)
    records.append(record)
    if max_entries > 0 and len(records) > max_entries:
        # FIFO drop — oldest entries off the front. Files on disk untouched.
        records = records[-max_entries:]
    save_history_records(path, records)


def save_history_ids(path: Path, ids: set[str]) -> None:
    """Back-compat shim — wrap each id in a bare HistoryRecord and persist as v2."""
    records = [HistoryRecord(video_id=i) for i in sorted(ids)]
    save_history_records(path, records)
