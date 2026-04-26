# Native Python GUI Frameworks — Research Report

**Author:** researcher-1
**Date:** 2026-04-26
**Scope:** PyQt6, PySide6, Tkinter+CustomTkinter (+ttkbootstrap, sv-ttk), Kivy, Dear PyGui, wxPython, BeeWare Toga
**Project context:** TikTok/Facebook batch downloader (Python 3.10+, threading/queue, list/grid display, progress UI). Already on PySide6.

---

## 1. Executive Summary

- **PySide6 wins for this project.** Already adopted; Qt 6.x mature; LGPL-friendly for closed-source distribution; first-class threading via `QThreadPool`/`QRunnable` with signal-slot — perfect fit for downloader queues + progress UI.
- **PyQt6 is functionally identical** to PySide6 (~99.9% same API). Only license differs: GPL/commercial vs LGPL. No technical reason to switch from PySide6.
- **Tkinter + sv-ttk / ttkbootstrap / CustomTkinter** is the lightest "modern enough" path — but loses Qt's Model/View, threading primitives, and rich widget set. Performance issues with many widgets / heavy main-thread work.
- **Dear PyGui** is GPU-rendered ImGui-style — superb for data viz/plots (1M+ points @ 60fps), but non-native look-and-feel. Not a fit for a consumer downloader.
- **Kivy** is desktop-second-class. Non-native widgets, sparse desktop ecosystem, scaling/HiDPI quirks. Skip for desktop.
- **wxPython** uses true native widgets but has smaller community than Qt and slower modernization (no out-of-box dark theme, ad-hoc HiDPI).
- **BeeWare Toga 0.5.x** is still stabilizing — backwards-incompatible changes in March 2025, Qt-on-Linux backend new in Nov 2025. Not production-ready for a polished Windows desktop app yet.
- **For Qt-modern look**: `qdarktheme`, `qt-material`, or `PyQt-Fluent-Widgets` (GPLv3 / commercial) on top of PySide6.
- **Threading verdict for PySide6**: `QThreadPool` + `QRunnable` for the downloader workers; signals carry progress to GUI thread. Avoid `QThread` subclassing unless persistent worker.
- **Bottom line:** Stay on PySide6 + a modern QSS theme (qdarktheme or qt-material). Migration cost zero, ceiling highest, distribution unencumbered.

---

## 2. Per-Framework Deep Dive

### 2.1 PySide6 (Qt for Python — official)

- **Version:** 6.11.0 (March 2026); wraps Qt 6.x. Python 3.10–3.14.
- **License:** **LGPL v3** (commercial paid option) — closed-source distribution OK with dynamic linking.
- **Maintainer:** The Qt Company. Tracks Qt release cadence closely.
- **Look & feel:** Native QStyle by default; modern via QSS, QtQuick/QML Material, or third-party libs. Dark mode requires theme.
- **Theming ecosystem:**
  - `qdarktheme` (PyQtDarkTheme) — flat dark theme.
  - `qt-material` — Material Design QSS.
  - `PyQt-Fluent-Widgets` / `PySide6-Fluent-Widgets` — Win11 Fluent (GPLv3 free; commercial paid).
  - `qtmodernredux` — frameless modern window chrome.
  - QtQuick Controls 2 — `Material`, `Universal`, `Fusion` styles.
- **Performance:** Excellent. Apps like Dropbox/Spotify shipped on Qt. 60fps plotting, smooth scrolling with QListView/QTableView + `QAbstractItemModel`.
- **Threading:** `QThreadPool` + `QRunnable` (recommended for task pools), `QThread` (persistent workers), `QtConcurrent` (functional map/reduce). Signals/slots cross-thread = safe. Mature, well-documented pattern.
- **HiDPI / multi-monitor:** First-class. `Qt::AA_EnableHighDpiScaling` (auto on Qt6).
- **Native widgets:** Custom-rendered but platform-styled — looks native enough on Windows/macOS, fully themable on Linux.
- **MVC/MVVM:** Built-in `QAbstractItemModel`, `QAbstractListModel`, item delegates. QtQuick/QML enables true MVVM with declarative bindings.
- **Learning curve:** Medium-high. Big API surface but excellent docs (doc.qt.io) + Python-specific tutorials (pythonguis.com).
- **Community:** Large. Books, courses (Martin Fitzpatrick "Create GUI Applications with Python & Qt6"), Stack Overflow saturation.

### 2.2 PyQt6 (Riverbank Computing)

- **License:** **GPL v3** or paid commercial (~£550/yr/dev).
- **Tech parity with PySide6:** ~99.9% identical API. Imports differ; signal syntax differs slightly (`pyqtSignal` vs `Signal`).
- **Why pick PyQt6 over PySide6:** Almost never. Slightly older Python wrapping idioms; some prefer SIP semantics. No performance difference.
- **Why pick PySide6 over PyQt6:** Free LGPL for closed-source apps; official Qt Company project; current Qt feature parity faster.
- **Verdict:** For a downloader app distributed as binary, **PySide6** is the correct choice.

### 2.3 Tkinter + Modern Themes

Stdlib (no install). Themes layered on top:

- **CustomTkinter** — 13.3k stars, MIT, active. New widget set on top of Tk; light/dark modes; HiDPI on Win/macOS. Limitations: still single-threaded Tk event loop; performance degrades with many widgets; not as rich as Qt for table/list views.
- **ttkbootstrap** — 20+ Bootstrap-inspired themes, Meter/DateEntry widgets. Themes ttk widgets directly.
- **sv-ttk (Sun Valley)** — Win11 Fluent-style theme. Pure ttk styling.
- **Azure-ttk** — Fluent-inspired light/dark.
- **Threading:** Tk is **NOT thread-safe**. Pattern: background `threading.Thread` + `root.after()` polling or `queue.Queue`. More manual than Qt signals.
- **HiDPI:** Win/macOS OK with CustomTkinter; Linux flaky.
- **Performance:** Fine for simple UIs; struggles with hundreds of dynamic widgets.
- **Verdict:** Acceptable for a small utility, but Qt offers strictly more for a download manager with table view + concurrent workers.

### 2.4 Dear PyGui (DPG)

- **Version:** 2.3 (April 2026). 15.4k stars, MIT.
- **Architecture:** C/C++ Dear ImGui core; immediate-mode GPU rendering (DirectX/OpenGL/Vulkan).
- **Look & feel:** **Non-native.** Game-engine-style UI. Looks consistent everywhere but feels out of place on a desktop OS.
- **Performance:** Best-in-class for plotting (1M+ points @ 60fps; ~120fps on complex charts vs Qt's 60).
- **Widgets:** Plots, node editors, tables, drawing canvas.
- **Threading:** Custom event/render loop; can call DPG from worker threads with the appropriate API.
- **Use case fit:** Data visualization, scientific tools, real-time dashboards. **Not** consumer-facing desktop apps.
- **Verdict:** Wrong fit for a downloader UI.

### 2.5 wxPython (Phoenix)

- **Version:** 4.2.4 (October 2025). Stable. wxBSD-style license.
- **Look & feel:** **Truly native** — uses platform widgets (Win32, Cocoa, GTK).
- **Theming:** Limited — relies on OS theme. No first-class dark mode without manual handling. Less third-party theme ecosystem than Qt.
- **HiDPI:** Yes in 4.2+, but per-platform quirks documented in `high_dpi_overview`.
- **Threading:** `wx.CallAfter` / event-based. Less elegant than Qt signals.
- **Performance:** Good general-purpose; native rendering is fast.
- **Community:** Smaller than Qt; older codebase.
- **Verdict:** Solid choice if you want OS-native at all costs and can tolerate dated tooling. For modern look + dark mode, Qt is easier.

### 2.6 Kivy

- **Version:** 2.3.1 (December 2024). 18.9k stars, MIT.
- **Look & feel:** **Non-native** on desktop. OpenGL-rendered. Built for touch/mobile.
- **Performance:** OK for mobile; Linux Wayland scaling bugs reported.
- **Ecosystem:** Sparse third-party desktop widgets. Strong on Android/iOS.
- **Verdict:** Avoid for a desktop downloader. Mobile-first framework.

### 2.7 BeeWare Toga

- **Version:** 0.5.x (March 2025). Active development. BSD.
- **Maturity:** **Pre-production for Windows polish.** Backwards-incompatible changes shipping. Qt backend on Linux added Nov 2025 — too new.
- **Look & feel:** Truly native (WinForms on Windows, Cocoa on macOS, GTK/Qt on Linux).
- **Coverage:** Cross-platform incl. iOS/Android/web. Widget set narrower than Qt.
- **Verdict:** Promising for cross-platform-incl-mobile apps. Not the right risk profile for a polished Windows desktop release in 2026.

---

## 3. Comparative Table

| Framework | Latest | License | Look | Theming | Native widgets | HiDPI | Threading | Perf | Community | Modern look OOTB |
|-----------|--------|---------|------|---------|----------------|-------|-----------|------|-----------|-----------------|
| **PySide6** | 6.11 (2026-03) | LGPL/Commercial | Qt-styled | QSS, QML Material/Fluent, qdarktheme, qt-material, Fluent-Widgets | Styled, near-native | Excellent | QThreadPool+signals (best) | Excellent | Very large | With theme: yes |
| PyQt6 | 6.x | GPL/Commercial | = PySide6 | = PySide6 | = PySide6 | = PySide6 | = PySide6 | = PySide6 | Large | = PySide6 |
| Tkinter+sv-ttk/ttkbootstrap | stdlib + lib | MIT | Themed ttk | sv-ttk, ttkbootstrap, Azure | Native via ttk | OK Win/Mac, weak Linux | Manual (Thread+after/Queue) | Good for small | Large for stdlib | Yes with theme |
| CustomTkinter | 5.x (2024+) | MIT | Custom modern | Built-in light/dark | No (custom) | OK Win/Mac | Same as Tk | OK | Medium (13k★) | Yes |
| Dear PyGui | 2.3 (2026-04) | MIT | ImGui (game-style) | Built-in styles | No | Yes | Custom event loop | Best (GPU) | Medium (15k★) | Modern but non-native |
| wxPython | 4.2.4 (2025-10) | wxBSD | True native | Limited; OS-theme-driven | Yes (true native) | Yes (with quirks) | wx.CallAfter | Good | Medium-small | Native only — no dark OOTB |
| Kivy | 2.3.1 (2024-12) | MIT | OpenGL custom | Themable, mobile-style | No | Buggy on Linux | Kivy event loop | OK | Large but mobile-skewed | Mobile-modern, desktop-out-of-place |
| BeeWare Toga | 0.5.x (2025-03) | BSD | True native | Limited | Yes per platform | Yes | asyncio | OK | Small, growing | Native only |

---

## 4. Recommendations by Use-Case

| Use case | Pick | Why |
|----------|------|-----|
| Small utility, ship fast | **Tkinter + sv-ttk** or **CustomTkinter** | Stdlib + tiny dep; modern enough |
| **Data-heavy / plots / dashboards** | **Dear PyGui** | GPU rendering, 1M-point plots |
| **Media-heavy (video/audio/streams)** | **PySide6** (QtMultimedia) | Mature media stack, native players |
| **Cross-platform consumer (Win+macOS+Linux)** | **PySide6** | Best balance of polish, license, ecosystem |
| Cross-platform incl. **mobile** | Kivy (touch) or BeeWare Toga (native) | Desktop-only frameworks don't reach mobile |
| Closed-source commercial app | **PySide6** | LGPL-safe; no royalty |
| Pure-native look-and-feel only | **wxPython** | True native widgets |

---

## 5. Application to TikTok/Facebook Downloader

**Already on PySide6** — recommendation: **stay**, modernize the theme.

Why PySide6 fits this app specifically:

1. **Threading model maps cleanly.** `download_engine.py` uses `ThreadPoolExecutor` — easily wrapped with `QRunnable` + `QThreadPool` so progress signals (`pyqtSignal`/`Signal`) update the GUI thread without manual queues. PySide6's signal-slot is the canonical Pythonic answer to "background workers + GUI updates".
2. **List/grid of downloads.** `QTableView` or `QListView` + `QAbstractItemModel` scales to thousands of rows with delegates for progress bars per row. None of Tkinter/CustomTkinter/Toga match this for tabular data.
3. **Channel browsing (image grid).** `QListView` + icon mode + `QPixmap` thumbnails + `QNetworkAccessManager` for async fetch. Built-in.
4. **Dark mode out of the box** with `qdarktheme.setup_theme("auto")` — single line, follows OS preference.
5. **PyInstaller compatible.** Project already builds standalone via `tiktokder.spec` (build.py). PySide6 packs cleanly.
6. **License OK for redistribution.** LGPL — no source disclosure obligation.

**Concrete modernization moves (no framework change):**
- Add `pyqtdarktheme` or `qt-material` for instant dark theme.
- For Win11 Fluent vibe: `PyQt-Fluent-Widgets` (PySide6 branch) — but **GPLv3 free / commercial paid** — confirm license fit before adopting.
- Replace any blocking `time.sleep` in GUI thread with `QTimer.singleShot`.
- Migrate workers from raw threads (if any) to `QRunnable` + `QThreadPool` for proper lifecycle + signal-based progress.

**What would justify changing framework:** nothing in the current app's requirements does. Switching to Tkinter loses table/grid quality; switching to Dear PyGui loses native consumer feel; switching to Toga adds risk and removes widgets.

---

## 6. Sources

- [PySide6 PyPI](https://pypi.org/project/PySide6/) — latest 6.11, Python 3.10–3.14 support
- [PyQt6 vs PySide6 — Python GUIs](https://www.pythonguis.com/faq/pyqt6-vs-pyside6/)
- [PyQt vs PySide Licensing — Python GUIs](https://www.pythonguis.com/faq/licensing-differences-between-pyqt6-and-pyside6/)
- [Which Python GUI library 2026 — Python GUIs](https://www.pythonguis.com/faq/which-python-gui-library/)
- [QThreadPool tutorial — Python GUIs (2026-03)](https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/)
- [Qt Multithreading Technologies docs](https://doc.qt.io/qt-6/threads-technologies.html)
- [CustomTkinter GitHub](https://github.com/TomSchimansky/CustomTkinter) — 13.3k★ MIT
- [ttkbootstrap GitHub](https://github.com/israel-dryer/ttkbootstrap)
- [sv-ttk / Sun Valley](https://github.com/rdbende/Sun-Valley-ttk-theme)
- [Azure-ttk-theme](https://github.com/rdbende/Azure-ttk-theme)
- [Dear PyGui GitHub](https://github.com/hoffstadt/DearPyGui) — v2.3, 15.4k★ MIT
- [DearPyGui 2.0 PyPI](https://pypi.org/project/dearpygui/2.0.0/)
- [wxPython HiDPI docs](https://docs.wxpython.org/high_dpi_overview.html)
- [wxPython 4.2.x PyPI](https://pypi.org/project/wxPython/)
- [Kivy GitHub](https://github.com/kivy/kivy) — 2.3.1 (Dec 2024), 18.9k★
- ["Is Kivy Dead?" — Medium](https://haddiebakrie.medium.com/is-kivy-dead-the-rise-of-a-new-python-ui-framework-era-31fba8ccf06b)
- [BeeWare Toga 0.5.0 release — March 2025](https://beeware.org/news/buzz/2025/march-2025-status-update/)
- [BeeWare November 2025 update](https://beeware.org/news/buzz/november-2025-status-update/)
- [PyQt-Fluent-Widgets GitHub](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — 7.8k★, GPLv3/Commercial
- [qt-material](https://github.com/UN-GCPDS/qt-material)
- [PyQtDarkTheme](https://github.com/5yutan5/PyQtDarkTheme)
- [QtModernRedux](https://github.com/robertkist/qtmodernredux)

---

## 7. Unresolved Questions

1. **Fluent-Widgets license fit?** PyQt-Fluent-Widgets is GPLv3 free / commercial paid. Project's distribution model (open-source vs paid binary) determines if free tier works. Need clarification on intended distribution.
2. **Mobile target?** If iOS/Android is on the roadmap, PySide6 desktop becomes insufficient and Toga/Kivy reopen. Currently README says Windows/macOS/Linux — assume desktop-only.
3. **Exact target Windows versions?** Win10+ vs Win11 affects whether Fluent (Win11-style) feels right. sv-ttk and Fluent-Widgets are Win11-flavored; on Win10 they may feel slightly off.
4. **Performance bar for download list?** Hundreds, thousands, or tens-of-thousands of rows? Affects whether `QListView` (lazy model) is needed vs simple `QTableWidget`.
5. **Streamed thumbnails for channel browsing?** If yes, prefer `QNetworkAccessManager` + `QPixmapCache` patterns; out of scope for framework choice but informs adoption work.

---

**Status:** DONE
**Summary:** Confirmed PySide6 is the right native framework for the project. Ranked alternatives with a comparative table; recommended modernization via `qdarktheme`/`qt-material` rather than framework change.
**Concerns:** Fluent-Widgets license needs review if adopted.
