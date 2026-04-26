# Modern Python Desktop GUI — Research Summary

**Synthesized by:** team-lead (modern-python-gui)
**Date:** 2026-04-26
**Sources:**
- `researcher-1-260426-1408-native-python-gui-frameworks.md` (PySide6/PyQt/Tk/Kivy/DPG/wx/Toga)
- `researcher-2-260426-1408-web-hybrid-gui-frameworks.md` (Flet/NiceGUI/PyWebView/Eel/Reflex/Trame/Anvil)
- `researcher-3-260426-1408-packaging-and-distribution.md` (PyInstaller/Nuitka/cx_Freeze/Briefcase/signing/installers/auto-update)
- `researcher-4-260426-1410-design-and-ux-patterns.md` (Fluent/M3/HIG, theming libs, a11y, icons, references)

---

## 1. Executive Summary

- **There are three credible 2026 paths** to a modern-looking Python desktop app: **PySide6 + modern theme** (most polish-per-effort, native), **NiceGUI native mode** (best polish-per-LOC, web-quality UI), **Flet** (cross-platform incl. mobile, prettiest visuals at 80–300 MB cost). Everything else is niche, dated, or dead.
- **Eel is dead** (repo archived 2025-06-22). **PyOxidizer is dead** (no release since Jan 2023). **PyUpdater is archived**. Drop these from any plan.
- **For tiktokder specifically: stay on PySide6.** All four researchers converge: project is already on it, LGPL-safe, threading model fits the existing `ThreadPoolExecutor`, table/list widgets fit the download UI, packaging story is mature. No framework change justified.
- **Biggest single-day modernization win: PyQtDarkTheme + qtawesome + darkdetect.listener** (all MIT). Adds dark/light theme, OS follow, and 1500+ icons for ~40 KB of dependencies. Largest visual delta for the least code.
- **Tier-3 option: QFluentWidgets** for full Win11 Fluent 2 (Mica/Acrylic, NavigationView, InfoBar, ProgressRing). GPLv3 license is the gating decision — fine if project stays GPL-compatible, blocking otherwise.
- **Packaging upgrade: disable UPX in `tiktokder.spec`.** UPX-compressed PyInstaller output is flagged by ~30–50% more AV engines. ~15–25% larger binary, much fewer Defender problems.
- **Code signing on Windows: Azure Artifact Signing ($10/mo)** is now the cheapest credible path. EV cert advantage over OV is gone (Microsoft policy change).
- **Auto-update: tufup** is the only actively maintained Python-native option in 2026; otherwise roll a simple GitHub Releases poller (~60 LOC).
- **Reference aesthetic: Motrix** (dark-first, sidebar nav, ring progress, accent green) is the closest aesthetic target for tiktokder. Linear/Raycast/Warp are the "pro tool" benchmark for keyboard-first dense UIs.

---

## 2. Comparative Matrix — Frameworks

| Framework | License | Renderer | Bundle | Cold start | UI polish (default) | UI polish (themed) | a11y | Mobile | Best for |
|---|---|---|---|---|---|---|---|---|---|
| **PySide6** | LGPL/Commercial | Qt-styled | 100–180 MB | 0.5–2 s | ★★☆ | ★★★★ (with Fluent/Material/Dark) | Decent (UIA/AT-SPI) | No | Native desktop, threaded apps, downloader-shape |
| PyQt6 | GPL/Commercial | =PySide6 | =PySide6 | =PySide6 | =PySide6 | =PySide6 | =PySide6 | No | Same as PySide6 but GPL — usually no reason to pick over PySide6 |
| **NiceGUI** | MIT | Vue+Quasar+pywebview | 40–80 MB | 1–3 s | ★★★★ (Material out of the box) | ★★★★ | Best (browser a11y) | No | Polished desktop tool fastest, Python-only team |
| **Flet** | Apache-2.0 | Flutter engine | 80–300 MB | 2–20 s | ★★★★★ | ★★★★★ | Partial | **Yes** | Beautiful cross-platform incl. mobile/web |
| PyWebView 6 | BSD-3 | System webview | <10 MB | <0.5 s | depends | depends | Best | No | Lightest binary, custom HTML/CSS/JS frontend |
| Tkinter+sv-ttk/ttkbootstrap | stdlib + MIT | ttk | small | fast | ★☆ | ★★★ | **Near-zero on Windows** | No | Quick small utility, not a11y-sensitive |
| CustomTkinter | MIT | Custom canvas | small | fast | ★★★ | ★★★ | None | No | Modern-ish Tk without Qt |
| wxPython | wxBSD | True native | 50–100 MB | fast | ★★★ (native) | ★★★ | Native | No | Pure-native at all costs |
| Dear PyGui | MIT | GPU/ImGui | small | fast | ★★ (game-style) | ★★ | None | No | Data viz / plots / dashboards |
| Kivy | MIT | OpenGL | medium | fast | ★★ | ★★ | None | Yes (touch) | Mobile-first, not desktop |
| BeeWare Toga 0.5.x | BSD | True native | medium | fast | ★★★ | ★★★ | Native | Yes | Cross-platform incl. mobile, **pre-production for polished Windows** |
| Eel | MIT | Chrome --app | small | fast | ★★ | ★★ | Web | No | **DEAD — do not adopt** |
| Reflex | Apache-2.0 | React (web) | n/a | n/a | n/a desktop | n/a desktop | Web | No | Web SPAs only |
| Trame | Apache-2.0 | Vue+VTK | varies | varies | viz-focused | viz-focused | Web | No | Scientific viz |
| Streamlit / Gradio | Apache-2.0 | Web | 100+ MB (wrapped) | medium | dashboard-shape | dashboard-shape | Web | No | Dashboards, ML demos |

---

## 3. Comparative Matrix — Packaging / Distribution

| Tool | Output | Cold start | Bundle size | AV false positives | Build time | macOS notarization | License | Verdict |
|------|--------|------------|-------------|--------------------|------------|--------------------|---------|---------|
| **PyInstaller** | onedir / onefile | 0.5–2 s / 3–10 s | 100–180 MB | High (notorious) | 30–90 s | Works (painful) | GPL+exception | **Default** |
| **Nuitka** | standalone / onefile | Fastest (native code) | 80–150 MB | Low | 5–15 min | Works (similar pain) | AGPL / Commercial | **Plan B for AV** |
| cx_Freeze | onedir | Reportedly fast | similar | Medium | 30–90 s | Works | PSF | Niche |
| Briefcase | Native installers (.msi/.dmg/.deb/.AppImage/iOS/Android) | Medium | Larger (full interpreter per app) | Low | 2–12 min | Built-in | BSD-3 | If mobile from day one |
| py2app | .app bundle (macOS) | Fast | 80–150 MB | Low | 1–3 min | Native fit | MIT | macOS-only fallback |
| PyOxidizer | Single binary | Fast | 50–100 MB | Low | Slow | Works | MPL-2 | **DEAD — avoid** |
| Shiv / PEX | .pyz / .pex | Requires preinstalled Python | small | n/a | fast | n/a | various | Not viable for GUI |

---

## 4. Recommendations by Use-Case

| Use case | Pick | Why |
|---|---|---|
| **Quick polished desktop tool**, Python-only team, list/forms/progress UI | **NiceGUI native mode** | Quasar Material 3 + Tailwind 4 free; FastAPI fits async Python; MIT; budget ~½ day for PyInstaller paper cuts |
| **Mature native desktop**, threaded workers, table/grid heavy | **PySide6 + PyQtDarkTheme/QFluentWidgets** | LGPL-safe; QThreadPool+signals; QTableView; mature packaging; best long-term ceiling |
| **Cross-platform incl. mobile/iOS** | **Flet** | Only option that targets desktop+iOS+Android+web from one Python codebase; accept 80–300 MB |
| **Lightest possible binary**, custom design, comfortable with HTML/CSS/JS | **PyWebView 6** | Sub-10 MB, <0.5 s start, BSD, system webview — but you author the entire frontend |
| **Data viz / plots / 1M+ points** | **Dear PyGui** | GPU-rendered ImGui; non-native look acceptable for tooling |
| **Truly native widgets at all costs** | **wxPython** | Real OS widgets; trade-off: weaker dark mode + smaller community than Qt |
| **Small utility, ship fast, no a11y need** | **Tkinter + sv-ttk** or **CustomTkinter** | Stdlib + tiny dep; modern enough |
| **Anything** | **NOT Eel** (archived), **NOT Reflex** (web only for desktop), **NOT PyOxidizer** (dead), **NOT PyUpdater** (archived) |

---

## 5. Modern Look-and-Feel Checklist (apply to any framework)

20-item checklist, ordered by ROI. Each is a binary check.

**Foundation (must-have):**
1. Single accent color, used sparingly (CTAs, progress, focus).
2. Semantic color tokens (`bg.canvas`, `text.primary`, `accent.default`, `state.success/warning/error/info`) — not raw hex in widgets.
3. Dark + light theme, **system-driven by default** with manual override; live OS-switch via `darkdetect.listener`.
4. One typeface for UI: Segoe UI Variable on Win11, SF Pro on macOS, Inter as cross-platform fallback.
5. Type scale of 6 sizes max — 11/12/13/14/16/20/28; line-height 1.4–1.5 body, 1.2 headings.
6. 4/8 spacing grid: padding/margins from {4, 8, 12, 16, 24, 32, 48}.
7. Consistent corner radius: 4 small / 8 default / 12 large.
8. Focus ring on every interactive element — 2px outset accent, 2px offset.
9. Hover + pressed + disabled states on every button.
10. Iconography from one set at one weight (Lucide line / Phosphor regular / Material Symbols rounded).

**Polish (high ROI):**
11. InfoBar/toast for transient feedback (not `QMessageBox`).
12. Empty state when list is empty (icon + helpful text + primary CTA).
13. Skeleton rows during async loading (animated wave, not pulse).
14. Differentiated progress affordances (indeterminate ring → determinate bar → checkmark / error).
15. Micro-interactions ≤200 ms (button press, row insert, theme switch); avoid bounce/elastic.
16. Mica/Acrylic on Windows 11 (via QFluentWidgets `MicaWindow`) — instantly reads "modern Win11".
17. Keyboard shortcuts with visible hints in tooltips/menus.
18. System tray icon with mini-menu (pause/resume/show/quit) for download-manager-shape apps.
19. Drag-and-drop of files/URLs onto window with overlay drop zone.
20. Window state persistence (size/position/splitters) via `QSettings`.

**Anti-patterns to avoid:**
- Tkinter default look; oversized buttons (>40 px); inconsistent padding; missing focus ring + hover state; light-only theme; `QMessageBox.warning` for every soft error; emoji in toolbar/status; mixing icon sets.

---

## 6. Theming Libraries (top 3 per framework family)

**Qt (PySide6/PyQt6):**
1. **QFluentWidgets** (GPLv3 / commercial) — full Win11 Fluent 2 incl. Mica/Acrylic, NavigationView, InfoBar, ProgressRing, SwitchButton, TeachingTip. Best polish, license is the gating call.
2. **PyQtDarkTheme** (MIT) — flat dark/light, "VS Code-ish", one-liner `qdarktheme.setup_theme("auto")` follows OS. Top pick for permissive license.
3. **qt-material** (BSD) — Material 2 vibe, runtime theme switch, density scaling. Caveat: M2 not M3, not native-feeling on Win11.

Honorable mentions: BreezeStyleSheets (KDE Breeze, Linux-first), QDarkStyle (older, superseded by PyQtDarkTheme).

Icon companion: **qtawesome** — bundles Material Design Icons (mdi6, ~7000), Phosphor (ph), Font Awesome 6, Codicons, Remix. 5-minute icon pipeline.

**Tkinter:**
1. **CustomTkinter** (MIT) — most polished modern Tk. But: not real ttk, no a11y, custom widgets so DPI/edge-cases bite.
2. **Sun Valley TTK** (MIT) — best-looking pure-ttk theme, Win11 Sun Valley aesthetic.
3. **ttkbootstrap** (MIT) — Bootstrap-inspired, 20+ themes, extra widgets (Meter/DateEntry/Floodgauge).

(Disqualified for any a11y-sensitive use — Tkinter on Windows has near-zero screen-reader integration.)

**Web-hybrid:**
1. **NiceGUI** — Quasar/Vue → Material Design free.
2. **Flet** — Flutter-rendered Material 3 + Cupertino built-in.
3. **PyWebView + Tailwind/shadcn/HeadlessUI** — bring-your-own, max flexibility.

---

## 7. Recommended Pipeline (cross-platform desktop, 2026)

**Per-OS pipeline:**

- **Windows:**
  PyInstaller onedir (UPX off) → **Inno Setup** wraps to single Setup.exe → **Azure Artifact Signing** ($10/mo) on inner exes + Setup.exe → GitHub Releases for hash-stable URLs → tufup or simple GH-Releases poller for updates.

- **macOS:**
  PyInstaller onedir → `codesign --deep --options runtime --entitlements …` (entitlements include `com.apple.security.cs.allow-unsigned-executable-memory=true` and, if loading 3rd-party dylibs like curl_cffi, `com.apple.security.cs.disable-library-validation=true`) → `xcrun notarytool submit … --wait` → `xcrun stapler staple` → `create-dmg` for branded DMG (sign + notarize the DMG too) → GitHub Releases. Universal2 (x86_64+arm64) preferred while ~30% of installed Macs are Intel.

- **Linux:**
  PyInstaller onedir on ubuntu-22.04 (oldest reasonable glibc for compatibility) → AppImage via `linuxdeploy` / `appimagetool` (single file, no install) → optional Flatpak manifest + Flathub submission for discoverability → optional GPG signature on AppImage.

**CI:** GitHub Actions matrix `[windows-latest, macos-14, ubuntu-22.04]` with platform-specific signing secrets. Pin Python version + pip-tools/uv lock files committed to repo.

---

## 8. Apply to tiktokder — Concrete Roadmap

The project is **PySide6 + Rich CLI + PyInstaller**, currently ships a Windows zip of the dist folder. Applying the synthesized recommendations:

### Tier 1 — High ROI, ~1–2 days

1. **`tiktokder.spec`: set `upx=False`** in both `EXE()` calls and `COLLECT()`. Reduces AV false-positives 30–50%; bundle grows ~15–25%.
2. **Add `pyqtdarktheme`, `qtawesome`, `darkdetect`** (all MIT). One-line `qdarktheme.setup_theme("auto")` + `darkdetect.listener(callback)` for live OS-follow theme. Standardize all icons to `mdi6.*` or `ph.*` via qtawesome.
3. **Define semantic color tokens** (14 entries: `bg.*`, `border.*`, `text.*`, `accent.*`, `state.*`) mapped twice (light/dark) in a `gui/tokens.py` module. Refactor any hardcoded hex in `gui/*.py` to read from the token map.
4. **Standardize spacing** to `{4, 8, 12, 16, 24}` via a `gui/spacing.py` constants module. Audit `setContentsMargins`/`setSpacing` calls.
5. **Add `Settings → Appearance` panel** with `System / Light / Dark` segmented control, persisted via `QSettings`.

### Tier 2 — Polish, ~2–4 days

6. Replace `QMessageBox` toasts with **InfoBar** (custom QFrame slide-in or QFluentWidgets if license permits).
7. **Empty state** in download table (icon + "Paste a URL or drop a .txt file to begin" + primary CTA).
8. **Skeleton rows** during channel/profile resolve (yt-dlp 1–5 s), animated gradient sweep.
9. **Focus rings** explicitly via QSS — `*:focus { outline: 2px solid <accent>; outline-offset: 2px; }`.
10. **System tray icon** with mini-menu (pause/resume/show/quit) — opt-in via Settings.
11. **Drag-and-drop** of URLs and `.txt` files onto window with overlay drop zone.
12. **Persist window geometry, splitters, last-used output dir** via `QSettings`.

### Tier 3 — Bigger calls (require product decisions)

13. **QFluentWidgets migration** for full Win11 Fluent 2 (Mica window, NavigationView sidebar, ProgressRing). GPLv3 — gating decision on license posture.
14. **Sidebar nav (Home / Channel / Settings)** replacing tabs, frameless Mica title bar — Motrix-inspired layout (see researcher-4 §7 sketch).
15. **Brand accent**: indigo `#4F46E5` (neutral, "professional dev tool", ages well, no platform IP overtones) vs TikTok pink `#FE2C55` (positioning question).

### Distribution upgrades (parallel track)

16. **Inno Setup script** to wrap dist folder into a real installer with Start Menu shortcut and uninstaller — boosts SmartScreen reputation accumulation.
17. **Azure Artifact Signing** ($10/mo) for both inner exes + Setup.exe.
18. **GitHub Actions matrix workflow** (windows-latest first, expand to macos-14 + ubuntu-22.04 later).
19. **Update checker** — start with simple GitHub Releases poller (~60 LOC); migrate to **tufup** if security needs grow.

### Skip / defer

- **Nuitka migration** — not justified yet; revisit only if AV false-positives persist after UPX-off + signing.
- **Briefcase** — overkill, no mobile need.
- **MSIX** — no Win10/Win11-only consumer benefit for a tool with no driver/service/sandboxing needs.
- **Flatpak** — premature until Linux user base materializes.
- **Framework swap to Flet/NiceGUI** — current PySide6 ceiling is high enough; theming + UX patches deliver the visual delta without a rewrite.

---

## 9. Reference Apps to Study

**Direct genre references:**
- **Motrix** (Electron, MIT, dark-first, sidebar nav, card-style task list with ring progress, accent green) — closest aesthetic target for tiktokder.
- **Free Download Manager 6.x** — modern but information-dense; good study for download-detail panel.
- **Ninja Download Manager** — clean minimum-viable polished.

**Anti-references:**
- **JDownloader 2** — Java Swing, capable but visually dated.
- **IDM (classic)** — Windows 9x toolbars; don't.

**"This is what modern feels like":**
- **Linear**, **Raycast**, **Warp**, **Arc Browser**, **GitHub Desktop**.

**Python ecosystem look-alikes:**
- **Spyder IDE** — qtawesome + Qt, decent dense Qt theming reference.
- **Tarekuzjaman0/TikTok-Downloader-GUI** (ttkbootstrap) — illustrates the ceiling of Tkinter polish (mediocre vs Motrix); confirms PySide6 was the right pick.

---

## 10. Unresolved Questions

These need product/scope answers before locking in Tier 3 decisions:

1. **License posture** — GPLv3-compatible, MIT-friendly, or commercial? Determines QFluentWidgets vs PyQtDarkTheme.
2. **Mobile target ever?** If yes → Flet becomes the only option and PySide6 hits a ceiling; if no → stay PySide6.
3. **OS priority** — Windows-only or actually multi-OS? If 95% Windows, defer macOS/Linux pipelines until v2.0.
4. **Brand accent** — TikTok pink (`#FE2C55`, fan-tool positioning) vs neutral indigo (`#4F46E5`, professional-tool positioning). Product owner call.
5. **Window chrome** — frameless+Mica (Win11 polish, Windows-only) vs native title bar (cross-platform consistency)?
6. **Sidebar nav vs tabs** — reading current `gui/main_window.py` not in scope here; refactor scope depends on existing layout.
7. **Min Qt version floor** — Mica APIs and CSS `outline` need Qt 6.5+; what is the current minimum?
8. **A11y target tier** — WCAG AA, AAA, or best-effort? Determines QAccessible work depth.
9. **Localization roadmap** — Latin-only or Vietnamese/CJK target market? Inter has good Vietnamese coverage; Segoe UI Variable wins on Windows.
10. **Code-signing eligibility** — US/Canada-based individual or organization? Determines Azure Artifact Signing path.
11. **Distribution channel** — direct download from website, GitHub Releases only, or eventually Microsoft Store / Mac App Store? Store paths add sandboxing constraints (yt-dlp may struggle).
12. **Update cadence** — weekly (tufup patches save bandwidth) or quarterly (full installer fine)?
13. **Antivirus / firewall behaviour** of NiceGUI's localhost socket on locked-down corporate Windows — not validated; relevant only if NiceGUI is reconsidered.
14. **Threat model for IP protection** — standard Nuitka does NOT obfuscate; Nuitka Commercial or PyArmor would be required if hiding business logic ever matters.
15. **macOS arch strategy** — Universal2 (x86+arm64) or arm64-only? Doubles binary size vs excludes Intel Macs (~30% installed base).

---

**Status:** DONE
**Summary:** 4-researcher synthesis. Recommendation for tiktokder: stay PySide6, modernize via PyQtDarkTheme + qtawesome + darkdetect (MIT, Tier-1, ~1–2 days), apply 20-item look-and-feel checklist, and upgrade packaging by disabling UPX + adding Inno Setup + Azure Artifact Signing. QFluentWidgets is the Tier-3 lever for full Win11 Fluent feel pending license decision. Skip Eel (dead), Reflex (web-only), PyOxidizer (dead), PyUpdater (archived).
