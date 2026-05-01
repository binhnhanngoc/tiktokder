"""Build TikTokDer portable app via PyInstaller, then zip the onedir bundle."""

import shutil
import subprocess
import sys
from pathlib import Path

from version import __version__

ROOT = Path(__file__).resolve().parent
DIST_NAME = "TikTokDer"
ZIP_STEM = f"TikTokDer-portable-{__version__}"


def main() -> None:
    # Clean previous build artifacts
    for dirname in ("build", "dist"):
        path = ROOT / dirname
        if path.exists():
            print(f"Cleaning {dirname}/...")
            shutil.rmtree(path)

    # Run PyInstaller with the spec file
    spec_file = str(ROOT / "tiktokder.spec")
    cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\nBuild failed!", file=sys.stderr)
        sys.exit(1)

    dist_dir = ROOT / "dist" / DIST_NAME
    # Seed an empty downloads folder so users see it on first extract
    (dist_dir / "downloads").mkdir(exist_ok=True)
    # Drop a README-style portable notice (plain text, no docs rules apply)
    (dist_dir / "PORTABLE.txt").write_text(
        "TikTokDer Portable\n"
        "==================\n"
        "This is a portable build. Configuration and downloads are stored\n"
        "next to the executables, so the whole folder is self-contained.\n\n"
        "  TikTokDer.exe       - desktop GUI\n"
        "  TikTokDer-CLI.exe   - command-line interface\n"
        "  data/               - settings + history (created on first run)\n"
        "  downloads/          - default output folder\n",
        encoding="utf-8",
    )

    # Zip the onedir bundle for distribution
    zip_path = ROOT / "dist" / ZIP_STEM
    print(f"\nZipping {dist_dir} -> {zip_path}.zip ...")
    shutil.make_archive(str(zip_path), "zip", root_dir=dist_dir.parent, base_dir=DIST_NAME)

    print("\nBuild complete:")
    print(f"  Folder: {dist_dir}")
    print(f"  GUI:    {dist_dir / 'TikTokDer.exe'}")
    print(f"  CLI:    {dist_dir / 'TikTokDer-CLI.exe'}")
    print(f"  Zip:    {zip_path}.zip")


if __name__ == "__main__":
    main()
