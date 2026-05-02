"""Health check — visible signals for platform fragility (pure data layer).

Reads existing on-disk state (`saved_channels.json`, `history.json`,
`cookies.txt` mtime, `yt_dlp.version`) plus a tiny cache file
(`data/health_cache.json`) for the 24h yt-dlp PyPI lookup, fetch-outcome
markers, and dismissed-issue IDs. Zero PySide6 imports — fully unit-testable
plus CLI-runnable via ``python -m health_check``.

Public API:
    HealthIssue, HealthReport, Severity, FixActionKind
    compute_health(channels, records, config, *, check_yt_dlp=False, now=None)
    record_fetch_outcome(path, channel_url, exception_class_name)
    dismiss_issue(path, issue_id)
    load_health_cache(path) / save_health_cache(path, cache)

Dismissal model: dismissed IDs hide ``info`` and ``warn`` issues; ``error``
issues always surface. A signal that escalates from ``warn`` to ``error``
re-appears even if previously dismissed.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

logger = logging.getLogger(__name__)

Severity = Literal["info", "warn", "error"]
FixActionKind = Literal["open_path", "open_url", "refresh_channel", "none"]
SCHEMA_VERSION = 1
SEVERITY_RANK: dict[str, int] = {"info": 1, "warn": 2, "error": 3}

# Serializes the load-modify-save sequences used by ``record_fetch_outcome``,
# ``dismiss_issue``, and the orchestrator's yt-dlp cache update so concurrent
# callers (engine fetch threads + the GUI worker) don't drop each other's writes.
_CACHE_LOCK = threading.Lock()


@dataclass
class HealthIssue:
    """One actionable health signal."""

    id: str
    severity: Severity
    title: str
    detail: str = ""
    fix_action_kind: FixActionKind = "none"
    fix_action_arg: str = ""


@dataclass
class HealthReport:
    """Aggregate of all current issues, post-dismissal filtering."""

    issues: list[HealthIssue] = field(default_factory=list)
    computed_at: str = ""

    def max_severity(self) -> Severity | None:
        """Highest severity present, or ``None`` when no issues."""
        if not self.issues:
            return None
        return max(self.issues, key=lambda i: SEVERITY_RANK[i.severity]).severity


def _now() -> datetime:
    """Wall clock in UTC. Override via ``now=`` kwarg in tests."""
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ── cache I/O ─────────────────────────────────────────────────────────────


def load_health_cache(path: Path) -> dict[str, Any]:
    """Tolerant load. Missing/malformed → empty dict; never raises."""
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Health cache %s malformed (%s); starting empty.", path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_health_cache(path: Path, cache: dict[str, Any]) -> None:
    """Atomic write of cache dict (mirrors ``history_store`` pattern)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        payload = dict(cache)
        payload["schema"] = SCHEMA_VERSION
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def record_fetch_outcome(
    path: Path, channel_url: str, exception_class_name: str | None
) -> None:
    """Mark/clear the last-fetch outcome for a channel.

    ``exception_class_name=None`` clears the marker (success path). Called
    from the engine + channel_fetcher without importing this module's GUI
    layer — string-name decoupling avoids a hard dep on ``retry_policy``.
    """
    with _CACHE_LOCK:
        cache = load_health_cache(path)
        outcomes = cache.setdefault("fetch_outcomes", {})
        if exception_class_name is None:
            outcomes.pop(channel_url, None)
        else:
            outcomes[channel_url] = exception_class_name
        save_health_cache(path, cache)


def dismiss_issue(path: Path, issue_id: str) -> None:
    """Persist a dismissed issue ID. Re-emerges only on severity escalation."""
    with _CACHE_LOCK:
        cache = load_health_cache(path)
        dismissed = cache.setdefault("dismissed", [])
        if issue_id not in dismissed:
            dismissed.append(issue_id)
        save_health_cache(path, cache)


def default_cache_path() -> Path:
    """Resolve `data/health_cache.json` lazily (avoid import cycle on app start)."""
    from config import CONFIG_DIR

    return CONFIG_DIR / "health_cache.json"


# Back-compat alias (was private during initial wiring).
_default_cache_path = default_cache_path


# ── orchestrator ──────────────────────────────────────────────────────────


def compute_health(
    channels: Any,
    records: Iterable[Any],
    config: Any,
    *,
    cache_path: Path | None = None,
    check_yt_dlp: bool = False,
    now: datetime | None = None,
    frozen: bool | None = None,
) -> HealthReport:
    """Run all 6 signals, apply dismissals, return a fresh ``HealthReport``.

    ``check_yt_dlp=True`` opts into the 5s PyPI fetch (skipped within 24h
    cache window). Network errors are silenced. ``now`` and ``frozen`` are
    injectable for tests.
    """
    # Lazy import to keep health_check.py importable without health_signals.
    from health_signals import (
        _all_channels,
        _check_auth_wall,
        _check_cookies_age,
        _check_login_required,
        _check_no_new_downloads,
        _check_stale,
        _check_yt_dlp,
    )

    now = now or _now()
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    cache_path = cache_path or default_cache_path()

    # Hold the lock across read-modify-write so a concurrent
    # ``record_fetch_outcome`` / ``dismiss_issue`` doesn't get clobbered.
    with _CACHE_LOCK:
        cache = load_health_cache(cache_path)
        flat = _all_channels(channels)

        issues: list[HealthIssue] = []
        issues += _check_stale(flat, now)
        issues += _check_auth_wall(flat, config, now)
        issues += _check_no_new_downloads(flat, records, now)
        issues += _check_login_required(flat, config, cache)
        issues += _check_cookies_age(config, now)
        issues += _check_yt_dlp(cache, now, online=check_yt_dlp, frozen=frozen)

        # Persist cache (yt-dlp check may have refreshed it).
        save_health_cache(cache_path, cache)

    # Apply dismissals — info/warn drop if dismissed; errors always show.
    dismissed = set(cache.get("dismissed", []) or [])
    issues = [
        i for i in issues
        if not (i.id in dismissed and i.severity != "error")
    ]
    return HealthReport(issues=issues, computed_at=_iso(now))


# ── CLI entry ─────────────────────────────────────────────────────────────


def _cli() -> int:
    """Pretty-print the current health report (KISS — plain print, no Rich)."""
    from config import (
        SAVED_CHANNELS_PATH,
        load_config,
        load_history_records,
    )
    from saved_channels_store import load_saved_channels

    config = load_config()
    store = load_saved_channels(SAVED_CHANNELS_PATH)
    records = load_history_records()
    report = compute_health(store, records, config, check_yt_dlp=True)
    if not report.issues:
        print("All good — no issues detected.")
        return 0
    print(f"{len(report.issues)} issue(s) at {report.computed_at}:")
    for i in report.issues:
        print(f"  [{i.severity:>5}] {i.title}")
        if i.detail:
            print(f"           {i.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())


__all__ = [
    "HealthIssue",
    "HealthReport",
    "Severity",
    "FixActionKind",
    "SEVERITY_RANK",
    "compute_health",
    "load_health_cache",
    "save_health_cache",
    "record_fetch_outcome",
    "dismiss_issue",
    "default_cache_path",
]
