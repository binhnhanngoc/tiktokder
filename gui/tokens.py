"""Semantic color tokens with light/dark palettes.

Resolved at call time so live theme switching (see ``gui.theme``) is reflected
immediately in any stylesheet that re-reads through ``token(...)``. Pure
Python — no PySide6 import — so the module remains testable headlessly.

Note: Stylesheets built once at widget construction will NOT auto-refresh
after ``set_mode`` flips the palette. Tier-1 accepts this; downstream tiers
may add a repaint-orchestration helper.
"""

from __future__ import annotations

# 15 keys — bg/border/text/accent/state. ``state.info`` reserved for future
# toast/InfoBar work; harmless to keep present now.
LIGHT: dict[str, str] = {
    "bg.canvas": "#FFFFFF",
    "bg.surface": "#F7F8FA",
    "bg.subtle": "#EEF0F4",
    "border.default": "#E2E5EB",
    "border.strong": "#C7CCD6",
    "text.primary": "#11151C",
    "text.secondary": "#3A4150",
    "text.muted": "#6B7280",
    "accent.default": "#4F46E5",
    "accent.hover": "#4338CA",
    "accent.fg": "#FFFFFF",
    "state.success": "#16A34A",
    "state.warning": "#D97706",
    "state.error": "#DC2626",
    "state.info": "#0284C7",
}

DARK: dict[str, str] = {
    "bg.canvas": "#0F1115",
    "bg.surface": "#161A21",
    "bg.subtle": "#1C2129",
    "border.default": "#2A2F3A",
    "border.strong": "#3A4150",
    "text.primary": "#E6E9EF",
    "text.secondary": "#A6ADBB",
    "text.muted": "#7A8493",
    "accent.default": "#6366F1",
    "accent.hover": "#818CF8",
    "accent.fg": "#FFFFFF",
    "state.success": "#22C55E",
    "state.warning": "#F59E0B",
    "state.error": "#EF4444",
    "state.info": "#38BDF8",
}

# Invariant: both palettes expose identical key sets.
assert LIGHT.keys() == DARK.keys(), "LIGHT and DARK palettes must share keys"

_ALLOWED_MODES = ("light", "dark")
_mode: str = "light"


def set_mode(mode: str) -> None:
    """Activate ``"light"`` or ``"dark"`` for subsequent ``token`` lookups."""
    global _mode
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"mode must be one of {_ALLOWED_MODES}, got {mode!r}")
    _mode = mode


def current_mode() -> str:
    """Return the currently active palette name (``"light"`` | ``"dark"``)."""
    return _mode


def token(name: str) -> str:
    """Look up the hex color for ``name`` in the active palette."""
    palette = DARK if _mode == "dark" else LIGHT
    return palette[name]
