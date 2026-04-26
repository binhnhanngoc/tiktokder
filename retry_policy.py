"""Tenacity-based retry policy with typed exceptions and Retry-After awareness.

Sits *outside* yt-dlp's own retry loop:
- yt-dlp inner retries handle HTTP/fragment/extractor flakiness per request.
- This outer layer reclassifies terminal failures into typed exceptions and
  decides retry/no-retry based on exception class.

`download_video` raises one of the typed exceptions below; tenacity catches
retryable ones (RateLimited / TransientFailure) and waits with either a
Retry-After-honored delay or decorrelated jitter. Permanent classes
(LoginRequired / Private / NotFound) propagate immediately.
"""

import logging
import random
import re
from typing import Callable

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
)

logger = logging.getLogger(__name__)


# --- Typed exceptions ---


class LoginRequired(Exception):
    """URL hits a login wall. Never retry — would only deepen the FB penalty."""


class Private(Exception):
    """Content is private/friends-only. Not retryable."""


class NotFound(Exception):
    """Video unavailable or 404. Not retryable."""


class RateLimited(Exception):
    """HTTP 429 / soft rate limit. Retryable; honors `retry_after` if provided."""

    def __init__(self, msg: str = "", retry_after: float | None = None) -> None:
        super().__init__(msg)
        self.retry_after = retry_after


class TransientFailure(Exception):
    """Network / 5xx / timeout. Retryable with decorrelated jitter."""


class PermanentFailure(Exception):
    """Unrecoverable error (e.g., cookie DB read failure). Not retryable."""


# --- Retry-After parsing ---


_RETRY_AFTER_PATTERN = re.compile(r"Retry-After:\s*(\d+)", re.IGNORECASE)


def parse_retry_after(msg: str) -> float | None:
    """Extract `Retry-After: N` (seconds) from an error message; None if absent.

    HTTP-date format is intentionally not supported — decorrelated-jitter
    fallback covers that case.
    """
    match = _RETRY_AFTER_PATTERN.search(msg)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


# --- Retry predicate ---


def _is_retryable(exc: BaseException) -> bool:
    """True for `RateLimited` and `TransientFailure`; False for everything else."""
    return isinstance(exc, (RateLimited, TransientFailure))


# --- Wait strategies ---


def decorrelated_jitter(
    base: float = 2.0, cap: float = 60.0
) -> Callable[..., float]:
    """AWS-style decorrelated-jitter wait function for tenacity.

    Each call: `prev = min(cap, uniform(base, prev * 3))` — produces a
    smoothed, growing-but-bounded retry distribution. State is closed over.
    """
    state = {"prev": base}

    def _wait(retry_state) -> float:  # noqa: ARG001 - tenacity passes RetryCallState
        sample = random.uniform(base, max(base, state["prev"] * 3))
        state["prev"] = min(cap, sample)
        return state["prev"]

    return _wait


def retry_after_aware_wait(
    base: float = 2.0, cap: float = 60.0
) -> Callable[..., float]:
    """Wait function that honors `RateLimited.retry_after` when present.

    Falls back to decorrelated jitter for transient failures or when no
    retry-after hint was provided.
    """
    fallback = decorrelated_jitter(base=base, cap=cap)

    def _wait(retry_state) -> float:
        outcome = retry_state.outcome
        if outcome is not None:
            exc = outcome.exception()
            if isinstance(exc, RateLimited) and exc.retry_after is not None:
                return min(cap, float(exc.retry_after))
        return fallback(retry_state)

    return _wait


# --- Decorator factory ---


def with_retry(max_attempts: int = 3, base: float = 2.0, cap: float = 60.0):
    """Return a tenacity decorator wrapping a callable with the project's retry policy.

    - `max_attempts`: outer retry budget (yt-dlp keeps its own inner budget).
    - Retries only on `RateLimited` and `TransientFailure`.
    - Wait honors `Retry-After` first, decorrelated jitter otherwise.
    - Reraises the terminal exception so callers can map back to `DownloadResult`.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        retry=retry_if_exception(_is_retryable),
        wait=retry_after_aware_wait(base=base, cap=cap),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True,
    )
