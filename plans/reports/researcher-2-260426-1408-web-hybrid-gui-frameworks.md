# Web-Hybrid Modern Python GUI Frameworks — Research Report

**Researcher:** researcher-2
**Date:** 2026-04-26
**Project context:** tiktokder (TikTok video downloader, Python, list+progress+settings UI)

---

## 1. Executive Summary

- **Flet** is the most credible "modern UI from Python" path: Flutter engine renders Material/Cupertino, true desktop app, 16k stars, 0.84.0 (2026-04-01), Apple-grade visuals. **Cost:** ~80–300 MB bundle, 10–20 s cold start before optimisations, imperative API still default (declarative 1.0 beta exists but not stable as of 2026-04). Real risk: ecosystem cannot tap pub.dev's 38k Flutter packages.
- **NiceGUI** (15.7k stars, v3.11.1, 2026-04-25, MIT) — Vue/Quasar/FastAPI; Material look out-of-the-box; runs as desktop via built-in `native=True` (pywebview). Best polished UI per LOC. PyInstaller works but has known rough edges; tray icon, drag-drop, notifications all reachable via pywebview but require glue.
- **PyWebView 6** (system webview, BSD) — most lightweight (sub-10 MB binary, <500 ms start, ~70-80% lower memory vs Electron). You write HTML/CSS/JS yourself; Python is backend only. New shared-state and network event APIs in v6 close the IPC ergonomics gap. Maximum control, maximum DIY.
- **Eel — DEAD.** Repo archived 2025-06-22. Do not adopt.
- **Reflex (Pynecone)** — pure web framework; React SPA + Python state. Not a desktop framework today; desktop packaging is a discussion item, not a product. Skip.
- **Trame (Kitware)** — niche: scientific viz with VTK/ParaView. Wrong tool for a downloader.
- **Streamlit / Gradio** — dashboard-first; "desktop" only via 3rd-party Electron/Tauri wrappers (stlite, gradio-lite). Cumbersome for an interactive downloader UI.
- **Anvil-runtime** — server-hosted web app builder. Drag-and-drop builder, but optimised for SaaS-style apps, not local desktop tools.
- **Spotify/Discord-quality from Python?** Honest answer: **Flet gets closest visually** (Flutter-rendered Material 3); **NiceGUI gets closest in productivity**; both are 80–90% of the way. PyWebView + a real frontend stack (e.g. React/Svelte) can match it 100% but you'd be writing two stacks.
- For **tiktokder**: **NiceGUI in native mode** is the fastest path to a polished list-of-tasks/progress/settings UI. Falls back to Flet if you want zero-HTML and a single bundle. PyWebView only if a heavier custom frontend is acceptable.

---

## 2. Per-Framework Deep Dive

### 2.1 Flet

| Field | Value |
|---|---|
| Latest version | 0.84.0 (2026-04-01); 1.0 in beta |
| License | Apache-2.0 |
| GitHub stars | ~16k, 651 forks, 138 releases |
| Renderer | **Flutter engine** (bundled) |
| Architecture | Python process talks to embedded Flutter app via `serious_python`; UI drawn by Flutter, controlled imperatively from Python |
| Bundle size (desktop) | macOS ~300 MB with `flet pack`; Windows commonly 80–150 MB with `flet build`; Flutter engine + Python interpreter both bundled |
| Cold start | Historically 10–20 s on first launch; v0.27 unpacks site-packages instead of zip → significantly faster; v0.83 added 6.7× faster control diffing |
| Async/threading | First-class async support; long-running work belongs in async tasks or threads; UI updates require `page.update()` (imperative) or auto-update in declarative 1.0 |
| OS integration | File-pickers (`FilePicker`), system tray via plugins, notifications via plugins; drag-drop limited; deep links via Flutter platform channels |
| Theming | Material 3, Cupertino, custom themes; 150+ built-in controls; full color/typography theming |
| Packaging | `flet build windows/macos/linux` uses Flutter SDK to produce native exe with embedded Python; cross-compile not supported (Windows must build on Windows, etc.) — Linux can also build for Windows |
| PyInstaller | Legacy `flet pack` route; deprecated for `flet build` |
| Hot reload | Yes, in dev mode via Flet CLI |
| Production proof | Flet's own iOS App Store companion app; community apps; **no high-profile commercial app publicly disclosed** |

**Strengths:**
- Visuals are genuinely modern (real Flutter rendering, not HTML faked to look native).
- Single Python codebase targets desktop + mobile + web (PWA / WASM) — only framework here with that scope.
- Active maintainers, frequent releases, Talk Python coverage twice (eps. 494 + others).

**Weaknesses (critical for tiktokder use-case):**
- **Imperative-by-default**: every state change requires `page.update()` or risks UI desync. Declarative 1.0 is beta, not stable in 2026-04.
- **Flutter ecosystem locked out**: 38k pub.dev packages unavailable; Stack Overflow + Flutter docs only partially apply.
- Bundle bloat: 80–300 MB is large for a small downloader.
- `ListView` has well-known scrolling gotchas inside containers (issue #2824).
- Critical review by Maxim Saplin (DEV.to) flags Flet as anti-Flutter philosophically — fine for prototypes, painful for long-lived apps.

**Verdict:** Pick Flet if visual polish is THE priority and you accept the imperative model + bundle size.

---

### 2.2 NiceGUI

| Field | Value |
|---|---|
| Latest version | 3.11.1 (2026-04-25); v3.0 was a major refactor (Talk Python ep. 525) |
| License | MIT |
| GitHub stars | ~15.7k |
| Renderer | Vue 3 + Quasar (Material) + Tailwind 4 in browser/webview; FastAPI + socket.io backend |
| Architecture | Python server (FastAPI/Uvicorn) ↔ Vue frontend over websocket; in `native=True`, embeds a pywebview window pointing at localhost |
| Bundle size | Small Python deps, but **pywebview + Quasar assets ~40–80 MB** packaged; depends on PyInstaller config |
| Cold start | Fast (sub-second to a few seconds depending on PyInstaller mode) |
| Async/threading | Pure async (FastAPI); `ui.timer`, queues, multiprocessing supported; CPU-bound work runs in subprocess to keep UI responsive |
| OS integration | Native mode: window controls, file dialogs (via pywebview), notifications (`ui.notify` in-app + pywebview/pystray for native), tray (pystray integration), drag-drop (`ui.upload` + native via pywebview js_api) |
| Theming | Quasar Material 3 + Tailwind 4; dark mode toggle; custom CSS supported; very rich component library out-of-box (charts, 3D, code editor, leaflet maps) |
| Packaging | PyInstaller documented; `nicegui-pack`/spec recipes exist; tray + splash patterns documented in discussions |
| PyInstaller | **Works but rough**: `window_args` and `on_startup` can be lost after freezing (issue #2549, #355); workarounds shared in discussions |
| Hot reload | Yes (FastAPI auto-reload in dev) |
| Production proof | nicegui.io site itself; **Zauberzeug uses it in production for mobile robot control**; PyData Berlin 2025 talks |

**Strengths:**
- Highest UI quality per Python LOC of any option here. Quasar gives Material polish for free.
- Rich component catalog: tables w/ sort/filter, dialogs, notifications, plotly/echarts, code editor, drawer, drag-drop. Perfect fit for a download manager UI (table, progress, settings).
- Pure Python — no HTML/CSS/JS required, but you can drop into Tailwind classes when you want fine control.
- v3 stack is fresh (Tailwind 4, modern Vue), backend-first philosophy aligns with existing tiktokder Python codebase.
- MIT license (more permissive than Flet's Apache-2.0).

**Weaknesses:**
- Effectively a localhost server — if user's antivirus is paranoid, false positives possible.
- Native mode = pywebview wrapping; tray/notifications require extra libs (pystray, plyer/winrt).
- PyInstaller bundling has paper cuts; expect 1-2 days to nail packaging.
- Two-process model (server + webview) costs memory vs single-process Flet.

**Verdict:** Best **productivity-to-polish ratio** for a Python desktop tool. Strongest fit for tiktokder.

---

### 2.3 PyWebView

| Field | Value |
|---|---|
| Latest version | 6.x (2025); 6.0 brought shared state + network events |
| License | BSD-3-Clause |
| GitHub stars | ~5k+ |
| Renderer | **System webview**: WebView2 (Chromium) on Windows, WKWebView on macOS, WebKitGTK / QtWebEngine on Linux |
| Architecture | Single Python process hosts a native webview window; Python ↔ JS via `js_api` and v6 shared state |
| Bundle size | Sub-10 MB binary common (webview is OS-provided); Linux WebKitGTK adds size if bundled |
| Cold start | <500 ms typical; "2.6× faster than Tauri" per pywebview marketing benchmarks |
| Async/threading | Sync + async API; window methods can be called from any thread |
| OS integration | File dialogs (built-in), full webview2 features on Windows, drag-drop (HTML5), tray via pystray, notifications via plyer/winrt |
| Theming | **You bring the frontend** — HTML/CSS/JS or React/Vue/Svelte; theme is whatever you build |
| Packaging | PyInstaller works well; smallest binaries of any option here |
| WebView2 runtime | Auto-installed on modern Windows 11; bundleable via `WEBVIEW2_RUNTIME_PATH` for offline scenarios |
| Hot reload | Manual (rebuild frontend, refresh webview) |
| Production proof | Many indie apps; Traefik Pilot used it; comparable footprint to Tauri but Python-native |

**Strengths:**
- **Lowest footprint** by far. Best memory and disk story.
- Total UI freedom — adopt any modern web stack.
- v6 shared state + network events make Python↔JS bridge ergonomic without a server.
- BSD license, mature, actively maintained.

**Weaknesses:**
- You must build (or adopt) the entire frontend. **No component library included.** This is the deal-breaker vs NiceGUI/Flet for "polished UI fast."
- Frontend tooling (npm, bundlers) re-enters your toolchain.
- Linux fragmentation: WebKitGTK quirks across distros.

**Verdict:** Best if (a) you already have a frontend skill or (b) you want the lightest desktop wrapper possible. Overkill for tiktokder unless you crave a custom-designed UI.

---

### 2.4 Eel

| Field | Value |
|---|---|
| Latest version | 0.18.2 (2025-06-22) |
| License | MIT |
| Status | **REPO ARCHIVED 2025-06-22** — read-only, unmaintained |
| GitHub stars | ~6.8k |
| Renderer | Chrome / Edge in `--app` mode |

**Verdict:** Do not adopt. Project owner explicitly states no plans to maintain.

---

### 2.5 Reflex (formerly Pynecone)

| Field | Value |
|---|---|
| Latest version | active 2025-2026 |
| License | Apache-2.0 |
| Architecture | Python state → compiles to React SPA + FastAPI backend |
| Desktop story | **Not a desktop framework.** Discussion #1211 ("desktop and mobile packaging") still open; Reflex Build (AI app generator) launched but for web |

**Verdict:** Wrong tool. Reflex is a Streamlit-class web framework, not desktop.

---

### 2.6 Trame (Kitware)

| Field | Value |
|---|---|
| License | Apache-2.0 |
| Renderer | Vuetify + Vue + VTK/ParaView + Altair/Vega/deck.gl |
| Use case | Scientific visualisation (3D data, VTK pipelines) |
| 2025 update | IEEE CG&A paper; new VTK rendering backends (X/EGL/OSMesa) |

**Verdict:** Specialised. Unrelated to a download manager.

---

### 2.7 Streamlit / Gradio (desktop wrappers)

- **stlite**: Streamlit compiled to WebAssembly, can be wrapped in Electron for desktop. Heavy and dashboard-shaped.
- **gradio-lite**: similar story; Gradio works best for ML model demos, not desktop tools.
- Neither maps well to a list-of-downloads + per-row progress + settings UI. They are "form → output" frameworks.

**Verdict:** Wrong shape.

---

### 2.8 Anvil-runtime

| Field | Value |
|---|---|
| Latest | 1.15.0 (2026-01-30) |
| Architecture | Drag-drop visual builder + Python on both client (transpiled to JS via Skulpt) and server |
| Desktop story | Self-host the App Server; not a true desktop app but runs offline-localhost |

**Verdict:** Optimised for SaaS-style line-of-business apps. Overkill and architecturally mismatched for a downloader.

---

## 3. Comparative Table

| Framework | Renderer | Bundle | Startup | UI Polish | OS Integration | Packaging | Maturity | Best For |
|---|---|---|---|---|---|---|---|---|
| **Flet** | Flutter engine | 80-300 MB | 2-20 s | ★★★★★ | ★★★☆☆ | `flet build` | Active, beta 1.0 | Beautiful cross-platform incl. mobile |
| **NiceGUI** | Vue/Quasar (webview) | 40-80 MB | 1-3 s | ★★★★☆ | ★★★★☆ (via pywebview) | PyInstaller (rough edges) | Mature, v3.11 | Polished desktop tools, fastest |
| **PyWebView** | System webview | <10 MB | <0.5 s | depends on you | ★★★★★ | PyInstaller | Mature, v6 | Lightweight, custom frontend |
| **Eel** | Chrome `--app` | small | fast | depends | ★★☆☆☆ | PyInstaller | **DEAD (archived)** | Nothing — avoid |
| **Reflex** | React (web) | n/a desktop | n/a | ★★★★☆ web | n/a | web only | Active | Web SPA only |
| **Trame** | Vue + VTK | varies | varies | viz-focused | ★★☆☆☆ | docker/pip | Active | Sci viz only |
| **Streamlit-desktop** | WebAssembly + Electron | 100+ MB | medium | ★★★☆☆ | ★★☆☆☆ | stlite/Electron | indirect | Dashboards |
| **Anvil-runtime** | Skulpt + Anvil | server | n/a | ★★★★☆ | ★☆☆☆☆ | App Server | Active | LOB web apps |

---

## 4. Recommendations Per Use-Case

| Use-case | Pick |
|---|---|
| Quick, modern desktop tool (data + lists + forms), Python-only team | **NiceGUI native mode** |
| Cross-platform incl. mobile/iOS, willing to pay bundle cost | **Flet** |
| Lightest possible desktop binary, comfortable with HTML/CSS/JS | **PyWebView 6** |
| Internal LOB web app, drag-drop builder | Anvil-runtime |
| Scientific viz, VTK/ParaView pipelines | Trame |
| ML model demo, single-page input → output | Gradio |
| Data dashboard | Streamlit |
| Anything | NOT Eel (dead), NOT Reflex for desktop |

---

## 5. Applied to tiktokder

**Project shape:** TikTok URL → list of queued/active downloads → per-row progress → settings panel. Already has:
- Python codebase, downloader logic, tenacity retries, PyInstaller build
- Existing GUI in some toolkit (modify-status shows GUI work in progress)

**Top recommendation: NiceGUI (native mode).**

Why:
1. Quasar's `q-table`/`q-list` + `ui.linear_progress` map 1:1 onto your domain (download rows + progress).
2. `ui.notify` + pywebview tray = native-feeling status without writing widgets.
3. FastAPI backend means your downloader (already async/concurrent for retries) drops in cleanly.
4. Material 3 dark mode + Tailwind 4 = "Spotify-ish" look out-of-the-box, no custom theming required for v1.
5. MIT license, low friction to package over your existing PyInstaller setup.

**Risks to plan for:**
- PyInstaller `window_args` / `on_startup` quirks — budget half a day of packaging work.
- Two-process model (Uvicorn + webview) bumps memory; fine for desktop, not VM-friendly.
- Antivirus may flag a localhost server on Windows; sign the binary.

**Second choice: Flet.** Pick if you want the prettiest possible UI and accept ~150 MB Windows installer + the imperative model. Best long-term bet IF you also want a mobile app later.

**Skip for tiktokder:** PyWebView (too DIY for the polish goal), Eel (dead), Reflex/Anvil (wrong shape), Streamlit/Gradio (dashboard pattern, not task manager pattern), Trame (unrelated domain).

**Migration cost from current GUI:** NiceGUI is the cheapest because logic stays Python; you replace the view layer. Flet would require larger refactor due to its imperative `page.update()` discipline.

---

## 6. Unresolved Questions

1. **Current tiktokder GUI framework?** Report assumes a swap. If it's already Tkinter/CustomTkinter, NiceGUI swap is small; if PySide6, may not need a hybrid framework at all.
2. **Mobile target ever?** If yes → Flet wins (only option). If no → NiceGUI wins on productivity.
3. **Binary size budget?** If <30 MB is hard requirement → PyWebView only.
4. **Code-signing infra?** Both Flet (`flet build`) and NiceGUI+PyInstaller produce binaries that benefit from signing on Windows/macOS; team capacity unclear.
5. **Flet 1.0 stable timeline.** As of 2026-04 still beta. If migration to declarative API is desired, timing matters.
6. **NiceGUI memory profile under heavy concurrent downloads** — not benchmarked here; worth a quick spike before commitment.
7. **Antivirus / firewall behaviour** of NiceGUI's localhost socket on locked-down corporate Windows — not validated.

---

## Sources

- [Flet GitHub](https://github.com/flet-dev/flet)
- [Flet flet.dev](https://flet.dev/)
- [Flet Publish docs](https://flet.dev/docs/publish/)
- [Flet 0.83 release notes](https://flet.dev/blog/flet-v-0-83-release-announcement/)
- [Flet 1.0 Alpha](https://flet.dev/blog/introducing-flet-1-0-alpha/)
- [Flet declarative UI](https://flet.dev/blog/introducing-declarative-ui-in-flet/)
- [Flet criticism — Maxim Saplin DEV.to](https://dev.to/maximsaplin/flet-is-the-fastest-way-to-build-flutter-apps-in-python-its-not--3dkm)
- [Flet startup time issue #322](https://github.com/flet-dev/flet/issues/322)
- [Flet ListView issue #2824](https://github.com/flet-dev/flet/issues/2824)
- [Talk Python ep. 494 — Flet update](https://talkpython.fm/episodes/show/494/update-on-flet-python-flutter-uis)
- [NiceGUI GitHub](https://github.com/zauberzeug/nicegui/)
- [NiceGUI nicegui.io](https://nicegui.io/)
- [NiceGUI Native Mode — DeepWiki](https://deepwiki.com/zauberzeug/nicegui/6.2-native-mode)
- [NiceGUI PyInstaller native mode discussion #1714](https://github.com/zauberzeug/nicegui/discussions/1714)
- [NiceGUI tray discussion #980](https://github.com/zauberzeug/nicegui/discussions/980)
- [NiceGUI drag-drop native discussion #3372](https://github.com/zauberzeug/nicegui/discussions/3372)
- [Talk Python ep. 525 — NiceGUI 3.0](https://talkpython.fm/episodes/show/525/nicegui-goes-3.0)
- [PyWebView 6.0 release notes](https://pywebview.flowrl.com/blog/pywebview6.html)
- [PyWebView vs Electron lightweight](https://johal.in/pywebview-python-tiny-electron-cef-alternative-cross-platform-2025/)
- [Eel GitHub (archived)](https://github.com/python-eel/Eel)
- [Reflex GitHub](https://github.com/reflex-dev/reflex)
- [Reflex desktop discussion #1211](https://github.com/orgs/reflex-dev/discussions/1211)
- [Trame GitHub](https://github.com/Kitware/trame)
- [Trame Kitware](https://www.kitware.com/trame/)
- [Anvil open source](https://anvil.works/blog/open-source)
- [Anvil-runtime GitHub](https://github.com/anvil-works/anvil-runtime)
- [Streamlit vs Gradio 2025](https://www.squadbase.dev/en/blog/streamlit-vs-gradio-in-2025-a-framework-comparison-for-ai-apps)
- [Gradio-lite desktop bundler issue](https://github.com/gradio-app/gradio/issues/7032)
- [PythonGUIs framework comparison 2026](https://www.pythonguis.com/faq/which-python-gui-library/)
