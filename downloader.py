"""yt-dlp wrapper for downloading TikTok videos."""

import logging
import os
import random
import re
import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Literal

import yt_dlp

logger = logging.getLogger(__name__)

_ffmpeg_warned = False


def _warn_ffmpeg_missing() -> None:
    """Warn once if ffmpeg is not on PATH (called before first download)."""
    global _ffmpeg_warned
    if _ffmpeg_warned:
        return
    _ffmpeg_warned = True
    if not shutil.which("ffmpeg"):
        logger.warning(
            "ffmpeg not found on PATH. Most downloads work without it (single-stream "
            "format), but some videos requiring stream merging may fail. Install ffmpeg "
            "for full compatibility."
        )
from yt_dlp.networking.impersonate import ImpersonateTarget
from url_parser import extract_video_id, detect_platform
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import (
    FB_LOGIN_WALL_MARKERS,
    get_platform_defaults,
    get_max_retry_attempts,
)
from yt_dlp_helpers import apply_cookies
from retry_policy import (
    LoginRequired,
    Private,
    NotFound,
    RateLimited,
    TransientFailure,
    PermanentFailure,
    parse_retry_after,
    with_retry,
)

console = Console()


# yt-dlp `retry_sleep_functions` callables: exponential + jitter capped per layer.
# These are the *inner* retry waits — yt-dlp invokes them between its own retry attempts.
_RETRY_SLEEP_FUNCTIONS = {
    "http": lambda n: min(60.0, 2 ** n + random.uniform(0, 1)),
    "fragment": lambda n: float(min(30, 2 ** n)),
    "extractor": lambda n: float(min(120, 5 * (2 ** n))),
}


# Mapping of error-classification kinds returned by `_classify_error`.
ErrorKind = Literal[
    "login_required",
    "private",
    "not_found",
    "rate_limited",
    "transient",
    "unknown",
]


def _jittered_sleep(
    mean: float,
    std: float,
    floor: float,
    rng: random.Random | None = None,
) -> None:
    """Sleep `max(floor, gauss(mean, std))` seconds.

    Gaussian jitter mimics human pacing; floor clamp guarantees non-negative wait.
    `rng` is injectable for deterministic tests.
    """
    sampler = rng if rng is not None else random
    delay = max(floor, sampler.gauss(mean, std))
    time.sleep(delay)


def _classify_error(exc: Exception) -> ErrorKind:
    """Classify a yt-dlp error message into a typed `ErrorKind`.

    Pure function over `str(exc)` — easy to unit-test. Returns `"unknown"` as
    safe fallback (Phase 04 treats unknown as retryable transient).
    """
    msg = str(exc)
    msg_lower = msg.lower()

    # Login-wall HTML markers (FB) — most specific; check first.
    if any(marker in msg for marker in FB_LOGIN_WALL_MARKERS):
        return "login_required"
    if "login" in msg_lower and ("required" in msg_lower or "redirect" in msg_lower):
        return "login_required"
    if "private" in msg_lower:
        return "private"
    if any(s in msg for s in ("404", "Video unavailable")) or "not found" in msg_lower:
        return "not_found"
    if (
        "HTTP Error 429" in msg
        or "rate limit" in msg_lower
        or "too many requests" in msg_lower
    ):
        return "rate_limited"
    if (
        "HTTP Error 5" in msg
        or "connection" in msg_lower
        or "timeout" in msg_lower
        or "temporarily" in msg_lower
    ):
        return "transient"
    return "unknown"


def _kind_to_exception(kind: ErrorKind, msg: str) -> Exception:
    """Map an `ErrorKind` to a typed exception consumed by the tenacity predicate."""
    if kind == "login_required":
        return LoginRequired(msg)
    if kind == "private":
        return Private(msg)
    if kind == "not_found":
        return NotFound(msg)
    if kind == "rate_limited":
        return RateLimited(msg, retry_after=parse_retry_after(msg))
    # `transient` and `unknown` are both retryable.
    return TransientFailure(msg)


def _exception_to_kind(exc: BaseException) -> ErrorKind:
    """Reverse map a typed exception back to an `ErrorKind` string."""
    if isinstance(exc, LoginRequired):
        return "login_required"
    if isinstance(exc, Private):
        return "private"
    if isinstance(exc, NotFound):
        return "not_found"
    if isinstance(exc, RateLimited):
        return "rate_limited"
    if isinstance(exc, TransientFailure):
        return "transient"
    return "unknown"


def _friendly_error(kind_or_msg: str) -> str:
    """Render an error kind as a user-facing string for progress output."""
    return {
        "login_required": "Login required",
        "private": "Private/restricted",
        "not_found": "Not found",
        "rate_limited": "Rate limited",
        "transient": "Transient failure",
        "unknown": "Unknown error",
    }.get(kind_or_msg, kind_or_msg)


@dataclass
class DownloadResult:
    """Result of a single video download attempt."""
    url: str
    success: bool
    video_id: str | None = None
    title: str | None = None
    error: str | None = None
    skipped: bool = False
    file_path: str | None = None


# Quality preset → yt-dlp `format` expression. yt-dlp falls back to best
# available when a height ceiling is unsatisfiable on a given platform.
QUALITY_FORMATS = {
    "best": "b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "audio": "ba/b",
}


def _format_for_quality(quality: str) -> str:
    """Map a quality literal to a yt-dlp format string. Unknown → best."""
    return QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"])


def get_ydl_opts(
    output_dir: str,
    cookie_browser: str | None = None,
    retries: int = 10,
    force_overwrite: bool = False,
    quality: str = "best",
    write_subs: bool = False,
    write_thumb: bool = False,
    cookies_file: str | None = None,
) -> dict:
    """Return yt-dlp options dict.

    `retries` is the inner HTTP-layer retry budget; tenacity in `retry_policy`
    sits above and adds a coarser outer budget. `retry_sleep_functions` apply
    exponential + jitter waits per failure layer (http/fragment/extractor).
    `quality`/`write_subs`/`write_thumb` plug directly into yt-dlp options;
    audio-only quality also wires the FFmpegExtractAudio postprocessor.
    `cookies_file` is a Netscape cookies.txt path (FB auth); when set it
    takes precedence over `cookie_browser` for the same call.
    """
    opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s_%(title).50s.%(ext)s"),
        "format": _format_for_quality(quality),
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "buffersize": 65536,  # 64KB buffer — reduces syscall overhead
        "throttled_rate": 10240,  # Re-extract URL only if below 10KB/s (TikTok CDN baseline is ~50KB/s)
        "retries": retries,
        "extractor_retries": 5,
        "file_access_retries": 3,
        "fragment_retries": 10,
        "sleep_interval_requests": 0.75,  # Per-request randomized pacing inside yt-dlp
        "sleep_interval": 2.0,
        "max_sleep_interval": 8.0,
        "retry_sleep_functions": _RETRY_SLEEP_FUNCTIONS,
        "socket_timeout": 30,  # Fail fast on stalled connections
        "impersonate": ImpersonateTarget("chrome", "136"),  # Bypass TLS fingerprint detection
    }
    apply_cookies(opts, cookie_browser, cookies_file)
    if force_overwrite:
        # Force re-download even if the destination file already exists.
        opts["overwrites"] = True
    if quality == "audio":
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }
        ]
    if write_subs:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = ["en"]
        opts["subtitlesformat"] = "srt/best"
    if write_thumb:
        opts["writethumbnail"] = True
    return opts


def get_downloaded_ids(output_dir: str) -> set[str]:
    """Recursively scan output dir for already-downloaded video IDs.

    Walks subfolders (platform/uploader tree) so old flat-root files and the
    new nested layout are both considered. Symlinks are NOT followed to avoid
    loop attacks if the user puts a symlink inside ``downloads/``.
    """
    ids: set[str] = set()
    if not os.path.isdir(output_dir):
        return ids
    pattern = re.compile(r"^(\d{15,25})_")
    for root, _dirs, files in os.walk(output_dir, followlinks=False):
        for filename in files:
            match = pattern.match(filename)
            if match:
                ids.add(match.group(1))
    return ids


def _do_download(
    url: str,
    output_dir: str,
    progress_hook: Callable | None = None,
    cookie_browser: str | None = None,
    retries: int = 10,
    force_overwrite: bool = False,
    quality: str = "best",
    write_subs: bool = False,
    write_thumb: bool = False,
    base_dir: str | None = None,
    cookies_file: str | None = None,
    page_hint: str | None = None,
) -> dict:
    """Inner download path: invokes yt-dlp; raises typed exception on failure.

    Pre-resolves `fb.watch` shortlinks before yt-dlp sees them so login walls
    surface fast and don't consume retry budget. Computes the platform-aware
    ``outtmpl`` from a metadata-only pass so the per-uploader folder is
    populated before the actual download runs.
    """
    # Lazy import — avoids hard dependency on facebook_resolver module load order.
    from facebook_resolver import is_fb_shortlink, resolve_fb_shortlink
    from path_builder import build_output_template

    if is_fb_shortlink(url):
        canonical, status = resolve_fb_shortlink(url)
        if status == "login_required":
            raise LoginRequired(f"fb.watch shortlink redirects to login: {url}")
        if status == "ok" and canonical and canonical != url:
            logger.debug(f"Resolved shortlink {url} -> {canonical}")
            url = canonical

    opts = get_ydl_opts(
        output_dir,
        cookie_browser=cookie_browser,
        retries=retries,
        force_overwrite=force_overwrite,
        quality=quality,
        write_subs=write_subs,
        write_thumb=write_thumb,
        cookies_file=cookies_file,
    )
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    # Per-call platform-aware outtmpl: metadata pre-pass yields the uploader,
    # then the same `info` is reused for the download via process_ie_result.
    target_base = base_dir or output_dir
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info_meta = ydl.extract_info(url, download=False, process=False)
            except Exception:
                info_meta = None
            opts["outtmpl"] = build_output_template(
                url, info_meta or {}, target_base, page_hint=page_hint,
            )
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info or {}
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        kind = _classify_error(e)
        logger.debug(f"Classified yt-dlp error as {kind}: {msg}")
        raise _kind_to_exception(kind, msg) from e
    except (LoginRequired, Private, NotFound, RateLimited, TransientFailure, PermanentFailure):
        raise
    except Exception as e:
        # Non-yt-dlp errors: classify the message conservatively, default to transient.
        msg = str(e)
        kind = _classify_error(e)
        raise _kind_to_exception(kind, msg) from e


def download_video(
    url: str,
    output_dir: str,
    progress_hook: Callable | None = None,
    cookie_browser: str | None = None,
    retries: int | None = None,
    max_attempts: int | None = None,
    force_overwrite: bool = False,
    quality: str = "best",
    write_subs: bool = False,
    write_thumb: bool = False,
    base_dir: str | None = None,
    return_info: bool = False,
    cookies_file: str | None = None,
    page_hint: str | None = None,
) -> "DownloadResult | tuple[DownloadResult, dict | None]":
    """Download a single video.

    Wraps `_do_download` with the project's retry policy:
    - Inner: yt-dlp's per-request retries (`retries` arg, defaults to platform value).
    - Outer: tenacity (`max_attempts`, defaults to platform value) — only retries
      `RateLimited` and `TransientFailure`; permanent classes propagate immediately.

    Public API stays compatible by default: callers receive a `DownloadResult`.
    Pass ``return_info=True`` to also receive the raw yt-dlp info dict (used by
    the engine to build a HistoryRecord).
    """
    _warn_ffmpeg_missing()

    if retries is None:
        retries = get_platform_defaults(url).retries
    if max_attempts is None:
        max_attempts = get_max_retry_attempts(url)

    @with_retry(max_attempts=max_attempts)
    def _retried() -> dict:
        return _do_download(
            url,
            output_dir,
            progress_hook=progress_hook,
            cookie_browser=cookie_browser,
            retries=retries,
            force_overwrite=force_overwrite,
            quality=quality,
            write_subs=write_subs,
            write_thumb=write_thumb,
            base_dir=base_dir,
            cookies_file=cookies_file,
            page_hint=page_hint,
        )

    info: dict | None = None
    try:
        info = _retried()
    except (LoginRequired, Private, NotFound, RateLimited, TransientFailure) as exc:
        result = DownloadResult(url=url, success=False, error=_exception_to_kind(exc))
        return (result, None) if return_info else result
    except PermanentFailure as exc:
        result = DownloadResult(url=url, success=False, error=str(exc) or "permanent_failure")
        return (result, None) if return_info else result
    except Exception as exc:
        # Defensive catch-all — anything not classified above is treated as raw error.
        result = DownloadResult(url=url, success=False, error=str(exc))
        return (result, None) if return_info else result

    result = DownloadResult(
        url=url,
        success=True,
        video_id=str(info.get("id", "")) if info else "",
        title=(info or {}).get("title", ""),
    )
    return (result, info) if return_info else result


def download_batch(
    urls: list[str],
    output_dir: str,
    workers: int = 3,
    delay: float = 1.0,
    skip_ids: set[str] | None = None,
    delay_std: float | None = None,
    delay_floor: float | None = None,
) -> list[DownloadResult]:
    """Download multiple videos concurrently with progress display.

    `delay` is the *mean* of a gaussian jittered wait between download
    completions. `delay_std` / `delay_floor` default to per-URL platform
    presets when not supplied — TikTok and Facebook pace asymmetrically.
    """
    os.makedirs(output_dir, exist_ok=True)
    skip_ids = skip_ids or set()
    results: list[DownloadResult] = []

    # Filter out already-downloaded URLs (by checking if video ID is in skip_ids)
    to_download = []
    for url in urls:
        vid = extract_video_id(url)
        if vid and vid in skip_ids:
            results.append(DownloadResult(url=url, success=True, video_id=vid, skipped=True))
        else:
            to_download.append(url)

    if not to_download:
        console.print("[yellow]All videos already downloaded. Nothing to do.[/yellow]")
        return results

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=len(to_download))

        def _download_with_delay(url: str) -> DownloadResult:
            result = download_video(url, output_dir)
            # Per-URL platform-aware jitter; falls back to caller-supplied params.
            defaults = get_platform_defaults(url)
            mean = delay if delay is not None else defaults.delay_mean
            std = delay_std if delay_std is not None else defaults.delay_std
            floor = delay_floor if delay_floor is not None else defaults.delay_floor
            _jittered_sleep(mean, std, floor)
            return result

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_download_with_delay, url): url for url in to_download}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    result = DownloadResult(url=futures[future], success=False, error=str(e))
                results.append(result)
                if result.success:
                    status = "[green]OK[/green]"
                else:
                    status = f"[red]FAIL: {_friendly_error(result.error or 'unknown')}[/red]"
                progress.console.print(f"  {result.url} -> {status}")
                progress.advance(task)

    return results
