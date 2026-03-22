"""Build TikTokDer standalone executable via PyInstaller."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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

    print("\nBuild complete: dist/TikTokDer/")
    print("  GUI: dist/TikTokDer/TikTokDer.exe")
    print("  CLI: dist/TikTokDer/TikTokDer-CLI.exe")


if __name__ == "__main__":
    main()
