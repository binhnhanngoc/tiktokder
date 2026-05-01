# Release Process

TikTokDer follows [SemVer](https://semver.org/): MAJOR.MINOR.PATCH (see `docs/project-changelog.md` "Versioning Policy" for triggers).

## Single Source of Truth

`version.py` — `__version__` is the only digit-bearing literal that matters. `__version_info__` is parsed from it at import time.

## Manual-Bump Locations (3)

On every release, update these together:

1. `version.py` — `__version__ = "X.Y.Z"`
2. `README.md` line 5 — `**vX.Y.Z**` (intentionally manual; one literal)
3. `docs/project-changelog.md` — prepend new `## [X.Y.Z] — YYYY-MM-DD — short headline` entry

The drift test in `test_version.py` enforces all three stay in lockstep.

## Build

```bash
python build.py
```

Produces `dist/TikTokDer-portable-X.Y.Z.zip`. The Windows EXEs inside have `VSVersionInfo` baked in (right-click → Properties → Details).

## Tag

```bash
git add version.py README.md docs/project-changelog.md
git commit -m "release: vX.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

## Pre-Tag Checklist

- [ ] `version.py`, `README.md`, changelog all show same `X.Y.Z`
- [ ] `python -m pytest` passes
- [ ] `python main.py --version` prints `TikTokDer X.Y.Z`
- [ ] `python build.py` succeeds; zip filename includes `X.Y.Z`
- [ ] Smoke-test built GUI: window title, Help → About both show `vX.Y.Z`
- [ ] Windows EXE Properties → Details shows `X.Y.Z`

## Out of Scope (not automated yet)

- Code-signing the EXEs
- GitHub Releases auto-upload
- Pre-release suffixes (`-rc`, `-beta`)
- Auto-generated release notes from commits
