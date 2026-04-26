"""Shared yt-dlp option helpers — kept out of downloader.py to keep that
file focused on the download pipeline.
"""

from __future__ import annotations

import os


def apply_cookies(
    ydl_opts: dict,
    browser: str | None,
    file_path: str | None,
) -> None:
    """Mutate ``ydl_opts`` to add a cookie source.

    Precedence: an existing cookie *file* on disk wins over a *browser*
    cookie DB. Mutually exclusive in practice — yt-dlp's behavior with both
    set is undefined. Missing/empty file silently falls through to browser.
    """
    if file_path and os.path.isfile(file_path):
        ydl_opts["cookiefile"] = file_path
    elif browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)


__all__ = ["apply_cookies"]
