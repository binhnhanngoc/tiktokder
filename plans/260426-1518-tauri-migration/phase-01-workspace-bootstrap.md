# Phase 01 — Workspace Bootstrap + Research Spike

## Context Links
- Plan: [plan.md](plan.md)
- Open research questions in plan.md → resolved here.

## Overview
- **Priority:** Critical (gates everything)
- **Status:** pending
- **Effort:** 0.5d
- Stand up the Cargo workspace, Tauri 2 + SvelteKit + Tailwind v4 scaffolding, and resolve the 5 open research questions before phase 02 starts. Spike-quality code; throwaway-acceptable.

## Key Insights
- Tauri 2.x is GA (since Oct 2024); plugins are versioned separately and live under `tauri-plugin-*`.
- SvelteKit `adapter-static` is required (Tauri serves static files; no SSR).
- Tailwind v4 ships with Vite plugin — no PostCSS config needed.
- WebView2 is preinstalled on Win10 22H2+ and Win11; `downloadBootstrapper` covers older targets.

## Requirements

### Functional
- `cargo tauri dev` opens an empty 900×600 window with title "TikTokDer" and the existing `assets/icon.ico`.
- Frontend hot-reload works.
- A trivial `invoke('ping')` round-trips a string from BE → FE.
- One sidecar `Command::new_sidecar("yt-dlp")` runs `--version` and prints the result.

### Non-functional
- Workspace builds clean on `cargo build` (release).
- `pnpm` (or `npm`) install completes; lockfile committed.
- No legacy Python files touched.

## Architecture

```
tiktokder/
├── Cargo.toml                  workspace = ["src-tauri"]
├── package.json                pnpm preferred; npm fallback
├── svelte.config.js            adapter-static, prerender = true
├── vite.config.ts              port 1420, strictPort, hmr.host = localhost
├── tailwind.config.js          content: ["./src/**/*.{html,svelte,ts}"]
├── tsconfig.json
├── src/
│   ├── app.html
│   ├── app.css                 @import "tailwindcss";
│   ├── lib/ipc.ts              ping wrapper
│   └── routes/+page.svelte     ping button
└── src-tauri/
    ├── Cargo.toml              edition = 2021, [package] tauri 2.x, plugins
    ├── tauri.conf.json         identifier "com.tiktokder.app", windows config
    ├── build.rs                tauri-build = "2"
    ├── capabilities/default.json
    ├── icons/icon.ico (copy of assets/icon.ico)
    ├── binaries/.gitkeep
    └── src/main.rs             ping command + plugin init
```

## Related Code Files

### Create
- `Cargo.toml` (workspace)
- `package.json`, `pnpm-lock.yaml` (or `package-lock.json`)
- `svelte.config.js`, `vite.config.ts`, `tailwind.config.js`, `tsconfig.json`, `postcss.config.js` (only if Tailwind v3 fallback)
- `src/app.html`, `src/app.css`, `src/lib/ipc.ts`, `src/routes/+page.svelte`, `src/routes/+layout.svelte`
- `src-tauri/Cargo.toml`, `src-tauri/build.rs`, `src-tauri/tauri.conf.json`
- `src-tauri/capabilities/default.json`
- `src-tauri/src/main.rs`, `src-tauri/src/lib.rs`
- `src-tauri/icons/icon.ico` (copy from `assets/icon.ico`)
- `.gitignore` additions: `node_modules/`, `target/`, `dist/`, `build/`, `src-tauri/binaries/*.exe`

### Read for context
- `assets/icon.ico` (copy)
- `app.py` (window title, geometry defaults — port to tauri.conf.json `windows[0]`)
- `gui/main_window.py` lines 47-49 (default 900×600)

### Do not modify
- Any existing `*.py`, `gui/*.py`, `tests`, `tiktokder.spec` — legacy stays untouched.

## Implementation Steps

### Step 1 — Init Cargo workspace
1. `cargo new --lib --name tiktokder-app src-tauri` (rename — see step 2).
2. Root `Cargo.toml`:
   ```toml
   [workspace]
   members = ["src-tauri"]
   resolver = "2"

   [workspace.package]
   version = "2.0.0-alpha.1"
   edition = "2021"
   rust-version = "1.77"
   ```
3. `src-tauri/Cargo.toml`:
   ```toml
   [package]
   name = "tiktokder"
   version.workspace = true
   edition.workspace = true

   [lib]
   name = "tiktokder_lib"
   crate-type = ["staticlib", "cdylib", "rlib"]

   [build-dependencies]
   tauri-build = { version = "2", features = [] }

   [dependencies]
   tauri = { version = "2", features = [] }
   tauri-plugin-shell = "2"
   tauri-plugin-dialog = "2"
   tauri-plugin-fs = "2"
   tauri-plugin-clipboard-manager = "2"
   serde = { version = "1", features = ["derive"] }
   serde_json = "1"
   tokio = { version = "1", features = ["full"] }
   anyhow = "1"
   thiserror = "1"
   tracing = "0.1"
   tracing-subscriber = { version = "0.3", features = ["env-filter"] }
   ```

### Step 2 — Init SvelteKit + Tailwind v4
1. `pnpm create svelte@latest .` → choose: Skeleton, TypeScript, ESLint, Prettier, Vitest, Playwright (yes for E2E later).
2. Install `@sveltejs/adapter-static`, set in `svelte.config.js`:
   ```js
   import adapter from '@sveltejs/adapter-static';
   export default {
     kit: { adapter: adapter({ fallback: 'index.html' }) },
   };
   ```
3. `+layout.ts`: `export const prerender = true; export const ssr = false;`
4. Tailwind v4: `pnpm add -D tailwindcss @tailwindcss/vite`. In `vite.config.ts`:
   ```ts
   import tailwind from '@tailwindcss/vite';
   export default { plugins: [sveltekit(), tailwind()], server: { port: 1420, strictPort: true } };
   ```
   `app.css`: `@import "tailwindcss";`
5. Tauri plugins (FE): `pnpm add @tauri-apps/api @tauri-apps/plugin-shell @tauri-apps/plugin-dialog @tauri-apps/plugin-fs @tauri-apps/plugin-clipboard-manager`.

### Step 3 — Init Tauri config
1. `pnpm add -D @tauri-apps/cli`.
2. `pnpm tauri init` (or hand-write `src-tauri/tauri.conf.json`):
   ```jsonc
   {
     "$schema": "https://schema.tauri.app/config/2",
     "productName": "TikTokDer",
     "version": "2.0.0-alpha.1",
     "identifier": "com.tiktokder.app",
     "build": {
       "beforeDevCommand": "pnpm dev",
       "beforeBuildCommand": "pnpm build",
       "devUrl": "http://localhost:1420",
       "frontendDist": "../build"
     },
     "app": {
       "windows": [{
         "title": "TikTokDer",
         "width": 900, "height": 600,
         "minWidth": 720, "minHeight": 480,
         "resizable": true,
         "fileDropEnabled": true
       }],
       "security": { "csp": null }
     },
     "bundle": {
       "active": true,
       "targets": ["nsis"],
       "icon": ["icons/icon.ico"],
       "externalBin": ["binaries/yt-dlp", "binaries/ffmpeg"],
       "windows": {
         "webviewInstallMode": { "type": "downloadBootstrapper" }
       }
     }
   }
   ```
3. Capability `src-tauri/capabilities/default.json`:
   ```json
   {
     "identifier": "default",
     "windows": ["main"],
     "permissions": [
       "core:default",
       "shell:default",
       "shell:allow-execute",
       { "identifier": "shell:allow-spawn", "allow": [{"name": "binaries/yt-dlp", "sidecar": true}, {"name": "binaries/ffmpeg", "sidecar": true}] },
       "dialog:default", "dialog:allow-open", "dialog:allow-save",
       "fs:default", "fs:allow-read-file",
       "clipboard-manager:default"
     ]
   }
   ```
4. `src-tauri/build.rs`: `fn main() { tauri_build::build() }`.

### Step 4 — Sidecar binary smoke test
1. Download yt-dlp.exe (latest stable, e.g. 2025.x.x) → `src-tauri/binaries/yt-dlp-x86_64-pc-windows-msvc.exe`.
2. Add `binaries/yt-dlp-x86_64-pc-windows-msvc.exe` to `.gitignore` (binary; download via build script in phase 09).
3. Smoke command in `src-tauri/src/lib.rs`:
   ```rust
   #[tauri::command]
   async fn ping() -> String { "pong".into() }

   #[tauri::command]
   async fn ytdlp_version(app: tauri::AppHandle) -> Result<String, String> {
       use tauri_plugin_shell::ShellExt;
       let out = app.shell()
           .sidecar("yt-dlp").map_err(|e| e.to_string())?
           .args(["--version"])
           .output().await.map_err(|e| e.to_string())?;
       Ok(String::from_utf8_lossy(&out.stdout).trim().into())
   }

   pub fn run() {
       tauri::Builder::default()
           .plugin(tauri_plugin_shell::init())
           .plugin(tauri_plugin_dialog::init())
           .plugin(tauri_plugin_fs::init())
           .plugin(tauri_plugin_clipboard_manager::init())
           .invoke_handler(tauri::generate_handler![ping, ytdlp_version])
           .run(tauri::generate_context!())
           .expect("failed to run tauri app");
   }
   ```
4. `src-tauri/src/main.rs`: `fn main() { tiktokder_lib::run() }`.

### Step 5 — FE smoke
1. `src/lib/ipc.ts`:
   ```ts
   import { invoke } from '@tauri-apps/api/core';
   export const ping = () => invoke<string>('ping');
   export const ytdlpVersion = () => invoke<string>('ytdlp_version');
   ```
2. `src/routes/+page.svelte`: button calls `ping()` and `ytdlpVersion()`, shows results. Confirms the round-trip + sidecar end-to-end.

### Step 6 — Research spike (block phase 02 until resolved)
Document each finding in `plans/260426-1518-tauri-migration/research/spike-results.md`:

1. **FB page enumeration via yt-dlp.exe** — run on a known public FB page:
   `yt-dlp --flat-playlist -J --no-warnings https://www.facebook.com/<known-page>` and `... --cookies-from-browser chrome ...`. Record: works/fails, # entries returned, time, error if any.
2. **rquest crate** — `cargo add rquest` in scratch dir; verify it builds, check latest Chrome impersonation profile available; HEAD request against `fb.watch/<id>` follows-no-auto-redirect, reads Location.
3. **ffmpeg minimal Windows build** — download `ffmpeg-essentials_build` from gyan.dev; verify `ffmpeg.exe -codecs | findstr h264` shows decode, `aac` shows decode/encode, `mov,mp4,m4a` shows mux. Record stripped size.
4. **Tauri 2 Channel API** — confirm `tauri::ipc::Channel<T>` is exposed in the version of `tauri = "2"` resolved. Test minimal `Channel<u32>` send-from-command pattern.
5. **`--cookies-from-browser`** — confirm `yt-dlp.exe --cookies-from-browser chrome --simulate <url>` produces no Python ImportError and yields cookies.

## Todo
- [ ] Cargo workspace + Tauri scaffold building clean
- [ ] SvelteKit + Tailwind v4 hot-reload working
- [ ] Tauri 2 plugins installed + capability JSON valid
- [ ] yt-dlp.exe placed in `src-tauri/binaries/`, sidecar invoke smoke green
- [ ] All 5 spike findings recorded in `research/spike-results.md`
- [ ] If FB page enumeration fails → add a phase-05 fallback note to plan.md before unblocking phase 02

## Success Criteria
- `pnpm tauri dev` opens window, button shows "pong" and yt-dlp version string.
- `pnpm tauri build` produces an NSIS installer (smoke build, may be unsigned).
- Spike doc resolved 5/5 questions.

## Risk Assessment
- **Rust toolchain version mismatch.** Pin via `rust-toolchain.toml`: stable, MSRV 1.77.
- **WebView2 missing on dev machine.** Installer auto-fetches; for dev, prompt user to install Edge.
- **Tailwind v4 still moving fast.** If breaking, fall back to v3 with PostCSS.
- **rquest unavailable / abandoned.** Document and switch Phase 02 to plain `reqwest` (TLS impersonation lost = matches current `unknown` fallback).

## Security
- Capability ACL is restrictive: only sidecar invocations whitelisted. No `shell:allow-execute` of arbitrary commands beyond the two sidecars.
- CSP set to `null` for now — tighten in Phase 09.

## Next Steps
- Phase 02 starts only after spike-results.md exists and confirms decisions in plan.md.
