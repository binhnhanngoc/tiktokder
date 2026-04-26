# Phase 09 — Bundling, sidecar fetch, ffmpeg, installer

## Context Links
- Plan: [plan.md](plan.md)
- Source: `tiktokder.spec`, `build.py` (PyInstaller pipeline being replaced)
- Phases 01-08: app feature-complete

## Overview
- **Priority:** High
- **Status:** pending
- **Effort:** 1d
- Produce shippable Windows installer + portable zip. Wire a build script that fetches yt-dlp.exe + ffmpeg essentials, places them under `src-tauri/binaries/` with the correct triple suffix, then runs `tauri build`. Targets ≤55 MB onedir, ≤30 MB MSI/NSIS installer.

## Key Insights
- Sidecar binaries are NOT committed to git (large + version-pinned via SHA). Build script downloads on-demand.
- Tauri requires sidecar files named with the host target triple, e.g. `yt-dlp-x86_64-pc-windows-msvc.exe`. Same convention for `ffmpeg`.
- Tauri 2 default Windows installer is NSIS. MSI (WiX) optional.
- Set `webviewInstallMode: downloadBootstrapper` so older Win10 < 22H2 users still install WebView2.
- ffmpeg essentials build (gyan.dev): ~80 MB unstripped → strip to ~20 MB by deleting `presets/`, `doc/`, and using a "ffmpeg-only" subset (drop `ffprobe` if unused — yt-dlp uses both for some formats; keep both).

## Requirements
- One command (`pnpm tauri build` after first-run setup) produces:
  - NSIS installer `.exe` in `src-tauri/target/release/bundle/nsis/` (≤30 MB).
  - Portable folder `src-tauri/target/release/` containing `tiktokder.exe` + WebView2 + sidecars (≤55 MB).
- Reproducible: SHA-pinned sidecars; build script verifies hashes.
- Icon set in `.exe` (TikTokDer icon).
- Version in window title and About modal matches package.json.

## Architecture

### Build script: `scripts/fetch-binaries.mjs` (Node)

```js
// Pinned versions + SHA256
const YTDLP = {
  url: 'https://github.com/yt-dlp/yt-dlp/releases/download/2025.10.15/yt-dlp.exe',
  sha256: '<pinned>',
  outName: 'yt-dlp-x86_64-pc-windows-msvc.exe',
};
const FFMPEG = {
  url: 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
  sha256: '<pinned>',
  outName: 'ffmpeg-x86_64-pc-windows-msvc.exe',
};

// Download, sha-verify, extract ffmpeg.exe out of the zip,
// place at src-tauri/binaries/<outName>. Skip if file already present and matches sha.
```

Run via `pnpm prebuild` hook (`package.json: "scripts": { "prebuild": "node scripts/fetch-binaries.mjs", "tauri": "tauri" }`).

### Updated `tauri.conf.json` bundle section
```jsonc
{
  "bundle": {
    "active": true,
    "targets": ["nsis"],
    "identifier": "com.tiktokder.app",
    "icon": ["icons/32x32.png", "icons/128x128.png", "icons/icon.icns", "icons/icon.ico"],
    "externalBin": ["binaries/yt-dlp", "binaries/ffmpeg"],
    "resources": [],
    "copyright": "MIT - See LICENSE",
    "category": "Utility",
    "shortDescription": "Batch download TikTok and Facebook videos",
    "longDescription": "Cross-platform desktop app for batch-downloading TikTok and Facebook videos without watermarks.",
    "windows": {
      "webviewInstallMode": { "type": "downloadBootstrapper", "silent": false },
      "nsis": {
        "installMode": "currentUser",
        "displayLanguageSelector": false,
        "installerIcon": "icons/icon.ico"
      },
      "wix": null
    }
  }
}
```

### Pipeline
```
pnpm install               (FE deps)
pnpm prebuild              (fetch & verify sidecars; idempotent)
pnpm tauri build --release (build Rust + Svelte + bundle)
↓
src-tauri/target/release/bundle/nsis/TikTokDer_2.0.0-alpha.1_x64-setup.exe
src-tauri/target/release/tiktokder.exe + WebView2Loader.dll + binaries/...
```

### Portable zip step
Add `scripts/zip-portable.mjs` that takes the `target/release/` folder and produces `TikTokDer-portable-2.0.0-alpha.1.zip` excluding `*.pdb` / build artifacts.

## Related Code Files

### Create
- `scripts/fetch-binaries.mjs`
- `scripts/zip-portable.mjs`
- `src-tauri/icons/{32x32.png,128x128.png,icon.ico,icon.icns}` (generate from `assets/icon.ico` via ImageMagick or Tauri's icon tool)
- `LICENSE` (MIT — copy from existing repo if present, else create)
- `.gitattributes` updates: `binaries/* binary` (already in `.gitignore`).

### Update
- `src-tauri/tauri.conf.json` — bundle config above.
- `package.json` — scripts:
  ```json
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "prebuild": "node scripts/fetch-binaries.mjs",
    "tauri": "tauri",
    "tauri:dev": "tauri dev",
    "tauri:build": "pnpm prebuild && tauri build",
    "portable": "pnpm tauri:build && node scripts/zip-portable.mjs"
  }
  ```
- `README.md` (later in phase 10) — build instructions.

### Read for context
- `tiktokder.spec` (current PyInstaller spec — for icon paths only).
- `build.py` (current build pipeline — for license/cleanup steps to mirror).

## Implementation Steps

### Step 1 — Icon set
1. Generate icons from `assets/icon.ico`:
   ```
   tauri icon assets/icon.ico
   ```
   Outputs to `src-tauri/icons/`.

### Step 2 — Sidecar fetch script
1. Implement `scripts/fetch-binaries.mjs` with:
   - URL + pinned SHA256 for yt-dlp and ffmpeg essentials.
   - Streaming download with progress to stderr.
   - SHA verification (`crypto.createHash('sha256')`).
   - Extract ffmpeg.exe out of the essentials zip; discard rest.
   - Atomic move into `src-tauri/binaries/`.
   - Idempotent: if file exists with matching SHA, skip.
2. Pin versions chosen by Phase 01 spike. Document update procedure in script header.

### Step 3 — Bundle config
1. Apply the JSON above.
2. Test: `pnpm tauri build` produces `bundle/nsis/*.exe`.
3. Inspect installed app: opens, sidecars run.

### Step 4 — WebView2 strategy
1. `downloadBootstrapper` for first installer cut.
2. Document size impact (~2 MB bootstrapper + auto-fetch on install).
3. Note `embedBootstrapper` would pre-include WebView2 runtime (~120 MB) — not used.

### Step 5 — Portable zip
1. `scripts/zip-portable.mjs`: `archiver` npm package; zip `target/release/` excluding `bundle/`, `deps/`, `*.pdb`, `*.exp`.
2. Output: `dist/TikTokDer-portable-<version>.zip`.

### Step 6 — Size budget verification
After `pnpm tauri:build` + `pnpm portable`:
- Installer ≤ 30 MB (target).
- Portable zip ≤ 55 MB compressed; folder ≤ 75 MB uncompressed.
- If over budget, identify largest contributors via `du -sh src-tauri/target/release/*` and trim.

### Step 7 — Smoke install
1. Run NSIS installer on a clean Windows VM (or fresh user profile).
2. Confirm WebView2 prompts/installs if missing.
3. Launch app; complete one TikTok download end-to-end.
4. Uninstall via Add/Remove Programs.

## Todo
- [ ] Icon set generated, present in src-tauri/icons/
- [ ] `fetch-binaries.mjs` downloads + verifies + places binaries
- [ ] `tauri build` produces NSIS installer
- [ ] Installer launches, sidecars run, download succeeds
- [ ] Portable zip script outputs valid archive
- [ ] Total installer ≤ 30 MB; portable ≤ 55 MB
- [ ] WebView2 download bootstrapper works on a fresh VM

## Success Criteria
- Two artefacts produced from a single command sequence.
- Installer under target size.
- Smoke install + uninstall clean.
- App version + icon shown correctly in Add/Remove Programs.

## Risk Assessment
- **gyan.dev URL changes / build no longer "release-essentials".** Mitigation: pin a specific date snapshot URL or mirror via GitHub release of our own.
- **AV flags unsigned binary.** Document SmartScreen "More info → Run anyway" in README; sign post-cutover.
- **NSIS CRT bundling missing on stripped Windows.** `downloadBootstrapper` covers WebView2; CRT redistributable is included by Tauri's NSIS template by default.
- **Sidecar SHA drift on re-fetch.** If yt-dlp release URL is replaced (rare), update script + commit new SHA.
- **ffmpeg essentials missing codec.** If audio extraction fails post-bundle, switch to LGPL essentials (~25 MB, +5 MB over budget).

## Security
- SHA-verify sidecars before bundling.
- Strip debug symbols (`*.pdb`) from portable zip to avoid leaking internals.
- NSIS install mode `currentUser` — no admin required, no system-wide writes.

## Next Steps
- Phase 10 runs the full test matrix and performs the cutover (delete Python, update README, ship v2.0.0).
