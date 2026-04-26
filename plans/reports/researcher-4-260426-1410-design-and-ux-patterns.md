---
title: Modern UX/UI Design Patterns, Theming, Accessibility for Python Desktop Apps
researcher: researcher-4
date: 2026-04-26
slug: design-and-ux-patterns
project: tiktokder
status: DONE
---

# Researcher-4: Modern UX/UI for Python Desktop Apps (2026)

Mission: how to make a Python desktop app actually look and feel modern, applied to **tiktokder** (PySide6 + CLI, batch TikTok/FB downloader).

---

## 1. Executive Summary

- **Stack already favorable.** tiktokder is on PySide6 — Qt is the only Python stack with a usable accessibility story (QAccessible/UIA), real native feel on Win11, and high-quality theming libs. Don't switch.
- **Drop-in modernization #1: QFluentWidgets.** Native Win11 Fluent 2 look (Mica/Acrylic, `FluentWindow`, `InfoBar`, `ProgressRing`, `SwitchButton`, `TeachingTip`) — biggest visual delta for least code. GPLv3 / commercial — fine for current MIT-style hobby project but flag if relicensing.
- **Drop-in modernization #2: PyQtDarkTheme + qtawesome.** If GPL is a blocker, this combo (MIT) gives a flat dark/light theme, system follow, and 6 icon font packs (Material Symbols, Lucide via SVG, Phosphor, Codicons) for ~40 KB.
- **Tokens + system follow are non-negotiable in 2026.** Dark mode must follow OS via `darkdetect.listener`; colors should be semantic tokens (`bg.surface`, `text.primary`, `state.success`) not hex literals; spacing on a 4/8 grid; typography on a fixed type scale.
- **Skeleton loaders + empty states + InfoBars.** Replace generic spinners with skeleton rows in the download table; show a friendly empty state before the first URL; surface errors as toasts (`InfoBar`) not modal `QMessageBox`.
- **Reference apps for tiktokder direction.** Motrix (Electron, dark-first, card layout, accent green) is the closest aesthetic target; Linear/Raycast/Warp are the "pro tool" benchmark for keyboard-first dense UIs; JDownloader and FDM are *anti-references* (cluttered, dated).
- **Accessibility tier list:** Qt = decent (free), Web-hybrid = full (Vue/Quasar inherits browser a11y), Tkinter/CustomTkinter = near-zero on Windows. Tkinter is disqualified for any app shipping outside hobby use.
- **Cheap design lift:** Untitled UI (free Figma kit) for tokens/components reference, Lucide for icons, Inter or Geist for typography, Coolors/Realtime Colors for accent picks.

---

## 2. Modern Look-and-Feel Checklist (apply to tiktokder)

20 items, ordered by ROI. Each is a binary check.

### Foundation (must-have)

1. **Single accent color**, used sparingly (CTAs, progress, focus). Pick one — pink (#FE2C55, TikTok-coded) or neutral indigo (safer/less platform-licensed feel).
2. **Semantic color tokens** (not raw hex in widgets): `bg.canvas`, `bg.surface`, `bg.subtle`, `border.default`, `text.primary`, `text.secondary`, `text.muted`, `accent.default`, `state.success/warning/error/info`.
3. **Dark + light theme**, **system-driven** by default with manual override (`System / Light / Dark` segmented control in Settings). Use `darkdetect.listener`.
4. **One typeface** for UI: Segoe UI Variable on Win11, SF Pro on macOS, Inter as cross-platform fallback. No mixing fonts.
5. **Type scale**: 6 sizes max — 11/12/13/14/16/20 (caption/body-sm/body/body-lg/h2/h1). Line-height 1.4–1.5 for body, 1.2 for headings.
6. **4/8 spacing grid**: padding/margins from {4, 8, 12, 16, 24, 32, 48}. Forbid arbitrary 7px / 13px values.
7. **Consistent corner radius**: 4px small (chips/inputs), 8px default (cards/buttons), 12px large (windows/modals). Pick once, apply everywhere.
8. **Focus ring on every interactive element** — 2px outset accent, 2px offset. Critical for keyboard users and a11y.
9. **Hover + pressed + disabled states** on every button. Tkinter default = no hover state = looks dead.
10. **Iconography from one set** at one weight. Lucide (line) or Phosphor Regular or Material Symbols Rounded — pick one, stick with it. Don't mix Font Awesome solid with Lucide outline.

### Polish (high ROI)

11. **InfoBar/toast** for transient feedback (download complete, error retrying) — not `QMessageBox`.
12. **Empty state** when download list is empty: friendly illustration/icon + "Paste a URL or drop a .txt file to begin" + primary CTA.
13. **Skeleton rows** in download table while resolving channel/profile metadata (yt-dlp can take 1–5s) — animated wave, not pulse.
14. **Progress affordances**: indeterminate `ProgressRing` for "resolving", determinate bar for "downloading", checkmark for "done", red exclamation for "error".
15. **Micro-interactions** ≤200ms (button press, row insert, theme switch fade). Use `QPropertyAnimation` or QFluentWidgets built-ins. Avoid bounce/elastic — feels childish in pro tools.
16. **Mica/Acrylic** on Windows 11 (via QFluentWidgets `MicaWindow` or `BlurWindow`) — instantly reads as "modern Win11 app".
17. **Keyboard shortcuts** with visible hints in tooltips/menus: `Ctrl+V` paste-and-add, `Ctrl+Enter` start, `Del` remove row, `Ctrl+,` settings, `Ctrl+L` focus URL field.
18. **System tray icon** with mini-menu (pause all / resume / show window / quit) — table-stakes for download managers.
19. **Drag-and-drop** of URLs and `.txt` files onto the window. Visual drop zone overlay on dragenter.
20. **Window state persistence** (size, position, splitter ratios) — `QSettings`. Trivial to add, screams "polished" when missed.

### Anti-patterns — explicitly avoid

- Tkinter default theme (gray rectangles, beveled buttons) — ship-killer.
- Oversized buttons (>40px height for default) — looks like a kids' learning app.
- Inconsistent padding (some 10px, some 14px) — root cause of "this looks AI-generated".
- No focus ring + no hover state — looks broken.
- Light theme only — failing dark mode in 2026 is a tell that the app is unmaintained.
- `QMessageBox.warning` for every soft error — use inline validation + InfoBar.
- Emoji in toolbar/status text — reads as amateur in a desktop app context.
- Three different icon sets in one screen.

---

## 3. Per-Framework Theming Options (top 3 each)

### Qt family (PySide6/PyQt6) — recommended for tiktokder

| Lib | License | Look | Verdict |
|---|---|---|---|
| **QFluentWidgets** ([repo](https://github.com/zhiyiYo/PyQt-Fluent-Widgets), [site](https://qfluentwidgets.com/)) | GPLv3 + commercial | Win11 Fluent 2 (Mica/Acrylic, NavigationView, InfoBar, etc.) | **Top pick for Win11-first apps.** Most components, best polish. License cost: app must be GPL-compatible or buy commercial. |
| **PyQtDarkTheme** ([repo](https://github.com/5yutan5/PyQtDarkTheme), [PyPI](https://pypi.org/project/pyqtdarktheme/)) | MIT | Flat dark/light, "VS Code-ish" | **Top pick for permissive license.** One-liner `qdarktheme.setup_theme("auto")` follows OS. No custom widgets — just stylesheet + palette. Lightweight. |
| **qt-material** ([repo](https://github.com/UN-GCPDS/qt-material), [docs](https://qt-material.readthedocs.io/)) | BSD | Material 2 (not 3) | Material *vibe*, runtime theme switch, density scaling. Caveat: not Material 3, not native-feeling on Win11. |

Honorable mention: **BreezeStyleSheets** ([repo](https://github.com/Alexhuszagh/BreezeStyleSheets)) — KDE Breeze look, good for Linux-first, generated from theme files. **QDarkStyle** is older and largely superseded by PyQtDarkTheme.

Icon companion: **qtawesome** ([repo](https://github.com/spyder-ide/qtawesome)) — Material Design Icons (mdi6), Phosphor (ph), Font Awesome 6 (fa6), Codicons, Remix. Solves icons in 5 minutes for any Qt app.

### Tkinter family — viable only if Qt is forbidden

| Lib | License | Look | Verdict |
|---|---|---|---|
| **CustomTkinter** ([docs](https://customtkinter.tomschimansky.com/)) | MIT | Custom widget set, rounded, dark/light | Most polished modern Tkinter. But: not real ttk, no a11y, custom widgets so DPI/edge-cases bite. |
| **Sun Valley TTK** ([repo](https://github.com/rdbende/Sun-Valley-ttk-theme)) | MIT | Win11 Sun Valley | Best-looking pure-ttk theme. Limited to widgets ttk supports. |
| **ttkbootstrap** ([repo](https://github.com/israel-dryer/ttkbootstrap), [docs](https://ttkbootstrap.readthedocs.io/)) | MIT | Bootstrap-inspired, 20+ themes | Best ecosystem (Meter, DateEntry, Floodgauge widgets). Bootstrap aesthetic feels "web 2018" to some. |

Reality: even with these, Tkinter on Windows has near-zero screen-reader integration ([tkinter-discuss thread](https://mail.python.org/pipermail/tkinter-discuss/2013-September/003480.html)). Disqualified for any app that needs a11y.

### Web-hybrid family

| Framework | Design system | Verdict |
|---|---|---|
| **NiceGUI** | Quasar/Vue → Material Design out of the box | Best modern look "for free". Strong a11y via browser. |
| **Flet** | Flutter-rendered, Material 3 + Cupertino built-in | Closest to Material 3 from Python. Renders to canvas — native a11y partial. |
| **PyWebView + Tailwind/shadcn** | Bring your own (web stack) | Most flexibility, biggest bundle, most build complexity. |

---

## 4. Color, Typography, Iconography Recommendations

### Color system (token blueprint for tiktokder)

Semantic tokens, mapped twice (light/dark). Aligns with [Fluent 2 tokens](https://fluent2.microsoft.design/design-tokens) and [M3 color roles](https://m3.material.io/styles/color/roles).

```
# tokens (semantic)              light          dark
bg.canvas                        #FAFAFA        #0F0F10
bg.surface                       #FFFFFF        #18181B
bg.subtle                        #F4F4F5        #27272A
border.default                   #E4E4E7        #3F3F46
border.strong                    #D4D4D8        #52525B
text.primary                     #18181B        #FAFAFA
text.secondary                   #52525B        #A1A1AA
text.muted                       #71717A        #71717A
accent.default                   #4F46E5        #818CF8   # indigo
accent.hover                     #4338CA        #6366F1
accent.fg                        #FFFFFF        #FFFFFF
state.success                    #16A34A        #22C55E
state.warning                    #D97706        #F59E0B
state.error                      #DC2626        #EF4444
state.info                       #2563EB        #3B82F6
```

Dark mode rule: **near-black, not pure black** (#0F0F10 / #18181B) — pure #000 over-contrasts on OLED text and adds halation per [2025 dark-mode UX guidance](https://www.influencers-time.com/dark-mode-ux-in-2025-design-tips-for-comfort-and-control/).

System follow: use [`darkdetect`](https://github.com/albertosottile/darkdetect) `.listener(callback)` daemon thread — switches theme live when user toggles OS theme. ~5 lines of code.

### Typography

- **Primary UI font (cross-platform fallback chain)**: `"Segoe UI Variable Display", "SF Pro Text", "Inter", system-ui, sans-serif`.
- **Monospace** (URLs, IDs): `"Cascadia Code", "JetBrains Mono", "SF Mono", monospace`.
- **Type scale** (px, line-height): 11/16 caption, 12/18 body-sm, 13/20 body, 14/22 body-lg, 20/28 h2, 28/36 h1. Six sizes is plenty.
- **Weights**: Regular 400 default, Medium 500 for emphasis/headings, Semibold 600 only for h1/h2. Skip Bold — feels heavy at body size.
- **Why Inter or Geist as fallback**: both screen-tuned, free for commercial use, very wide weight range. Geist (Vercel) reads slightly more "developer tool"; Inter reads slightly more neutral. Either is correct. ([Inter](https://rsms.me/inter/), [Geist](https://vercel.com/font)).

### Iconography

- **Recommendation: Lucide via SVG** (1500+ icons, MIT, consistent 1.5px stroke, line style only — instant modern feel). Load via `QIcon` from SVG files; tint via Qt `QPainter` or pre-render two themed sets.
- **Alternative if you want icon font convenience: qtawesome** with `mdi6` (Material Design Icons, ~7000 icons) or `ph` (Phosphor, multiple weights). One pip install, no asset pipeline.
- **Avoid mixing** outline + filled in same view. Pick one weight (regular/outline) and stick with it.
- **Icon sizes**: 16px (inline), 20px (default toolbar/buttons), 24px (large toolbars), 32–48px (empty-state hero). Always on the 4-grid.
- **Filled vs outline tradeoff**: outline is the current default in 2025 modern UIs (Linear, Vercel, Raycast). Use filled only for *active/selected* state to differentiate.

---

## 5. Accessibility Per Framework

| Framework | Screen reader (Win/macOS/Linux) | Keyboard nav | Focus ring | High contrast | Verdict |
|---|---|---|---|---|---|
| **Qt (PySide6/PyQt)** | Win: UIA via QAccessible (good); macOS: NSAccessibility (good); Linux: AT-SPI (good) | Built-in tab order, customizable | Available, often disabled by default styles — must re-enable | Honors OS HC theme | **Decent.** Best Python option. Custom widgets need explicit `QAccessibleWidget` work. |
| **Web-hybrid (NiceGUI/Flet/PyWebView)** | Browser a11y stack — full ARIA semantics if you author them | Browser handles it | CSS `:focus-visible` | Inherits browser/OS | **Best.** Web stack is the gold standard if you write it correctly. |
| **Tkinter / CustomTkinter** | Win: ~none (no MSAA/UIA bridge); macOS: very limited; Linux: AT-SPI works | Yes | Manual via `<FocusIn>` | Manual | **Disqualified** for accessibility-sensitive use. |
| **Kivy / DearPyGui** | None — they paint to canvas | Manual | Manual | Manual | **Disqualified** unless a11y is a non-goal. |

For Qt apps, the practical a11y to-do list:
1. Re-enable focus ring in QSS (most themes hide it — Fluent/qt-material both need re-enabling).
2. Set `accessibleName` and `accessibleDescription` on every interactive widget that doesn't have visible text (icon-only buttons especially).
3. Keep tab order logical via `setTabOrder()` or just declarative widget creation order.
4. Use `QShortcut` for hotkeys; expose them in tooltips.
5. Test contrast: WCAG AA (4.5:1 body, 3:1 large) is the minimum bar.
6. Test with NVDA on Windows — Qt 5.11+/6.x speaks UI Automation natively now ([NVDA issue 8604](https://github.com/nvaccess/nvda/issues/8604)). NVDA is the default free reader for testing.

---

## 6. Reference Apps to Study (for tiktokder direction)

### Direct genre references

- **Motrix** ([motrix.app](https://motrix.app/), [GitHub](https://github.com/agalwood/Motrix)) — Electron, MIT, dark-first, sidebar nav, card-style task list with ring progress, accent green. **Closest aesthetic target.** Worth screenshotting and matching layout.
- **Free Download Manager 6.x** ([freedownloadmanager.org](https://www.freedownloadmanager.org/)) — modern but information-dense; good study for download-detail panel.
- **Ninja Download Manager** — clean, simple; good study for "minimum-viable polished".

### Anti-references (study to avoid)

- **JDownloader 2** — power-user oriented, classic Java Swing dense look. Capable but visually dated.
- **IDM (classic)** — Windows 9x toolbars, dropdowns-of-dropdowns. Don't.

### General "this is what modern feels like" benchmarks

- **Linear** (linear.app desktop) — keyboard-first, dense but spacious, perfectly tuned typography, pure tokens. The bar.
- **Raycast** — palette-driven, extremely tight visual rhythm, dark-first.
- **Warp** — terminal with modern UI; great example of fitting a "tool" feel into a polished frame.
- **Arc Browser** — sidebar-driven, accent-personalized, dark-first.
- **GitHub Desktop** (Electron) — closest "Microsoft-y" reference, polite and accessible.

### Python ecosystem look-alikes

- **Spyder IDE** — uses qtawesome + Qt, decent reference for dense Qt theming.
- **Existing Python TikTok GUIs** ([Tarekuzjaman0/TikTok-Downloader-GUI](https://github.com/Tarekuzjaman0/TikTok-Downloader--GUI)) use ttkbootstrap — illustrates the ceiling of Tkinter polish (mediocre vs Motrix). **Confirms PySide6 was the right pick.**

---

## 7. Concrete Recommendations for tiktokder

Ranked by impact-to-effort. Adopt the top 3 first.

### Tier 1 — Do these first (1–2 days work)

1. **Adopt PyQtDarkTheme** as the base theme (`qdarktheme.setup_theme("auto", custom_colors={"primary": "#4F46E5"})`). Zero new dependencies of GPL concern. Instant flat dark/light + system follow.
2. **Wire `darkdetect.listener`** to live-toggle theme when the user changes OS theme. Add a `System / Light / Dark` segmented control in Settings, persisted via `QSettings`.
3. **Add qtawesome** and standardize all icons to `mdi6.*` (Material Design Icons) or `ph.*` (Phosphor) — pick one. Replace all current emoji/text-button labels with icon+label.
4. **Define and use a token map** (Python dict or QSS variables) for the 14 semantic colors above. Refactor any hardcoded hex in `gui/*.py` to read from the token map. This is the highest-leverage refactor — locks in consistency and makes light/dark trivial.
5. **Standardize spacing** to {4,8,12,16,24} via a `spacing` constants module. Audit `gui/main_window.py`, `gui/settings_panel.py`, etc. for `setContentsMargins(...)` and `setSpacing(...)` to align.

### Tier 2 — Polish (2–4 more days)

6. **Replace `QMessageBox` toasts with InfoBar** — either QFluentWidgets' `InfoBar` (if you adopt it) or a custom `QFrame` slide-in toast (~50 lines).
7. **Add empty state** to `gui/download_table.py`: when row count == 0, paint a centered icon + headline + sub + primary CTA over the empty area.
8. **Add skeleton rows** when resolving a channel/profile (`gui/channel_browser.py`) — animated gradient sweep on placeholder rows.
9. **Add focus rings** explicitly via QSS — `*:focus { outline: 2px solid <accent>; outline-offset: 2px; }` (Qt 6.5+ supports outline; for older, simulate with border).
10. **Tray icon + minimize-to-tray** option with mini-menu (pause/resume/show/quit). Use `QSystemTrayIcon`. Ship as opt-in.
11. **Drag-and-drop** of URLs and `.txt` onto the window with overlay. Hook `dragEnterEvent` / `dropEvent` on `MainWindow`.
12. **Persist window geometry, splitters, last-used output dir** via `QSettings`.

### Tier 3 — Consider, with tradeoffs

13. **Migrate to QFluentWidgets** if you want full Win11 native feel (Mica window, NavigationView sidebar, ProgressRing). **Cost**: GPLv3 — fine if your repo is GPL-compatible, **not fine** if you plan a permissive license or paid distribution without commercial license. Study its [Components page](https://qfluentwidgets.com/pages/componentlist) before committing.
14. **Replace text labels in toolbar with icon+caption buttons** (à la Office/VS Code). Better visual hierarchy at the cost of being less self-explanatory for first-time users — mitigate with tooltips.
15. **Brand accent**: indigo (#4F46E5) reads "professional dev tool"; pink (#FE2C55, TikTok-coded) reads "fan tool". Pick based on positioning. Default recommendation: indigo — feels neutral, ages better, no platform IP overtones.

### Layout direction (sketch)

Recommend a 3-zone layout, Motrix-inspired:

```
+-----------------------------------------+
| [⬇]  TikTokDer                  [_][□][×] |   <- Mica title bar, frameless
+-----+-----------------------------------+
|     |  URL/Input panel                  |
|  H  |  +-------------------------------+|
|  o  |  |  Download table               ||
|  m  |  |   (skeleton rows when busy)   ||
|  e  |  |   (empty state when empty)    ||
|     |  +-------------------------------+|
|  ⚙  |  Status bar: 3/12 done · 1.4 MB/s|
+-----+-----------------------------------+
```

Sidebar nav (Home / Channel / Settings) instead of current tabs reads more "modern app" and uses screen real estate better at typical 1280×800 windows.

---

## 8. Free / Cheap Design Assets to Bootstrap

- **Untitled UI Free** ([Figma](https://www.figma.com/community/file/1020079203222518115/), [site](https://www.untitledui.com/free-figma-ui-kit)) — best free Figma kit, has tokens (color/spacing/radius/typography variables) you can copy directly into Python constants.
- **Lucide Icons** ([lucide.dev](https://lucide.dev/)) — 1500+ MIT SVGs.
- **Phosphor Icons** ([phosphoricons.com](https://phosphoricons.com/)) — 9000+ icons in 6 weights, MIT.
- **Material Symbols** ([Google Fonts](https://fonts.google.com/icons)) — 3000+ variable icons (fill/weight/grade/optical-size axes), Apache 2.0.
- **Realtime Colors** ([realtimecolors.com](https://realtimecolors.com/)) — tweak token palettes against live UI preview.
- **Coolors** ([coolors.co](https://coolors.co/)) — palette generator with WCAG contrast checker.
- **WebAIM Contrast Checker** — verify AA/AAA on every token pair.
- **Microsoft Fluent 2 docs** ([fluent2.microsoft.design](https://fluent2.microsoft.design/)) — read the [tokens page](https://fluent2.microsoft.design/design-tokens) and [typography page](https://fluent2.microsoft.design/typography); free reference for "what does Win11 native expect".
- **Material Theme Builder** ([m3 builder](https://material-foundation.github.io/material-theme-builder/)) — generate full M3 token set from a seed color.

---

## 9. Unresolved Questions

1. **License posture for tiktokder** — is the project open-source (and OK with GPLv3) or planning permissive/commercial distribution? Determines QFluentWidgets vs PyQtDarkTheme.
2. **Brand identity** — accent color (TikTok pink #FE2C55 vs neutral indigo) is a positioning call. Need product owner input.
3. **A11y target** — does the project need to meet WCAG AA, or is a11y "best-effort"? Determines depth of QAccessible work and contrast strictness.
4. **Window chrome preference** — frameless+Mica (modern, Windows-only polish) vs native title bar (cross-platform consistency)? Affects QFluentWidgets adoption.
5. **Sidebar nav vs tabs** — current code uses what layout? Recommendation hinges on whether to refactor `MainWindow`. Have not read `gui/main_window.py` line-by-line; a small architecture review by a designer-aware contributor would tighten Tier 2.
6. **Min Qt version** — focus-ring `outline` support and Mica APIs need 6.5+. What is the current floor?
7. **Localization plan** — typography pick (Inter vs Segoe UI Variable) is fine for Latin; if Vietnamese/CJK is a target market, Inter has good Vietnamese coverage but Segoe UI Variable wins on Windows. Need locale roadmap.

---

**Status:** DONE
**Summary:** Comprehensive research delivered: modernization checklist (20 items), per-framework theme libs ranked, color/type/icon system blueprint, a11y matrix, reference apps, and 15-item ranked roadmap tailored to tiktokder's PySide6 stack. Recommendation: keep PySide6, adopt PyQtDarkTheme + qtawesome + darkdetect as Tier-1 (MIT, ~1 day work, biggest visual delta); consider QFluentWidgets as Tier-3 if license allows.
**Concerns/Blockers:** None blocking. Seven unresolved product/scope questions listed for team-lead.
