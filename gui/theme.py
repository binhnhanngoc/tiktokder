"""Theme bootstrap, live OS-follow listener, and Settings-driven mode switch.

Single owner of theme transitions. Public API:

* ``bootstrap(app, config)`` — call once at startup before window.show().
* ``apply(mode)`` — re-apply qdarktheme + sync ``gui.tokens`` to resolved palette.
* ``set_mode(mode)`` — Settings-side handler: validate, persist will be done
  by caller, apply theme, start/stop OS listener.

The ``darkdetect`` listener runs on a daemon thread and marshals theme
changes back to the Qt main thread via a Signal — never touch Qt from the
listener thread directly.
"""

from __future__ import annotations

import threading
from typing import Optional

import darkdetect
import qdarktheme
from PySide6.QtCore import QObject, Signal, Slot

from gui import progress_styles, tokens


ACCENT = "#4F46E5"
ALLOWED_MODES = ("system", "light", "dark")

_listener_thread: Optional[threading.Thread] = None
_bridge: Optional["_ThemeBridge"] = None
_current_mode: str = "system"


class _ThemeBridge(QObject):
    """Cross-thread bridge — listener emits, main thread receives."""

    system_theme_changed = Signal(str)  # "Light" | "Dark"

    @Slot(str)
    def _on_system_theme_changed(self, name: str) -> None:
        # Honor manual override: ignore OS flips when user pinned light/dark.
        if _current_mode != "system":
            return
        apply("system")


def _resolved_palette() -> str:
    """Return ``"dark"`` or ``"light"`` based on the OS-resolved theme."""
    return "dark" if darkdetect.isDark() else "light"


def apply(mode: str) -> None:
    """Apply a theme to the running QApplication and sync token palette.

    ``mode`` can be ``"system"`` (auto-detect), ``"light"``, or ``"dark"``.
    Safe to call multiple times.
    """
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of {ALLOWED_MODES}, got {mode!r}")

    qdarktheme_mode = "auto" if mode == "system" else mode
    try:
        qdarktheme.setup_theme(
            qdarktheme_mode, custom_colors={"primary": ACCENT}
        )
    except TypeError:
        # API drift fallback: older signatures may not accept custom_colors.
        qdarktheme.setup_theme(qdarktheme_mode)

    palette = mode if mode in ("light", "dark") else _resolved_palette()
    tokens.set_mode(palette)
    # Repaint any progress bars that registered themselves with the new palette.
    progress_styles.refresh_all()


def _start_listener_if_needed(mode: str) -> None:
    """Spawn the daemon OS-theme listener exactly once when in system mode."""
    global _listener_thread, _bridge
    if mode != "system":
        return
    if _listener_thread is not None and _listener_thread.is_alive():
        return

    _bridge = _ThemeBridge()
    _bridge.system_theme_changed.connect(_bridge._on_system_theme_changed)

    def _runner() -> None:
        try:
            darkdetect.listener(lambda name: _bridge.system_theme_changed.emit(name))
        except Exception:
            # darkdetect is best-effort across DEs; swallow to avoid taking
            # the app down if the listener thread errors.
            pass

    _listener_thread = threading.Thread(
        target=_runner, name="darkdetect-listener", daemon=True
    )
    _listener_thread.start()


def bootstrap(app, config) -> None:
    """Startup entry point: apply saved mode and start listener if needed."""
    global _current_mode
    mode = getattr(config, "theme_mode", "system")
    if mode not in ALLOWED_MODES:
        mode = "system"
    _current_mode = mode
    apply(mode)
    _start_listener_if_needed(mode)


def set_mode(mode: str) -> None:
    """Settings-driven mode switch. Caller persists ``config.theme_mode``."""
    global _current_mode
    if mode not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of {ALLOWED_MODES}, got {mode!r}")
    _current_mode = mode
    apply(mode)
    _start_listener_if_needed(mode)


def current_mode() -> str:
    """Active theme mode (``system`` | ``light`` | ``dark``)."""
    return _current_mode
