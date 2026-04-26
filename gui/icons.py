"""qtawesome wrapper. Single source for icon lookups across the GUI.

Callers must use ``from gui.icons import icon`` — direct ``import qtawesome``
elsewhere is a violation. Cache keys are ``(name, color)`` so explicit color
overrides are memoized separately.
"""

from __future__ import annotations

import qtawesome as qta
from PySide6.QtGui import QIcon

_CACHE: dict[tuple[str, str | None], QIcon] = {}


def icon(name: str, color: str | None = None) -> QIcon:
    """Return a (cached) ``QIcon`` for the given qtawesome name (e.g. ``mdi6.plus``)."""
    key = (name, color)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    qicon = qta.icon(name, color=color) if color else qta.icon(name)
    _CACHE[key] = qicon
    return qicon
