"""Version SSOT and drift tests.

Enforces:
- ``__version__`` is a valid SemVer MAJOR.MINOR.PATCH string.
- ``__version_info__`` is the parsed 3-tuple of ints.
- CLI ``--version`` prints ``TikTokDer X.Y.Z``.
- README badge and the latest changelog entry stay in lockstep with ``version.py``.
"""

import re
import subprocess
import sys
from pathlib import Path

from version import __version__, __version_info__

ROOT = Path(__file__).resolve().parent


def test_version_string_format() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


def test_version_info_tuple() -> None:
    parts = tuple(int(p) for p in __version__.split("."))
    assert __version_info__ == parts
    assert len(__version_info__) == 3
    assert all(isinstance(p, int) for p in __version_info__)


def test_cli_version_flag() -> None:
    # 30s headroom: cold yt-dlp/rich imports in main.py take 3-8s on Windows under AV scanning.
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    # argparse writes --version to stdout (Python 3.4+).
    assert result.stdout.strip() == f"TikTokDer {__version__}"


def test_readme_version_matches_ssot() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:20])
    assert f"**v{__version__}**" in head, (
        "README.md badge does not match version.py — bump README.md line 5 alongside version.py"
    )


def test_changelog_latest_matches_ssot() -> None:
    text = (ROOT / "docs" / "project-changelog.md").read_text(encoding="utf-8")
    # First "## [X.Y.Z]" or "### [vX.Y.Z]" heading wins; the "## Versioning Policy" preamble has no brackets.
    match = re.search(r"^#{2,3}\s*\[v?(\d+\.\d+\.\d+)\]", text, flags=re.MULTILINE)
    assert match, "no version heading found in changelog"
    assert match.group(1) == __version__, (
        f"latest changelog entry {match.group(1)} != version.py {__version__}"
    )
