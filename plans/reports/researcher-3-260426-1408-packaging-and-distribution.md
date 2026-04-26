# Packaging, Distribution & Cross-Platform Deployment for Python Desktop Apps

**Author:** researcher-3
**Date:** 2026-04-26
**Project context:** tiktokder — PySide6 GUI + Rich CLI, currently shipped via PyInstaller onedir + zip (Windows). Bundles `yt-dlp`, `curl_cffi`, `playwright` (excluded), `certifi`, dynamic extractor submodules.

---

## 1. Executive Summary

- **Bundler choice (today, 2026):** Stick with **PyInstaller** as the default; consider **Nuitka** as a parallel option for Windows where AV false-positives are biting. **PyOxidizer is dead** (no release since Jan 2023), **PyUpdater is archived** — drop both as candidates. **Briefcase** matters only if you also want mobile/native installers and accept GTK/Qt-via-Toga constraints.
- **Single-file vs onedir:** Onedir is the correct default. `--onefile` self-extracts to temp every launch → slow startup, AV heuristics flag it, and on Windows it triples cold-start latency. Tiktokder already uses onedir; keep it.
- **AV false positives:** PyInstaller's bootloader is on multiple AV blocklists. Mitigations (in order of effectiveness): code signing → onedir → recompile bootloader from source → switch to Nuitka. Disabling UPX (which `tiktokder.spec` currently enables) reduces detection by ~30-50%.
- **Code signing economics:** Microsoft's **Azure Artifact Signing** ($10/mo) is the cheapest credible path for Windows in 2026; OV/EV certs from traditional CAs ($150-400/yr) no longer give EV the SmartScreen instant-bypass advantage they once did. Apple Developer Program ($99/yr) is mandatory for macOS distribution outside the Mac App Store.
- **macOS reality:** notarization with `notarytool` is required (altool dead since Nov 2023). PySide6 + PyInstaller still has open issues with hardened runtime (entitlement `com.apple.security.cs.allow-unsigned-executable-memory` required, deep-signing all bundled .dylib/.so).
- **Linux distribution:** **AppImage** for portable single-file delivery (closest analog to current Windows zip), **Flatpak** for desktop trust/Flathub discoverability. Skip Snap unless targeting Ubuntu specifically. .deb/.rpm only if you want repo presence.
- **Auto-update (2026):** **tufup** (TUF-backed, packager-agnostic) is the only actively maintained Python-native option. Most production apps roll custom HTTPS+signature checks against GitHub Releases.
- **CI:** GitHub Actions matrix (windows-latest, macos-14, ubuntu-22.04) with platform-specific signing secrets is the standard. Windows can sign via Azure Trusted Signing action; macOS uses `xcrun notarytool` with App Store Connect API key.
- **Tiktokder-specific risks:** `curl_cffi` ships native binaries (already handled in spec), `yt-dlp` extractors are dynamically imported (already collected), `playwright` is excluded (correct — would add ~200MB Chromium). Bundle size today is ~120-180MB onedir; that's acceptable.
- **Recommended pipeline:** PyInstaller onedir → platform installer (Inno Setup / DMG / AppImage) → Azure Trusted Signing (Win) + notarytool (Mac) → tufup or custom GH-Releases-based updater → GitHub Actions matrix build.

---

## 2. Per-Tool Deep Dive

### 2.1 Bundlers

#### PyInstaller (current incumbent)
- **What it does:** Bundles CPython interpreter + frozen pyc + native libs into an extractable archive. Ships a C bootloader.
- **Bundle modes:** `--onedir` (default, folder of files) and `--onefile` (self-extracting archive). Onefile extracts to `%TEMP%/_MEIxxxxx/` on each run.
- **Output size (PySide6 GUI typical):** 100-180MB onedir; ~120-180MB onefile (compressed). Tiktokder spec excludes `playwright`/`tkinter`/`pytest` — saves ~250MB.
- **Startup:** Onedir ~0.5-2s; onefile 3-10s on cold disk. PyInstaller's onefile is the slowest of all options because of temp-extract.
- **AV false positives:** Notorious. Issues #6754, #8164 in pyinstaller/pyinstaller GitHub. PyInstaller team rebuilds the bootloader periodically to dodge AV signatures. UPX compression (currently ON in tiktokder.spec) increases detection rate by ~30-50% — recommend disabling.
- **OS support:** Windows x64/arm64, macOS x64/arm64 (universal2), Linux x64/arm64.
- **macOS notarization:** Works but pain. Issue #8927 documents PySide6 onedir notarization failures. Need entitlements file with `com.apple.security.cs.allow-unsigned-executable-memory=true`, deep-sign all nested .dylib/.so, then notarytool submit.
- **Maturity:** Most popular (~12.8k stars), wide community, hooks for nearly every package.
- **Verdict:** Default choice. Keep tiktokder on it.

#### Nuitka
- **What it does:** Translates Python → C → native machine code via gcc/clang/MSVC. Produces real compiled binaries.
- **Bundle modes:** `--standalone` (folder), `--onefile` (single exe with similar self-extract penalty), `--module` (single library).
- **Output size (PySide6):** Folder ~80-150MB; onefile ~85MB on macOS for QtCore/QtGui apps.
- **Startup:** Fastest of all options — native code, no interpreter init overhead. 2-4× faster execution than CPython for compute paths; UI code roughly same.
- **AV false positives:** Significantly fewer than PyInstaller — output looks like a normal compiled binary, not a self-extractor.
- **Build time:** 5-30× slower than PyInstaller. First clean build of a PySide6 app: 5-15 minutes vs PyInstaller's 30-90 seconds.
- **License:** AGPL v3 (free). **Nuitka Commercial** (paid subscription) adds IP protection plugins; standard edition does NOT obfuscate source/data.
- **PySide6 plugin:** `--plugin-enable=pyside6` mature; recent fixes in Nuitka 2.8 for QML and single-shot timers.
- **Verdict:** Best Plan B for Windows AV problems. Acceptable trade-off: longer CI builds for fewer Defender complaints.

#### cx_Freeze
- **Bundle modes:** Onedir style (`build` directory), no onefile.
- **Startup:** Reportedly faster than PyInstaller in some real-world tests (8s vs 50s for the same app — old anecdote, take with salt).
- **OS support:** Win/Mac/Linux. Active (v8.5.3 Jan 2026, supports Python 3.10-3.14).
- **Community:** Far smaller (~1.5k stars vs PyInstaller's 12.8k).
- **Verdict:** Niche. Keep on the radar if PyInstaller blocks you, but no compelling reason for tiktokder to switch.

#### Briefcase (BeeWare)
- **What it does:** Packages Python project as native installer per OS (.msi, .dmg, .deb, .rpm, .pkg, .AppImage, plus iOS/Android).
- **Approach:** Ships an isolated Python interpreter per app (huge bundle but predictable).
- **2025 updates:** PDB+VSCode debugger integration; Toga Qt backend (KDE-native); MSI install-dir customization; cross-platform Bluetooth permission API.
- **Limitations:** No cross-compilation — must build on each target OS (Mac for .dmg, Windows for .msi, etc.). Best fit for Toga GUIs; awkward with PySide6 (works but you lose the BeeWare value-add).
- **Verdict:** Good if you want native installers + mobile from day one. Overkill for a Windows-first app like tiktokder; PySide6 + PyInstaller + Inno Setup is leaner.

#### py2app (macOS only)
- **What it does:** Builds .app bundles from Python scripts on macOS.
- **Status:** Active but niche. Some prefer it over PyInstaller specifically for macOS because it produces a more conventional .app structure.
- **Verdict:** Consider only if PyInstaller's macOS output keeps failing notarization. Adds another tool to maintain.

#### PyOxidizer
- **Status:** **Abandoned.** No release since January 2023. Maintainer (Gregory Szorc) confirmed in issue #741 they're unlikely to return. Anki has begun migrating away (issue #3081).
- **Verdict:** Do not adopt. Migrate off if you're already on it.

#### Shiv / PEX
- **What they are:** Zipapp-style bundles (`.pyz`/`.pex`) — assume Python installed on target.
- **Verdict:** Not viable for desktop GUI distribution (assumes target has matching Python). Skip.

### 2.2 Code Signing

#### Windows
- **Authenticode** is the signature format. Three certificate paths in 2026:
  - **Microsoft Azure Artifact Signing** (formerly Trusted Signing): $10/month or $9.99 base for 5,000 sigs/mo + $0.005/sig overage. **Cheapest credible option.** Requires Azure subscription. Available to individuals in US/Canada (no longer requires 3-year history as of April 2026). EU/UK + organizations also supported.
  - **OV (Organization Validation) certificate:** $150-300/year from CAs like Sectigo/SSL.com/DigiCert. Now requires hardware token (HSM) for key storage since CA/B Forum 2023 baseline.
  - **EV (Extended Validation):** $400+/year. **Both EV and OV now have equivalent SmartScreen behavior** for new files (Microsoft policy change). EV is no longer worth the premium for SmartScreen alone; only justified for kernel drivers or enterprise procurement requirements.
- **SmartScreen reputation:** Builds automatically as downloads accumulate. Initial publish always shows the warning regardless of cert type for unsigned-by-this-publisher files; reputation kicks in after enough installs (no exact threshold published; days to weeks).
- **Tooling:** `signtool.exe` (legacy), `osslsigncode` (cross-platform), Azure Trusted Signing CLI. GitHub Actions has `azure/trusted-signing-action`.

#### macOS
- **Required:** Apple Developer Program membership ($99/yr).
- **Hardened runtime:** Mandatory for notarization since Jan 2020. Requires entitlements:
  - `com.apple.security.cs.allow-unsigned-executable-memory=true` (Python needs this for ctypes/cffi).
  - `com.apple.security.cs.disable-library-validation=true` if loading 3rd-party dylibs (curl_cffi will need this).
- **notarytool:** `xcrun notarytool submit app.zip --apple-id ... --team-id ... --password ... --wait`. Old `altool` removed Nov 2023. Auth via App Store Connect API key (recommended) or app-specific password.
- **Stapling:** `xcrun stapler staple App.app` after successful notarization (offline verification).
- **Deep signing required for Python apps:** All bundled .dylib/.so/Mach-O files must be individually signed. PyInstaller adds many — `codesign --deep --options runtime` is required (despite Apple's guidance against `--deep` in normal cases).
- **Open PyInstaller issues:** #8927 (PySide6 onedir notarization), #4629 (hardened runtime crashes). Workarounds exist but expect debugging.

#### Linux
- **No equivalent of Authenticode/Gatekeeper.** Trust is per-distro via repo signing keys.
- **AppImage:** Optional GPG signing via embedded signature; verifiable but no enforcement.
- **Flatpak/Snap:** Repo-level signing handled by Flathub/Snap Store.
- **.deb/.rpm:** GPG-sign packages and repos.
- **Verdict:** Sign if distributing through repos; otherwise low priority compared to Win/Mac.

### 2.3 Installer Creation

#### Windows
| Tool | License | Strength | Weakness |
|------|---------|----------|----------|
| **Inno Setup** | Free | Pascal scripting, readable, integrated 7-Zip LZMA compression, easiest learning curve | EXE-only output (no MSI) |
| **NSIS** | Free | Smallest installer overhead (~34KB), powerful plugins | Cryptic syntax, easy to write spaghetti |
| **WiX/MSI** | Free | Native Windows installer format, GPO/SCCM deployment | Complex XML, steep learning curve |
| **MSIX** | Free | Modern format, Win10/11 sandboxed, auto-cleanup | Limited reach (no Win7/8), no driver/service support, signing required |
| **Advanced Installer** | Paid | GUI builder, MSI/MSIX/EXE | Cost ($600+) |

**Recommendation for tiktokder:** Inno Setup. NSIS only if you need ultra-small installer overhead.

#### macOS
- **DMG** (most common): drag-to-Applications metaphor; built via `hdiutil` or `create-dmg`.
- **PKG**: scripted installer; needed for daemons, system-wide installs, or pre/post hooks.
- **App Store**: PKG-based, sandboxing rules — usually overkill for utilities.

**Recommendation:** DMG for tiktokder.

#### Linux
- **AppImage:** Single executable file, no install required. FUSE-mounted at runtime. **Fastest startup** of the three universal formats.
- **Flatpak:** Sandboxed, runtime-shared (smaller marginal disk cost), best for desktop discovery via Flathub. Slowest startup of the three.
- **Snap:** Auto-updates by default; Ubuntu-centric; controversial in non-Ubuntu communities. Slowest initial startup.
- **.deb / .rpm:** Native package manager integration; required for repo presence.

**Recommendation:** AppImage as the minimum; add Flathub if/when going broad.

### 2.4 Auto-Update Mechanisms

| Tool | Status | Notes |
|------|--------|-------|
| **tufup** | Active (2024-2026) | TUF-backed, PyInstaller-friendly, packager-agnostic, patch-based diffs. **Recommended.** |
| **PyUpdater** | **Archived** | No commits in 12+ months. Migrate off. |
| **Sparkle** | Active (macOS) | The macOS standard; usable from Python via pyobjc but adds Obj-C overhead. |
| **Squirrel.Windows** | Mostly stalled | .NET ecosystem; not Python-friendly. |
| **WinSparkle** | Active | C/C++ port of Sparkle for Windows. Embeddable but not native to Python. |
| **Custom GitHub Releases** | Most common in practice | App checks `https://api.github.com/repos/.../releases/latest`, verifies signature, downloads, restarts. Simple, reliable. |

**Verdict:** tufup if security is a priority (signed metadata, rollback protection); custom GH-Releases poller if simplicity wins.

### 2.5 Build Automation (CI/CD)

- **GitHub Actions matrix:** Standard pattern is `runs-on: [windows-latest, macos-14, ubuntu-22.04]` with `if:` conditionals per OS-specific step.
- **Secrets handling:**
  - Windows: `AZURE_TRUSTED_SIGNING_*` or imported PFX from base64 secret.
  - macOS: `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` (or App Store Connect API key as base64 P8); developer ID cert imported into temp keychain.
  - Linux: GPG key for AppImage/deb signing.
- **Reproducibility:** Pin Python version, pip-tools / uv lock, pin PyInstaller. Use lock files (requirements.lock or uv.lock) committed to repo.
- **Artifact strategy:** Upload signed binaries to GitHub Releases or S3; tufup ingestion can be a follow-up step.

---

## 3. Comparative Table

| Tool | Output | Startup (cold) | Bundle Size | AV FPs | Build Time | macOS Notarization | License | Verdict |
|------|--------|----------------|-------------|--------|------------|---------------------|---------|---------|
| **PyInstaller** | onedir/onefile | Onedir 0.5-2s, Onefile 3-10s | 100-180MB | High (notorious) | 30-90s | Works (painful) | GPL+exception | **Default** |
| **Nuitka** | standalone/onefile | Fastest (native) | 80-150MB | Low | 5-15min | Works (similar pain) | AGPL/Commercial | **Plan B for AV** |
| **cx_Freeze** | onedir | Reported fast | ~Similar to PyInstaller | Medium | 30-90s | Works | PSF | Niche |
| **Briefcase** | Native installers | Medium | Larger (full interpreter per app) | Low | 2-12min | Built-in | BSD-3 | If mobile too |
| **py2app** | .app bundle | Fast | 80-150MB | Low | 1-3min | Native fit | MIT | macOS-only niche |
| **PyOxidizer** | Single binary | Fast (in-memory imports) | 50-100MB | Low | Slow | Works | MPL-2 | **DEAD — avoid** |

---

## 4. Recommended Pipeline Per OS

### Windows (priority for tiktokder)
1. **Build:** PyInstaller onedir (current spec, but **disable UPX** to reduce AV false positives).
2. **Installer:** Inno Setup wraps the onedir into a single `Setup.exe` with shortcuts, uninstall registry, optional auto-launch.
3. **Sign:** Azure Artifact Signing ($10/mo) on the Setup.exe AND the inner TikTokDer.exe and TikTokDer-CLI.exe. Use `signtool` or the GH Action.
4. **Distribute:** GitHub Releases for hash-stable URLs; document SHA256 in release notes.
5. **Update:** tufup polling on app start, or simpler: app pings `https://api.github.com/repos/.../releases/latest` weekly, prompts user to download new installer.

### macOS
1. **Build:** PyInstaller onedir → `--osx-bundle-identifier`, produce .app.
2. **Sign:** `codesign --deep --options runtime --entitlements entitlements.plist --sign "Developer ID Application: ..."` over the .app.
3. **Notarize:** Zip → `xcrun notarytool submit ... --wait` → `xcrun stapler staple App.app`.
4. **Package:** `create-dmg` for branded .dmg with drag-to-Applications layout. Sign + notarize the .dmg too.
5. **Distribute:** GitHub Releases. Universal2 binary (x86_64+arm64) preferred.
6. **Update:** Same as Windows; tufup or custom poller.

### Linux
1. **Build:** PyInstaller onedir on ubuntu-22.04 (oldest reasonable glibc for compat).
2. **Package primary:** AppImage via `linuxdeploy` or `appimagetool`. Single file, no install, FUSE-mounted at runtime.
3. **Optional secondary:** Flatpak manifest + submission to Flathub. Higher friction (sandboxing rules) but increases discoverability.
4. **Sign:** Optional GPG signature on AppImage.
5. **Update:** AppImageUpdate tool consumes AppImage's update info; or tufup.

---

## 5. Apply to Tiktokder: Concrete Next Steps

**Current state (audited from `tiktokder.spec`, `build.py`, `requirements.txt`):**
- PyInstaller 6.x, onedir (good).
- Dual entry points: GUI (no console) + CLI (console). Correct, though COLLECT bundles both into one folder — keep this.
- Hidden imports for yt_dlp submodules and curl_cffi (correct — both have dynamic loading).
- UPX enabled (`upx=True`) on both EXEs and COLLECT — **change this.**
- Excludes: playwright, pytest, tkinter, unittest. Correct.
- Output: zip of dist folder. Portable, no installer.

**Action items (ranked by ROI):**

1. **Disable UPX in `tiktokder.spec`.** UPX-compressed binaries are flagged by ~30-50% more AV engines. Bundle size grows ~15-25% but installs and runs unchanged.
   - Change `upx=True` → `upx=False` in both `EXE()` calls and `COLLECT()`.

2. **Add an Inno Setup script.** Replace/supplement the zip with a real installer. Users get Start Menu shortcut, uninstaller, and Windows treats it as a proper install — boosts SmartScreen reputation accumulation. ~50 lines of Pascal script.

3. **Sign with Azure Artifact Signing.** $10/mo. Sign both inner exes + the Setup.exe. Massively reduces Defender blocks and SmartScreen warnings.

4. **Add GitHub Actions matrix workflow.** windows-latest only first (current platform), then expand to macos-14 and ubuntu-22.04. Automates builds on tag push.

5. **Implement update check.** Start with simple GitHub Releases poller (60 LOC). Migrate to tufup if the user base + security needs grow.

6. **Address curl_cffi on macOS later.** It loads native libs that need `disable-library-validation` entitlement. Not urgent until macOS becomes a target.

7. **Skip:** Nuitka migration (build time pain not worth it yet), Briefcase (no mobile need), MSIX (no consumer benefit), Flatpak (premature).

---

## 6. Unresolved Questions

1. **Who is the user base?** Windows-only or actually multi-OS? If 95% Windows, defer macOS/Linux pipelines until v2.0.
2. **Is the user a US/Canada-based individual or organization?** Determines Azure Artifact Signing eligibility (currently US/CA individuals; EU/UK orgs).
3. **Distribution channel?** Direct download from a website, GitHub Releases only, or eventually Microsoft Store / Mac App Store? The Store paths add sandboxing constraints (yt-dlp may struggle).
4. **Update cadence?** If pushing weekly, tufup's patch-based diffs save bandwidth. If quarterly, simple full-installer download is fine.
5. **Threat model for IP protection?** Standard Nuitka does NOT obfuscate. If hiding business logic matters, Nuitka Commercial or PyArmor is required — but for tiktokder this seems irrelevant.
6. **Will `playwright` ever ship?** Currently excluded. If channel browsing needs it, accept +200MB Chromium download or lazy-fetch Chromium on first run.
7. **macOS arch strategy?** Universal2 (x86+arm64) or arm64-only? Universal2 doubles binary size; arm64-only excludes Intel Macs (still ~30% installed base in 2026).

---

**Status:** DONE
**Summary:** Comprehensive packaging research delivered: PyInstaller remains default, Nuitka is best AV fallback, PyOxidizer/PyUpdater are dead. Recommended Windows-first pipeline: PyInstaller onedir (UPX off) → Inno Setup → Azure Artifact Signing → GH Releases → tufup. Concrete tiktokder action items prioritized.

---

## Sources

- [Compilation vs Bundling: Nuitka vs PyInstaller — krrt7](https://krrt7.dev/en/blog/nuitka-vs-pyinstaller)
- [2026 Showdown: PyInstaller vs cx_Freeze vs Nuitka — AhmedSyntax](https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/)
- [PyInstaller issue #6754 — onefile AV false positives](https://github.com/pyinstaller/pyinstaller/issues/6754)
- [PyInstaller issue #8164 — VirusTotal regressions post-5.13.2](https://github.com/pyinstaller/pyinstaller/issues/8164)
- [PyInstaller AV false positive guide — pythonguis](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/)
- [Qt for Python: Nuitka deployment](https://doc.qt.io/qtforpython-6/deployment/deployment-nuitka.html)
- [Nuitka Release 2.8 changelog](https://nuitka.net/posts/nuitka-release-28.html)
- [Nuitka Commercial license terms](https://nuitka.net/doc/commercial-license.html)
- [PyInstaller issue #4629 — macOS hardened runtime](https://github.com/pyinstaller/pyinstaller/issues/4629)
- [PyInstaller issue #8927 — PySide6 notarization onedir](https://github.com/pyinstaller/pyinstaller/issues/8927)
- [Signing/notarizing a Python macOS UI app — haim.dev](https://haim.dev/posts/2020-08-08-python-macos-app)
- [Apple notarization changes Nov 2023 — altool retirement](https://developer.apple.com/news/upcoming-requirements/?id=11012023a)
- [SmartScreen reputation for Windows app developers — Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [SSL.com: EV vs OV code signing](https://www.ssl.com/faqs/which-code-signing-certificate-do-i-need-ev-ov/)
- [Authenticode in 2025 — Azure Trusted Signing](https://textslashplain.com/2025/03/12/authenticode-in-2025-azure-trusted-signing/)
- [Azure Artifact Signing pricing](https://azure.microsoft.com/en-us/pricing/details/artifact-signing/)
- [Trusted Signing public preview for individual developers](https://techcommunity.microsoft.com/blog/microsoft-security-blog/trusted-signing-is-now-open-for-individual-developers-to-sign-up-in-public-previ/4273554)
- [BeeWare November 2025 status update](https://beeware.org/news/buzz/november-2025-status-update/)
- [BeeWare Briefcase docs](https://briefcase.beeware.org/en/stable/)
- [PyOxidizer issue #741 — project status update (abandoned)](https://github.com/indygreg/PyOxidizer/issues/741)
- [Anki issue #3081 — PyOxidizer migration](https://github.com/ankitects/anki/issues/3081)
- [PyUpdater PyPI listing — archived](https://pypi.org/project/PyUpdater/)
- [tufup — TUF-backed update framework](https://github.com/dennisvang/tufup)
- [tufup-example with PyInstaller workflow](https://github.com/dennisvang/tufup-example)
- [Flatpak vs Snap vs AppImage 2025 — sudostation](https://www.sudostation.org/post/flatpak-vs-snap-vs-appimage-which-one-should-you-choose-in-2025)
- [Flatpak vs Snap vs AppImage compared — phoenixnap](https://phoenixnap.com/kb/flatpak-vs-snap-vs-appimage)
- [NSIS vs WiX vs Inno Setup 2026 guide](https://copyprogramming.com/howto/nsis-vs-wix-vs-anyother-installation-package)
- [yt-dlp PyInstaller bundle workflow](https://github.com/yt-dlp/yt-dlp)
- [yt-dlp/FFmpeg-Builds — patched ffmpeg builds](https://github.com/yt-dlp/FFmpeg-Builds)
- [GitHub Actions matrix builds — community guide](https://github.com/orgs/community/discussions/132605)
- [cross-platform CI/CD example — Zettlr](https://www.zettlr.com/post/continuous-cross-platform-deployment-github-actions)
