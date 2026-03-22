"""CLI entry point for TikTok & Facebook batch video downloader."""

import argparse
import sys

from rich.console import Console

from url_parser import validate_url, validate_facebook_url, read_batch_file, build_user_url
from downloader import download_batch, get_downloaded_ids

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="TikTok & Facebook Batch Video Downloader")
    parser.add_argument("url", nargs="?", help="Single TikTok or Facebook video URL")
    parser.add_argument("--batch", metavar="FILE", help="Text file with URLs (one per line)")
    parser.add_argument("--user", metavar="USERNAME", help="TikTok username to scrape")
    parser.add_argument(
        "--facebook-page", metavar="PAGE_URL",
        help="Facebook page URL to scrape videos from",
    )
    parser.add_argument("--output", default="./downloads", help="Output directory (default: ./downloads)")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent downloads (default: 3)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between downloads in seconds (default: 1)")
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Validate numeric args
    if args.workers < 1:
        console.print("[red]Error: --workers must be at least 1[/red]")
        sys.exit(1)
    if args.delay < 0:
        console.print("[red]Error: --delay must be non-negative[/red]")
        sys.exit(1)

    # Validate: exactly one input mode
    modes = [args.url, args.batch, args.user, args.facebook_page]
    active = sum(1 for m in modes if m)
    if active == 0:
        console.print("[red]Error: Provide a URL, --batch FILE, --user USERNAME, or --facebook-page URL[/red]")
        sys.exit(1)
    if active > 1:
        console.print("[red]Error: Use only one input mode (URL, --batch, --user, or --facebook-page)[/red]")
        sys.exit(1)

    # Build URL list
    if args.url:
        if not validate_url(args.url):
            console.print(f"[red]Error: Invalid URL: {args.url}[/red]")
            sys.exit(1)
        urls = [args.url]
    elif args.batch:
        urls = read_batch_file(args.batch)
        if not urls:
            console.print("[yellow]Batch file is empty.[/yellow]")
            sys.exit(0)
    elif args.user:
        profile_url = build_user_url(args.user)
        urls = [profile_url]
        console.print(f"[cyan]Scraping user profile: {profile_url}[/cyan]")
    else:
        # --facebook-page: individual video URLs work via yt-dlp without Playwright,
        # but page scraping (listing all videos) requires it.
        if not validate_facebook_url(args.facebook_page):
            console.print(f"[red]Error: Invalid Facebook URL: {args.facebook_page}[/red]")
            sys.exit(1)
        urls = [args.facebook_page]
        console.print(f"[cyan]Scraping Facebook page: {args.facebook_page}[/cyan]")

    # Filter already-downloaded
    skip_ids = get_downloaded_ids(args.output)
    console.print(f"[cyan]Processing {len(urls)} URL(s), {len(skip_ids)} already downloaded[/cyan]")

    # Download
    results = download_batch(urls, args.output, args.workers, args.delay, skip_ids)

    # Summary
    ok = sum(1 for r in results if r.success and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.success)
    console.print(f"\n[bold]Done:[/bold] {ok} downloaded, {skipped} skipped, {failed} failed")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
