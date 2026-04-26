---
title: "Migrate TikTokDer to Tauri 2 + SvelteKit + Rust core"
description: "Big-bang rewrite from Python/PySide6 to Tauri 2 (Rust) + SvelteKit/Tailwind frontend. yt-dlp.exe as sidecar. Drop CLI. Target: ~30-50 MB build (from 167 MB)."
status: blocked
priority: P1
effort: 4-6 weeks
branch: feat/tauri-migration
tags: [tauri, rust, sveltekit, migration, packaging, performance]
created: 2026-04-26
blockedBy: [260426-2231-platform-first-ui-restructure]
blocks: []
---

> **Blocked (2026-04-26):** Paused pending platform-first UI restructure
> (`260426-2231-platform-first-ui-restructure`). Per user decision: ship the new IA
> on the stable PySide6 codebase first; when this resumes, **phase-07-svelte-tabs**
> must be revised to match the platform-first 3-tab IA (TikTok | Facebook | Settings)
> with Channels / Queue / Library sub-sections per platform.


# Tauri 2 Migration — Implementation Plan

## Goal
Rewrite TikTokDer's GUI + core in Rust (Tauri 2) + SvelteKit/Tailwind, keeping yt-dlp.exe as the only Python (sidecar binary). Drop CLI. Eliminate PySide6, Playwright, curl_cffi, tenacity, and the entire Python interpreter from the shipped artefact. Cut bundle from 167 MB → ~30-50 MB. Match feature parity with v1.2.0.

## Out of Scope
- yt-dlp replacement (no Rust equivalent exists; bundle the .exe).
- Python CLI (`main.py`) — deleted at cutover.
- iOS/Android (Tauri Mobile is alpha; defer).
- Code signing, auto-updates (defer to post-cutover).
- New features beyond v1.2.0 parity.

## Source Context
- Current codebase: 22 Python modules, 6115 LOC, 257 tests, 167 MB onedir build.
- Feature surface (v1.2.0): 4 tabs (Download/Channel-Page/History/Settings), drag-drop, import/export, retry/force, history v2 with FIFO cap, per-platform pacing (TikTok 1.5s ±0.5; FB 3.0s ±1.5, workers=1), 10/2 retry attempts, FB shortlink pre-resolution, FB login-wall fast-fail, yt-dlp ImpersonateTarget chrome 136, dark/light/system theme with darkdetect listener, 15 semantic tokens.
- Hard contracts to preserve: history JSON v2 schema, config.json keys, output tree `downloads/{platform}/{uploader}/{id}_{title}.{ext}`, error classes (LoginRequired/Private/NotFound/RateLimited/TransientFailure), per-platform PlatformDefaults, FB_LOGIN_WALL_MARKERS list.

## Locked Decisions
| # | Question | Decision |
|---|----------|----------|
| 1 | yt-dlp strategy | Bundle yt-dlp.exe as Tauri sidecar (no Python interpreter in build) |
| 2 | Frontend | SvelteKit + Tailwind v4 + TypeScript, adapter-static |
| 3 | CLI | Drop. yt-dlp.exe sidecar can be invoked manually by power users |
| 4 | Migration | Big-bang full Rust rewrite of core + Tauri front-end |
| 5 | History store | SQLite via `rusqlite` (JSON v2 imported once at first launch) |
| 6 | TLS impersonation | `rquest` crate (Chrome JA3/JA4 fingerprints) replaces curl_cffi |
| 7 | Retry policy | Custom Rust impl with `tokio::time::sleep` + decorrelated jitter + Retry-After awareness (no `backon` dep) |
| 8 | Browser automation | **Eliminate.** Replace Playwright FB scraping with yt-dlp.exe `--flat-playlist` + cookies-from-browser. If insufficient, document and use rquest HTML scraping. |
| 9 | ffmpeg | Bundle minimal Windows static build (~15-25 MB stripped) — point yt-dlp at it via `--ffmpeg-location` |
| 10 | Workspace | Single Cargo workspace at repo root; legacy Python kept until phase 10 cutover |

## Phases

| # | File | Status | Effort | Depends |
|---|------|--------|--------|---------|
| 01 | [phase-01-workspace-bootstrap.md](phase-01-workspace-bootstrap.md) | pending | 0.5d | — |
| 02 | [phase-02-rust-core-port.md](phase-02-rust-core-port.md) | pending | 2d | 01 |
| 03 | [phase-03-ytdlp-sidecar-engine.md](phase-03-ytdlp-sidecar-engine.md) | pending | 3d | 02 |
| 04 | [phase-04-history-sqlite.md](phase-04-history-sqlite.md) | pending | 1d | 02 |
| 05 | [phase-05-channel-fb-listing.md](phase-05-channel-fb-listing.md) | pending | 2d | 03 |
| 06 | [phase-06-svelte-ui-shell.md](phase-06-svelte-ui-shell.md) | pending | 1.5d | 01 |
| 07 | [phase-07-svelte-tabs.md](phase-07-svelte-tabs.md) | pending | 4d | 03, 04, 05, 06 |
| 08 | [phase-08-ux-parity.md](phase-08-ux-parity.md) | pending | 1.5d | 07 |
| 09 | [phase-09-bundling.md](phase-09-bundling.md) | pending | 1d | 07 |
| 10 | [phase-10-tests-cutover.md](phase-10-tests-cutover.md) | pending | 2d | 08, 09 |

**Total: ~18.5 dev-days (~4 weeks calendar with normal slippage; 5-6 weeks if Rust learning curve hits).**

## Architecture (target)

```
tiktokder/                                  (repo root, kept as monorepo)
├── Cargo.toml                              workspace
├── src-tauri/                              Tauri app (Rust)
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   ├── capabilities/
│   │   └── default.json                    ACL — shell:execute (sidecar), fs:read, dialog:open
│   ├── icons/
│   ├── binaries/                           sidecars per target triple
│   │   ├── yt-dlp-x86_64-pc-windows-msvc.exe
│   │   └── ffmpeg-x86_64-pc-windows-msvc.exe
│   ├── migrations/                         SQL files (rusqlite_migration)
│   └── src/
│       ├── main.rs                         Tauri builder + plugins + state
│       ├── commands.rs                     #[tauri::command] handlers
│       ├── config.rs                       AppConfig load/save (JSON, serde)
│       ├── url_parser.rs                   regex patterns + detect_platform
│       ├── path_builder.rs                 slugify + outtmpl
│       ├── retry.rs                        typed errors + decorrelated jitter
│       ├── fb_resolver.rs                  rquest-based fb.watch shortlink resolver
│       ├── engine/
│       │   ├── mod.rs                      DownloadEngine (tokio tasks + semaphore)
│       │   ├── ytdlp.rs                    sidecar Command wrapper, JSON-line stream parser
│       │   ├── progress.rs                 typed event enum + Channel<T>
│       │   └── classify.rs                 stderr → ErrorKind
│       ├── history/
│       │   ├── mod.rs                      SQLite store
│       │   ├── schema.sql
│       │   └── import_v2.rs                one-shot migration from history.json
│       ├── channel/
│       │   ├── tiktok.rs                   yt-dlp --flat-playlist
│       │   └── facebook.rs                 yt-dlp --flat-playlist (replaces Playwright)
│       └── lib.rs
├── package.json
├── svelte.config.js                        adapter-static, prerender all
├── vite.config.ts
├── tailwind.config.js
├── src/                                    SvelteKit frontend
│   ├── app.html
│   ├── app.css                             Tailwind + design tokens via CSS vars
│   ├── lib/
│   │   ├── ipc.ts                          invoke wrappers, event listeners, channel consumers
│   │   ├── stores/
│   │   │   ├── downloads.ts                queue + progress map
│   │   │   ├── history.ts
│   │   │   ├── settings.ts
│   │   │   └── theme.ts
│   │   ├── tokens.ts                       light/dark palettes (port of gui/tokens.py)
│   │   └── components/
│   │       ├── DownloadTable.svelte
│   │       ├── UrlInputBar.svelte
│   │       ├── HistoryList.svelte
│   │       ├── SettingsForm.svelte
│   │       └── ChannelBrowser.svelte
│   └── routes/
│       ├── +layout.svelte                  Tab shell + theme provider
│       ├── +page.svelte                    Download tab
│       ├── channel/+page.svelte
│       ├── history/+page.svelte
│       └── settings/+page.svelte
└── (legacy python kept until phase 10)
```

## IPC Contract (high-level)

| Direction | Mechanism | Use |
|-----------|-----------|-----|
| FE → BE | `invoke('add_urls', {urls})` | queue ops, settings r/w, history queries, channel listing kickoff |
| BE → FE | `tauri::ipc::Channel<ProgressEvent>` per-download | high-frequency progress (downloaded_bytes, eta) |
| BE → FE | `app.emit('queue:changed', state)` | low-frequency queue state, all-finished, history-changed |
| BE → FE | `app.emit('channel:video-found', VideoInfo)` | streaming flat-playlist results |

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rust learning curve slows team | High | +1-2 weeks | Phase 01 is a full-stack spike; book time before declaring scope |
| yt-dlp.exe FB page enumeration insufficient | Medium | Medium | Phase 05 spike validates first; fallback = rquest HTML scrape |
| `rquest` impersonation insufficient for FB shortlinks | Low | Low | Module is fail-open today; fallback to plain `reqwest` |
| WebView2 missing on user machines | Low | Medium | Use `webviewInstallMode: downloadBootstrapper` in tauri.conf.json |
| ffmpeg bundle size larger than estimate | Medium | Low | Strip unused encoders; document optional system install path |
| Per-uploader outtmpl differs vs Python | Low | Low | Pre-pass with `yt-dlp -J` to fetch metadata, then build path in Rust before second invocation |
| AV false-positives on unsigned binary | Medium | Low | UPX off (already), document SmartScreen workaround, plan signing post-cutover |
| Existing user data loss | Medium | High | First-launch importer reads `~/.tiktokder/config.json` + `data/history.json` (both legacy and current paths) into new SQLite store |

## Success Criteria
- Bundle size: ≤55 MB onedir, ≤30 MB MSI installer (compressed)
- Cold start: ≤500 ms to first paint
- All 4 v1.2.0 tabs functional with feature parity
- 100% of locked-decision contracts preserved (history schema import, output tree shape, error kinds)
- ≥80% Rust unit-test coverage on ported modules; smoke E2E covers 5 critical user paths
- No Python interpreter or .pyd in shipped bundle
- Drag-drop, import/export, context menus, toasts work on Windows 10 22H2 + 11

## Open Research Questions (to resolve in Phase 01 spike)
1. **yt-dlp.exe FB page enumeration** — does `yt-dlp --flat-playlist -J facebook.com/<page>` work without browser cookies? With `--cookies-from-browser`? If neither, design rquest fallback in Phase 05.
2. **rquest crate maturity** — current version, MSRV, Chrome 131+ impersonation availability. If immature, use `reqwest` + manual JA3 (likely insufficient for FB) — accept fail-open behavior since the Python version is also fail-open.
3. **ffmpeg minimal build** — confirm gyan.dev/BtbN essentials build (~15 MB stripped) supports the codecs yt-dlp invokes (libx264 demux, aac decode, mp4 mux). Else fall back to LGPL essentials (~25 MB).
4. **Tauri 2 channel API stability** — `tauri::ipc::Channel<T>` shipped GA in Tauri 2.0 (Oct 2024) — confirm latest 2.x version still exposes it; fallback to `app.emit` per-URL events.
5. **`--cookies-from-browser` in standalone yt-dlp.exe** — confirm it works out-of-the-box in the standalone build (no Python cookies module needed).

## Cutover & Rollback
- Branch: `feat/tauri-migration`. Legacy `main` keeps Python build until Phase 10.
- Phase 10 PR: deletes Python source, replaces README, ships v2.0.0.
- Rollback: `git revert` of cutover PR + restore `tiktokder.spec` + republish v1.2.x patch line.

## Reference
- Current PyInstaller artefact size: 167.2 MB onedir, 80.2 MB zip.
- Rust target: `x86_64-pc-windows-msvc` first; macOS/Linux deferred (track in tauri.conf.json `bundle.targets`).
