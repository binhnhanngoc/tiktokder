"""yt-dlp wrapper for downloading TikTok videos."""

import logging
import os
import re
import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

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
from url_parser import extract_video_id
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()


@dataclass
class DownloadResult:
    """Result of a single video download attempt."""
    url: str
    success: bool
    video_id: str | None = None
    title: str | None = None
    error: str | None = None
    skipped: bool = False


def get_ydl_opts(
    output_dir: str,
    cookie_browser: str | None = None,
) -> dict:
    """Return yt-dlp options dict optimized for TikTok downloads."""
    opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s_%(title).50s.%(ext)s"),
        "format": "b",  # Single best stream (avoids watermark + merge failures)
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "buffersize": 65536,  # 64KB buffer — reduces syscall overhead
        "throttled_rate": 10240,  # Re-extract URL only if below 10KB/s (TikTok CDN baseline is ~50KB/s)
        "retries": 5,
        "socket_timeout": 30,  # Fail fast on stalled connections
        "impersonate": ImpersonateTarget("chrome", "136"),  # Bypass TLS fingerprint detection
    }
    if cookie_browser:
        opts["cookiesfrombrowser"] = (cookie_browser,)
    return opts


def get_downloaded_ids(output_dir: str) -> set[str]:
    """Scan output dir for already-downloaded video IDs (numeric prefix before _)."""
    ids = set()
    if not os.path.isdir(output_dir):
        return ids
    # Match files starting with a numeric video ID
    pattern = re.compile(r"^(\d{15,25})_")
    for filename in os.listdir(output_dir):
        match = pattern.match(filename)
        if match:
            ids.add(match.group(1))
    return ids


def download_video(
    url: str,
    output_dir: str,
    progress_hook: Callable | None = None,
    cookie_browser: str | None = None,
) -> DownloadResult:
    """Download a single TikTok video. Optional progress_hook receives yt-dlp progress dicts."""
    _warn_ffmpeg_missing()
    opts = get_ydl_opts(output_dir, cookie_browser=cookie_browser)
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return DownloadResult(
                url=url,
                success=True,
                video_id=str(info.get("id", "")),
                title=info.get("title", ""),
            )
    except Exception as e:
        return DownloadResult(url=url, success=False, error=str(e))


def download_batch(
    urls: list[str],
    output_dir: str,
    workers: int = 3,
    delay: float = 1.0,
    skip_ids: set[str] | None = None,
) -> list[DownloadResult]:
    """Download multiple videos concurrently with progress display."""
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
            time.sleep(delay)
            return result

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_download_with_delay, url): url for url in to_download}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    result = DownloadResult(url=futures[future], success=False, error=str(e))
                results.append(result)
                status = "[green]OK[/green]" if result.success else f"[red]FAIL: {result.error}[/red]"
                progress.console.print(f"  {result.url} -> {status}")
                progress.advance(task)

    return results
