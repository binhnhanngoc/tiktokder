"""Polished QProgressBar styling driven by semantic tokens.

Two visual variants:
  * ``determinate``  — rounded groove + filled chunk, ~14px tall, centered text
  * ``indeterminate`` — slim 6px marquee bar (used while fetching channel lists)

Four color states (set independently of variant):
  * ``normal``  → ``accent.default`` (indigo)
  * ``success`` → ``state.success`` (green) — download finished
  * ``error``   → ``state.error``   (red)   — download failed
  * ``muted``   → ``text.muted``    (gray)  — skipped / cancelled

Bars register themselves in a ``WeakSet`` on first ``apply``; ``refresh_all``
re-applies QSS after a token-palette flip so light↔dark theme switches repaint
without recreating widgets. ``WeakSet`` lets garbage-collected widgets fall out
on their own — no manual unregister needed.
"""

from __future__ import annotations

from weakref import WeakSet

from PySide6.QtWidgets import QProgressBar

from gui import tokens


_VARIANT_PROP = "_pb_variant"
_STATE_PROP = "_pb_state"

_DEFAULT_VARIANT = "determinate"
_DEFAULT_STATE = "normal"

_registry: "WeakSet[QProgressBar]" = WeakSet()


def _chunk_color(state: str) -> str:
    if state == "success":
        return tokens.token("state.success")
    if state == "error":
        return tokens.token("state.error")
    if state == "muted":
        return tokens.token("text.muted")
    return tokens.token("accent.default")


def _build_qss(variant: str, state: str) -> str:
    chunk = _chunk_color(state)
    border = tokens.token("border.default")
    groove = tokens.token("bg.subtle")
    text = tokens.token("text.primary")

    if variant == "indeterminate":
        return (
            "QProgressBar {"
            f" border: 1px solid {border};"
            " border-radius: 4px;"
            f" background-color: {groove};"
            " min-height: 6px;"
            " max-height: 6px;"
            " }"
            "QProgressBar::chunk {"
            f" background-color: {chunk};"
            " border-radius: 3px;"
            " }"
        )

    # determinate
    return (
        "QProgressBar {"
        f" border: 1px solid {border};"
        " border-radius: 6px;"
        f" background-color: {groove};"
        f" color: {text};"
        " text-align: center;"
        " min-height: 14px;"
        " font-size: 10px;"
        " font-weight: 600;"
        " }"
        "QProgressBar::chunk {"
        f" background-color: {chunk};"
        " border-radius: 5px;"
        " margin: 1px;"
        " }"
    )


def apply(
    bar: QProgressBar,
    variant: str = _DEFAULT_VARIANT,
    state: str = _DEFAULT_STATE,
) -> None:
    """Apply polished styling and register the bar for live theme refresh."""
    bar.setProperty(_VARIANT_PROP, variant)
    bar.setProperty(_STATE_PROP, state)
    bar.setStyleSheet(_build_qss(variant, state))
    _registry.add(bar)


def set_state(bar: QProgressBar, state: str) -> None:
    """Switch chunk color (e.g. ``success`` on completion). No-op if unstyled."""
    variant = bar.property(_VARIANT_PROP) or _DEFAULT_VARIANT
    bar.setProperty(_STATE_PROP, state)
    bar.setStyleSheet(_build_qss(variant, state))
    _registry.add(bar)


def refresh_all() -> None:
    """Re-apply QSS for every registered bar. Call after a token-mode flip."""
    for bar in list(_registry):
        variant = bar.property(_VARIANT_PROP) or _DEFAULT_VARIANT
        state = bar.property(_STATE_PROP) or _DEFAULT_STATE
        bar.setStyleSheet(_build_qss(variant, state))
