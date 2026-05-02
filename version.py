"""Single source of truth for TikTokDer version. Bump ``__version__`` only."""

import re

__version__ = "1.5.0"

# SemVer §2: numeric identifiers MUST NOT include leading zeros.
_match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", __version__)
if _match is None:
    raise ValueError(
        f"version.py: __version__={__version__!r} is not MAJOR.MINOR.PATCH"
    )
__version_info__: tuple[int, int, int] = tuple(int(p) for p in _match.groups())  # type: ignore[assignment]
