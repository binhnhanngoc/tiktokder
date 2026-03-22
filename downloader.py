"""yt-dlp wrapper for downloading TikTok videos."""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import yt_dlp
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


def get_ydl_opts(output_dir: str) -> dict:
    """Return yt-dlp options dict for TikTok downloads."""
    return {
        "outtmpl": os.path.join(output_dir, "%(id)s_%(title).50s.%(ext)s"),
        "format": "best",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }


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


def download_video(url: str, output_dir: str) -> DownloadResult:
    """Download a single TikTok video."""
    opts = get_ydl_opts(output_dir)
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
