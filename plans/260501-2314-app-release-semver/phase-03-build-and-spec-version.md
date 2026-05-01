# Phase 03 — Build artifact + Windows EXE metadata

## Context Links
- Plan overview: `plan.md`
- Blocker: `phase-01-version-ssot-and-wireup.md`
- Existing build pipeline: `build.py:10` (`ZIP_STEM = "TikTokDer-portable"`), `tiktokder.spec` (GUI EXE at line 92, CLI EXE at line 134)

## Overview
- **Priority:** P2
- **Status:** pending
- **Description:** Stamp the version onto the distributable artifact in two places: (a) zip filename `TikTokDer-portable-1.4.0.zip`, (b) Windows VSVersionInfo metadata baked into both EXEs (visible in Properties → Details).

## Key Insights
- `build.py` is small (~60 lines) — just import `__version__` and embed in `ZIP_STEM`.
- PyInstaller's `EXE()` accepts a `version` parameter that takes either a path to a version-info text file **or** a `VSVersionInfo` instance. We use the latter, inline in the spec — no separate `version_info.txt` file (per scope constraint).
- `VSVersionInfo` requires version as a 4-tuple `(MAJOR, MINOR, PATCH, BUILD)` — we use BUILD=0 since SemVer has no build component.
- Both GUI EXE and CLI EXE get the same metadata (single inline helper, DRY).
- Spec runs as a Python file at PyInstaller invocation, so `from version import __version__, __version_info__` works as long as the spec's working directory is the repo root (it is, by default invocation).

## Requirements
**Functional**
- `python build.py` produces `dist/TikTokDer-portable-1.4.0.zip` (filename includes version).
- `dist/TikTokDer/TikTokDer.exe` Properties → Details shows: ProductName=TikTokDer, ProductVersion=1.4.0, FileVersion=1.4.0.0.
- `dist/TikTokDer/TikTokDer-CLI.exe` shows the same metadata.

**Non-functional**
- No new files (no `version_info.txt`).
- VSVersionInfo construction stays inline in `tiktokder.spec`, single `_build_version_info()` helper to avoid duplicating the dict for GUI vs CLI EXE (DRY).

## Architecture
```
version.py
   │
   ├─► build.py           (ZIP_STEM f-string)
   │
   └─► tiktokder.spec
          ├─► _build_version_info(__version_info__)  # local helper
          ├─► EXE(... version=_build_version_info(...))   # GUI
          └─► EXE(... version=_build_version_info(...))   # CLI
```

## Related Code Files
**Modify**
- `build.py` — import `__version__`, change `ZIP_STEM` from constant to f-string at usage site.
- `tiktokder.spec` — import `__version_info__`, define `_build_version_info()`, pass to both `EXE()` calls.

**Create / Delete**
- None.

## Implementation Steps
1. Edit `build.py`:
   - Add `from version import __version__` near top.
   - Replace `ZIP_STEM = "TikTokDer-portable"` with `ZIP_STEM = f"TikTokDer-portable-{__version__}"`.
   - Verify the `print(f"  Zip:    {zip_path}.zip")` line still resolves correctly (it will — `zip_path` already uses `ZIP_STEM`).
2. Edit `tiktokder.spec`:
   - Add at top (after the existing imports):
     ```python
     from version import __version_info__

     from PyInstaller.utils.win32.versioninfo import (
         VSVersionInfo, FixedFileInfo, StringFileInfo,
         StringTable, StringStruct, VarFileInfo, VarStruct,
     )

     def _build_version_info() -> VSVersionInfo:
         major, minor, patch = __version_info__
         filevers = (major, minor, patch, 0)
         ver_str = f"{major}.{minor}.{patch}"
         return VSVersionInfo(
             ffi=FixedFileInfo(filevers=filevers, prodvers=filevers,
                               mask=0x3F, flags=0x0, OS=0x40004,
                               fileType=0x1, subtype=0x0, date=(0, 0)),
             kids=[
                 StringFileInfo([StringTable("040904B0", [
                     StringStruct("CompanyName", "TikTokDer"),
                     StringStruct("FileDescription", "TikTok & Facebook Batch Video Downloader"),
                     StringStruct("FileVersion", ver_str),
                     StringStruct("ProductName", "TikTokDer"),
                     StringStruct("ProductVersion", ver_str),
                     StringStruct("OriginalFilename", "TikTokDer.exe"),
                 ])]),
                 VarFileInfo([VarStruct("Translation", [0x0409, 0x04B0])]),
             ],
         )
     ```
   - Add `version=_build_version_info(),` to the GUI `EXE(...)` call (around line 92, alongside `icon='assets/icon.ico'`).
   - Add `version=_build_version_info(),` to the CLI `EXE(...)` call (around line 134).
   - **Note:** `OriginalFilename` is "TikTokDer.exe" for both EXEs — Windows convention; Properties dialog still reads `FileDescription`/`ProductName` correctly. Acceptable cosmetic compromise to keep one helper.
3. Local build verification:
   - `python build.py` (Windows host).
   - Confirm `dist/TikTokDer-portable-1.4.0.zip` exists.
   - Right-click `dist/TikTokDer/TikTokDer.exe` → Properties → Details → ProductVersion = 1.4.0.

## Todo List
- [ ] `build.py` imports `__version__`, `ZIP_STEM` includes version
- [ ] `tiktokder.spec` imports `__version_info__`, defines `_build_version_info()`
- [ ] GUI `EXE(...)` call gets `version=_build_version_info()`
- [ ] CLI `EXE(...)` call gets `version=_build_version_info()`
- [ ] `python build.py` produces `TikTokDer-portable-1.4.0.zip`
- [ ] Windows Properties dialog shows v1.4.0 on built GUI EXE
- [ ] Windows Properties dialog shows v1.4.0 on built CLI EXE

## Success Criteria
- Zip filename: `TikTokDer-portable-1.4.0.zip`.
- Both EXEs show v1.4.0 in Windows Properties → Details.
- No new files created in repo root (no `version_info.txt`).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PyInstaller version-info import path varies across versions | Low | Medium | Imports from `PyInstaller.utils.win32.versioninfo` — stable since PyInstaller 5.x; pin in `requirements.txt` if it breaks |
| Spec file runs from wrong CWD and can't import `version` | Low | High | `build.py` invokes PyInstaller from repo root via `subprocess.run` — CWD is repo root; document if anyone invokes spec directly |
| VSVersionInfo only meaningful on Windows; macOS/Linux ignore it | Certain | None | By design — non-Windows builds simply don't read this metadata |
| `FixedFileInfo` `mask`/`flags`/`OS` magic numbers wrong | Low | Low | Values copied from PyInstaller's documented examples — Microsoft VERSIONINFO standard constants |

## Security Considerations
- Build artifacts unsigned — out of scope for this plan. Document in release-process.md as a known limitation/follow-up.

## Next Steps
After build artifacts ship with version, follow-up consideration: code-signing the EXEs (out of scope, separate plan).
