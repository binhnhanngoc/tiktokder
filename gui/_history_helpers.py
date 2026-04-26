"""Shared helpers for history-row formatting and OS file actions.

Extracted from `gui/history_tab.py` so `gui/library_panel.py` can reuse them
without dragging the legacy widget along.
"""

from __future__ import annotations

import os
import subprocess
import sys


def format_size(size_bytes: int | None) -> str:
    """Render byte count as human-readable string. `None`/0 → `—`."""
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    val = float(size_bytes)
    idx = 0
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    return f"{val:.1f} {units[idx]}"


def format_date(iso: str | None) -> str:
    """Compact `YYYY-MM-DD HH:MM` from ISO8601. `None` → `—`."""
    if not iso:
        return "—"
    date_part, _, rest = iso.partition("T")
    time_part = rest.split("+", 1)[0].split("-", 1)[0]
    return f"{date_part} {time_part[:5]}".strip() if rest else date_part


def open_path(path: str) -> bool:
    """Open ``path`` with the OS default handler. False when missing."""
    if not path or not os.path.exists(path):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except OSError:
        return False


def reveal_in_file_manager(path: str) -> bool:
    """Open OS file manager with ``path`` highlighted. False when missing."""
    if not path or not os.path.exists(path):
        return False
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path) or "."])
        return True
    except OSError:
        return False
