# Tauri 2 + SvelteKit Architecture Research Report

**Date:** 2026-04-26 | **Status:** DONE | **Focus:** Tauri 2.0 stable → production desktop app migration

---

## 1. Project Layout (Tauri 2.x + SvelteKit + Vite + Tailwind + TypeScript)

### Directory Tree
```
tiktokder/
├── package.json                 # npm scripts, @svelte/* @tauri-apps/*
├── pnpm-lock.yaml              # (or package-lock.json)
├── svelte.config.js            # adapter-static
├── vite.config.ts              # plugins: sveltekit, tailwindcss
├── tailwind.config.ts          # @theme CSS, dark mode
├── tsconfig.json
├── src/
│   ├── app.html                # root HTML (script load Tauri API)
│   ├── routes/
│   │   ├── +page.svelte
│   │   ├── +layout.svelte
│   │   └── +layout.ts          # export const ssr = false
│   └── lib/
│       ├── components/
│       ├── stores/
│       └── utils/
├── build/                      # SvelteKit output (→ frontendDist)
├── src-tauri/                  # Rust backend
│   ├── Cargo.toml              # workspace, tauri v2.x
│   ├── tauri.conf.json         # dev + prod config
│   ├── src/
│   │   ├── lib.rs             # #[tauri::command] handlers
│   │   ├── main.rs            # fn main()
│   │   └── commands/          # modular command files
│   ├── capabilities/
│   │   └── default.json       # permissions (ACL)
│   ├── icons/
│   ├── binaries/
│   │   └── yt-dlp-x86_64-pc-windows-msvc.exe  # sidecar
│   └── build.rs               # optional: Tauri build script
└── .env.example               # (no actual .env in git)
```

### Cargo.toml Root (Optional Workspace)
```toml
[workspace]
members = ["src-tauri"]
resolver = "2"

[workspace.package]
version = "1.0.0"
edition = "2021"
```

### Cargo.toml (src-tauri/)
```toml
[package]
name = "tiktokder"
version.workspace = true
edition.workspace = true

[build-dependencies]
tauri-build = "2.x"

[dependencies]
tauri = { version = "2.x", features = ["shell", "macos-private-api"] }
tauri-plugin-shell = "2.x"
tauri-plugin-dialog = "2.x"
tauri-plugin-fs = "2.x"
tauri-plugin-clipboard-manager = "2.x"
tauri-plugin-store = "2.x"
tauri-plugin-process = "2.x"
tauri-plugin-theme = "2.x"

tokio = { version = "1.35", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
anyhow = "1.0"
thiserror = "1.0"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
dirs = "5.0"
regex = "1.10"
rusqlite = { version = "0.31", features = ["bundled"] }
# OR for async SQLite: sqlx = { version = "0.7", features = ["sqlite", "tokio-native-tls"] }
slug = "0.1"
```

### tauri.conf.json (Minimal Dev)
```json
{
  "productName": "TikTok & Facebook Downloader",
  "version": "2.0.0",
  "identifier": "com.tiktokder.app",
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devPath": "http://localhost:5173",
    "frontendDist": "../build"
  },
  "app": {
    "windows": [
      {
        "title": "TikTok & Facebook Downloader",
        "width": 1200,
        "height": 800,
        "minWidth": 600,
        "minHeight": 400,
        "resizable": true,
        "fullscreen": false,
        "focus": true,
        "visible": true,
        "decorations": true,
        "theme": null,
        "dragDropEnabled": true,
        "fileDropEnabled": true
      }
    ],
    "security": {
      "csp": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';"
    }
  },
  "bundle": {
    "active": true,
    "targets": ["nsis", "msi", "app"],
    "externalBin": ["binaries/yt-dlp-x86_64-pc-windows-msvc"],
    "windows": {
      "certificateThumbprint": null,
      "digestAlgorithm": "sha256",
      "signingIdentity": null,
      "timestampUrl": "",
      "nsis": {
        "template": null,
        "diffInstallers": true,
        "installerIcon": "../icons/icon.ico",
        "headerImage": null,
        "sidebarImage": null,
        "installerLanguages": ["en-US"],
        "shortcutLanguages": []
      },
      "wix": null,
      "webviewInstallMode": "downloadBootstrapper"
    }
  },
  "plugins": {
    "shell": {
      "scope": ["shell:allow-execute", "shell:allow-spawn", "shell:allow-kill"]
    },
    "dialog": {
      "scope": ["dialog:allow-open", "dialog:allow-save"]
    },
    "fs": {
      "scope": ["fs:allow-read", "fs:allow-write", "fs:allow-mkdir", "fs:allow-remove"]
    },
    "clipboard-manager": {
      "scope": ["clipboard-manager:allow-read-text", "clipboard-manager:allow-write-text"]
    },
    "store": {}
  }
}
```

### tauri.conf.json (Production)
```json
{
  "bundle": {
    "windows": {
      "nsis": {
        "installer": "download",
        "shortcutLanguages": ["en-US"]
      },
      "webviewInstallMode": "downloadBootstrapper"
    }
  }
}
```

### package.json (Scripts)
```json
{
  "name": "tiktokder",
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "tauri": "cargo tauri",
    "tauri:dev": "cargo tauri dev",
    "tauri:build": "cargo tauri build",
    "tauri:build:no-bundle": "cargo tauri build --no-bundle",
    "lint": "eslint . && prettier --check .",
    "format": "prettier --write .",
    "test": "vitest"
  },
  "dependencies": {
    "@tauri-apps/api": "^2.0",
    "@tauri-apps/plugin-shell": "^2.0",
    "@tauri-apps/plugin-dialog": "^2.0",
    "@tauri-apps/plugin-fs": "^2.0",
    "@tauri-apps/plugin-clipboard-manager": "^2.0",
    "@tauri-apps/plugin-store": "^2.0",
    "@tauri-apps/plugin-process": "^2.0",
    "@tauri-apps/plugin-theme": "^2.0",
    "svelte": "^5.x",
    "lucide-svelte": "^0.x"
  },
  "devDependencies": {
    "@sveltejs/adapter-static": "^3.x",
    "@sveltejs/kit": "^2.x",
    "@sveltejs/vite-plugin-svelte": "^3.x",
    "@tailwindcss/vite": "^4.x",
    "tailwindcss": "^4.x",
    "typescript": "^5.x",
    "vite": "^5.x"
  }
}
```

### vite.config.ts
```typescript
import { defineConfig } from 'vite'
import { sveltekitVite } from '@sveltejs/kit/vite'
import { sveltePreprocess } from 'svelte-preprocess'
import tailwindcss from 'tailwindcss'
import autoprefixer from 'autoprefixer'

export default defineConfig({
  plugins: [sveltekitVite()],
  server: {
    port: 5173,
    strictPort: false
  },
  css: {
    postcss: {
      plugins: [tailwindcss(), autoprefixer()]
    }
  }
})
```

### svelte.config.js
```javascript
import adapter from '@sveltejs/adapter-static'
import { vitePreprocess } from '@sveltejs/kit/vite'

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      fallback: 'index.html'
    }),
    paths: {
      base: process.env.TAURI_PLATFORM ? '' : ''
    }
  }
}
```

### tailwind.config.ts (v4)
```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {}
  },
  plugins: [],
  darkMode: 'class'
} satisfies Config
```

### +layout.ts (SPA mode)
```typescript
export const ssr = false
export const prerender = false
```

---

## 2. Sidecar Binaries (yt-dlp.exe)

### Platform Naming & Directory Structure

```
src-tauri/binaries/
├── yt-dlp-x86_64-pc-windows-msvc.exe     # Windows (main target)
├── yt-dlp-aarch64-apple-darwin           # macOS ARM64 (defer)
├── yt-dlp-x86_64-unknown-linux-gnu       # Linux x86_64 (defer)
└── .gitignore                             # *.exe, binaries/ in dist only
```

**Naming convention:** `{name}-{target-triple}.{ext}`
- Windows: `yt-dlp-x86_64-pc-windows-msvc.exe`
- macOS ARM64: `yt-dlp-aarch64-apple-darwin` (no .exe)
- Linux: `yt-dlp-x86_64-unknown-linux-gnu` (no .exe)

Find your target: `rustc --print host-tuple`

### tauri.conf.json Bundle Configuration
```json
{
  "bundle": {
    "externalBin": [
      "binaries/yt-dlp"
    ],
    "windows": {
      "webviewInstallMode": "downloadBootstrapper"
    }
  }
}
```

Relative paths are **from `src-tauri/` directory**. Tauri resolves `yt-dlp` to the platform-specific binary at build time.

### Rust: Spawning the Sidecar
```rust
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

#[tauri::command]
async fn download_video(
    app: tauri::AppHandle,
    url: String,
    output_dir: String,
) -> Result<String, String> {
    let (mut rx, mut child) = app
        .shell()
        .sidecar("yt-dlp")
        .map_err(|e| e.to_string())?
        .args([
            "--no-warnings",
            "-f", "best",
            "-o", &format!("{}/%(title)s.%(ext)s", output_dir),
            &url
        ])
        .spawn()
        .map_err(|e| format!("Failed to spawn yt-dlp: {}", e))?;

    let mut output = String::new();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    // Log or emit progress event
                    output.push_str(&line);
                    output.push('\n');
                }
                CommandEvent::Stderr(err) => {
                    eprintln!("yt-dlp stderr: {}", err);
                }
                CommandEvent::Terminated(_) => break,
                _ => {}
            }
        }
    });

    Ok("Download started".to_string())
}
```

### JavaScript: Spawning from Frontend
```typescript
import { Command } from '@tauri-apps/plugin-shell'

const command = new Command('yt-dlp', [
  '--no-warnings',
  '-f', 'best',
  '-o', `${outputDir}/%(title)s.%(ext)s`,
  url
])

const output = await command.execute()
console.log(output.stdout)
```

### Capabilities (permissions)
```json
{
  "permissions": [
    "shell:allow-execute",
    "shell:allow-spawn",
    "shell:allow-kill",
    "shell:allow-open"
  ]
}
```

---

## 3. IPC Patterns for Download Progress Streaming

### Pattern A: High-Frequency Events (Progress Updates)

Use **`Channel<T>`** for streaming progress; don't emit events per byte.

```rust
#[derive(Debug, serde::Serialize, Clone)]
pub enum DownloadEvent {
    Started { url: String, filename: String },
    Progress { downloaded: u64, total: u64, percentage: f64 },
    Finished { path: String, size: u64 },
    Failed { error: String },
}

#[tauri::command]
async fn download_with_progress(
    url: String,
    output_dir: String,
    channel: tauri::ipc::Channel<DownloadEvent>,
) -> Result<(), String> {
    let _ = channel.send(DownloadEvent::Started {
        url: url.clone(),
        filename: "video.mp4".to_string(),
    }).await;

    // Simulate progress (real: parse yt-dlp stdout)
    for i in 0..100 {
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
        let _ = channel.send(DownloadEvent::Progress {
            downloaded: i * 1024,
            total: 100 * 1024,
            percentage: i as f64,
        }).await;
    }

    let _ = channel.send(DownloadEvent::Finished {
        path: format!("{}/video.mp4", output_dir),
        size: 102400,
    }).await;

    Ok(())
}
```

**Frontend (Svelte):**
```svelte
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core'

  let progress = 0
  let status = 'Idle'

  async function startDownload() {
    try {
      const unsub = await invoke<void>('download_with_progress', {
        url: 'https://...',
        outputDir: '/downloads'
      }, (event) => {
        const data = event.payload as any
        if (data.Started) status = 'Starting...'
        else if (data.Progress) progress = data.Progress.percentage
        else if (data.Finished) status = 'Done!'
      })
    } catch (e) {
      console.error('Download failed:', e)
    }
  }
</script>

<button on:click={startDownload}>Start Download</button>
<p>{status}</p>
<progress value={progress} max={100}></progress>
```

### Pattern B: Low-Frequency Events (Queue State)

Use **`Window::emit`** for discrete state changes (started/paused/finished).

```rust
#[tauri::command]
fn start_download(window: tauri::Window, url: String) -> Result<(), String> {
    window.emit("download:started", json!({ "url": url, "timestamp": chrono::Utc::now() }))
        .map_err(|e| e.to_string())?;
    
    // Start download in background
    tauri::async_runtime::spawn(async move {
        // ... download logic ...
        window.emit("download:completed", json!({ "url": url })).ok();
    });

    Ok(())
}
```

**Frontend:**
```svelte
<script lang="ts">
  import { listen } from '@tauri-apps/api/event'

  onMount(async () => {
    const unlistenStarted = await listen('download:started', (event) => {
      console.log('Download started:', event.payload)
    })

    const unlistenCompleted = await listen('download:completed', (event) => {
      console.log('Download completed:', event.payload)
    })

    return () => {
      unlistenStarted()
      unlistenCompleted()
    }
  })
</script>
```

### Pattern C: Terminal Events (Per-Download Lifecycle)

```rust
#[derive(Debug, serde::Serialize, Clone)]
pub enum DownloadStatus {
    Queued,
    Downloading,
    Paused,
    Completed,
    Failed { error: String },
}

#[tauri::command]
async fn enqueue_download(
    app: tauri::AppHandle,
    url: String,
    output_dir: String,
) -> Result<String, String> {
    let download_id = uuid::Uuid::new_v4().to_string();
    let id_clone = download_id.clone();
    let app_clone = app.clone();

    tauri::async_runtime::spawn(async move {
        app_clone.emit_all("download:status", json!({
            "id": id_clone.clone(),
            "status": "Downloading"
        })).ok();

        // Call sidecar, stream stdout
        // On completion:
        app_clone.emit_all("download:status", json!({
            "id": id_clone,
            "status": "Completed",
            "path": "/downloads/video.mp4"
        })).ok();
    });

    Ok(download_id)
}
```

---

## 4. State Management in Rust

### Approach 1: Simple Mutex<T> (no Arc needed)

```rust
#[derive(Clone, serde::Serialize, serde::Deserialize)]
pub struct AppState {
    pub downloads: Vec<DownloadRecord>,
    pub settings: AppSettings,
    pub history: Vec<HistoryEntry>,
}

#[tauri::command]
fn get_downloads(state: tauri::State<std::sync::Mutex<AppState>>) -> Result<Vec<DownloadRecord>, String> {
    let app_state = state.lock().map_err(|e| e.to_string())?;
    Ok(app_state.downloads.clone())
}

#[tauri::command]
fn add_download(
    state: tauri::State<std::sync::Mutex<AppState>>,
    record: DownloadRecord,
) -> Result<(), String> {
    let mut app_state = state.lock().map_err(|e| e.to_string())?;
    app_state.downloads.push(record);
    Ok(())
}

// In main.rs:
let state = std::sync::Mutex::new(AppState {
    downloads: vec![],
    settings: AppSettings::default(),
    history: vec![],
});

tauri::Builder::default()
    .manage(state)
    .invoke_handler(tauri::generate_handler![get_downloads, add_download])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
```

### Approach 2: Tokio Async Mutex (for async I/O resources)

```rust
use tokio::sync::Mutex as AsyncMutex;

pub struct AppState {
    pub db: Arc<tokio::sync::Mutex<rusqlite::Connection>>,
    pub downloads: Arc<tokio::sync::Mutex<Vec<DownloadRecord>>>,
}

#[tauri::command]
async fn query_history(
    state: tauri::State<'_, AppState>,
) -> Result<Vec<HistoryEntry>, String> {
    let db = state.db.lock().await;
    // Query database
    Ok(vec![])
}
```

### Approach 3: Global State (Avoid if possible)

```rust
use std::sync::OnceLock;

static APP_STATE: OnceLock<std::sync::Mutex<AppState>> = OnceLock::new();

pub fn init_state() {
    let _ = APP_STATE.set(std::sync::Mutex::new(AppState::default()));
}

pub fn get_app_state() -> &'static std::sync::Mutex<AppState> {
    APP_STATE.get().expect("State not initialized")
}
```

**Recommendation:** Use `tauri::State<T>` + `std::sync::Mutex<T>` unless you have async DB operations, then `tokio::sync::Mutex<T>`.

---

## 5. Bundling (Installers, Portable, Size Optimization)

### tauri.conf.json Bundle Targets
```json
{
  "bundle": {
    "active": true,
    "targets": ["nsis", "msi", "app"],
    "externalBin": ["binaries/yt-dlp"],
    "windows": {
      "nsis": {
        "installerIcon": "../icons/icon.ico",
        "headerImage": null,
        "sidebarImage": null,
        "template": null,
        "diffInstallers": true,
        "installerLanguages": ["en-US"],
        "shortcutLanguages": []
      },
      "wix": {
        "license": null,
        "lightOptions": [],
        "candle": []
      },
      "webviewInstallMode": "downloadBootstrapper",
      "certificateThumbprint": null,
      "signingIdentity": null,
      "timestampUrl": ""
    }
  }
}
```

### Bundle Formats

| Format | Size | When | Command |
|--------|------|------|---------|
| **NSIS** (`.exe` installer) | ~8–12 MB | Default, best for users | `cargo tauri build` |
| **MSI** (WiX, `.msi`) | ~10–14 MB | Enterprise/Windows Update | `cargo tauri build --target x86_64-pc-windows-msvc` |
| **APP** (portable `.zip`) | ~5–8 MB | Portable/USB deployments | `cargo tauri build` (includes zip) |
| **No bundle** (debug) | — | Development | `cargo tauri build --no-bundle` |

### WebView2 Install Modes

| Mode | Size Overhead | Use Case |
|------|---------------|----------|
| `downloadBootstrapper` | 1.8 MB installer | Default, requires internet at install |
| `embedBootstrapper` | 2–3 MB installer | Better Win7 compat, no internet required |
| `offlineInstaller` | 127 MB installer | Air-gapped environments (Microsoft Store) |
| `skip` | None | Assume WebView2 already installed (risky) |

**Recommendation:** Stick with `downloadBootstrapper` for web distribution.

### Size Optimization

- **Disable debug symbols:** `[profile.release] strip = true`
- **Disable LTO if too slow:** `lto = false`
- **Svelte bundles:** Svelte runtime already ~30 KB; Tailwind v4 adds ~15–20 KB (tree-shaking).
- **Typical baseline (no sidecar):**
  - Rust binary: ~3–5 MB
  - WebView2 stub: ~200 KB
  - Frontend assets: ~500 KB–2 MB
  - **Total before sidecar: ~5–8 MB**
- **With yt-dlp sidecar (bundled):** +40–50 MB

### Build Command Reference
```bash
# Development (debug, no bundle)
cargo tauri dev

# Build NSIS + MSI + portable ZIP
cargo tauri build

# Build x86_64 only (multi-arch deferrable)
cargo tauri build --target x86_64-pc-windows-msvc

# Build no bundle (test frontend only)
cargo tauri build --no-bundle

# Build release with optimizations
cargo tauri build --release
```

---

## 6. Drag-and-Drop + File Input

### tauri.conf.json Configuration
```json
{
  "app": {
    "windows": [
      {
        "dragDropEnabled": true,
        "fileDropEnabled": true
      }
    ]
  }
}
```

### Rust Event Handler
```rust
use tauri::menu::Menu;
use tauri::window::WindowBuilder;

let app = tauri::Builder::default()
    .on_window_event(|window, event| match event {
        tauri::WindowEvent::FileDrop(event) => {
            match event {
                tauri::window::FileDrop::Dropped(paths) => {
                    for path in paths {
                        println!("File dropped: {:?}", path);
                        let _ = window.emit("files:dropped", json!({
                            "paths": vec![path]
                        }));
                    }
                }
                tauri::window::FileDrop::Hover(paths) => {
                    println!("Hovering: {:?}", paths);
                }
                tauri::window::FileDrop::Cancelled => {
                    println!("Drop cancelled");
                }
            }
        }
        _ => {}
    })
    .build(tauri::generate_context!())
    .expect("error while running tauri application");
```

### Svelte Drop Zone
```svelte
<script lang="ts">
  import { listen } from '@tauri-apps/api/event'

  let isDragging = false
  let droppedUrls: string[] = []

  onMount(async () => {
    const unlisten = await listen<{ paths: string[] }>('files:dropped', (event) => {
      const files = event.payload.paths
      
      // Parse .txt files or URLs
      for (const file of files) {
        if (file.endsWith('.txt')) {
          // Read file and extract URLs
          const content = await readFile(file)
          const urls = content.split('\n').filter(line => line.startsWith('http'))
          droppedUrls.push(...urls)
        } else if (file.startsWith('http')) {
          droppedUrls.push(file)
        }
      }
    })

    return () => unlisten()
  })

  function handleDragOver(e: DragEvent) {
    e.preventDefault()
    isDragging = true
  }

  function handleDragLeave() {
    isDragging = false
  }
</script>

<div 
  class="drop-zone {isDragging ? 'active' : ''}"
  on:dragover={handleDragOver}
  on:dragleave={handleDragLeave}
>
  Drop URLs or .txt files here
</div>

{#each droppedUrls as url}
  <p>{url}</p>
{/each}
```

### Clipboard (Paste URLs)
```rust
use tauri_plugin_clipboard_manager::ClipboardExt;

#[tauri::command]
async fn paste_url(app: tauri::AppHandle) -> Result<String, String> {
    let clipboard_text = app
        .clipboard()
        .read_text()
        .await
        .map_err(|e| e.to_string())?;
    
    Ok(clipboard_text.unwrap_or_default())
}
```

---

## 7. Window / Theme / Menu

### Window Configuration
```json
{
  "app": {
    "windows": [
      {
        "title": "TikTok & Facebook Downloader",
        "width": 1200,
        "height": 800,
        "minWidth": 600,
        "minHeight": 400,
        "resizable": true,
        "fullscreen": false,
        "focus": true,
        "decorations": true,
        "transparent": false,
        "theme": null,
        "dragDropEnabled": true,
        "fileDropEnabled": true
      }
    ]
  }
}
```

### Theme Detection & Switching (Tauri 2)

**Using `tauri-plugin-theme`:**
```rust
// Cargo.toml
tauri-plugin-theme = "2.x"

// Use in frontend:
```

```typescript
import { theme } from '@tauri-apps/plugin-theme'

const currentTheme = await theme.getTheme() // 'light' | 'dark' | null
await theme.setTheme('dark')

// Listen to OS theme changes:
const unlisten = await theme.onThemeChanged((newTheme) => {
  console.log('Theme changed to:', newTheme)
})
```

**Tailwind Dark Mode (Paired with Theme Plugin):**
```html
<!-- In app.html or layout: -->
<script>
  if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
</script>
```

```typescript
// Svelte store for theme:
// stores/theme.ts
import { writable } from 'svelte/store'

export const theme = writable<'light' | 'dark'>('light')

theme.subscribe((value) => {
  localStorage.theme = value
  if (value === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
})
```

---

## 8. WebView2 Distribution (Windows)

### Overview
Tauri relies on **WebView2** (Edge browser component). You have 4 options for distribution:

| Option | Size | Use Case |
|--------|------|----------|
| `downloadBootstrapper` (default) | 1.8 MB installer | Internet available at install time |
| `embedBootstrapper` | 2–3 MB installer | Limited internet; better Win7 |
| `offlineInstaller` | 127 MB installer | Air-gapped; Microsoft Store required |
| `skip` | 0 | Assume pre-installed (risky) |

**For this project:** Use `downloadBootstrapper` (default). Tauri automatically downloads the WebView2 runtime during first install if missing.

### Configuration
```json
{
  "bundle": {
    "windows": {
      "webviewInstallMode": "downloadBootstrapper"
    }
  }
}
```

---

## 9. Tauri 2 vs Tauri 1: Key Migration Differences

### Breaking Changes

| Area | Tauri 1 | Tauri 2 |
|------|---------|---------|
| **Core API Shape** | Monolithic | Modular (plugins) |
| **CLI Config** | `tauri > cli` | `plugins > cli` |
| **Allowlist** | `tauri > allowlist > { fs, shell, ... }` | **Removed**; use Capabilities/ACL |
| **Clipboard** | `@tauri-apps/api/clipboard` | `@tauri-apps/plugin-clipboard-manager` |
| **Dialog** | `@tauri-apps/api/dialog` | `@tauri-apps/plugin-dialog` |
| **Shell/Process** | Core | `@tauri-apps/plugin-shell` |
| **Permissions** | Allowlist | **ACL/Capabilities** (fine-grained) |

### Capability/ACL (Tauri 2 Only)

```json
{
  "permissions": [
    "core:app:allow-app-hide",
    "core:app:allow-app-show",
    "shell:allow-execute",
    "shell:allow-spawn",
    "shell:allow-kill",
    "dialog:allow-open",
    "fs:allow-read-file",
    "fs:allow-write-file",
    "clipboard-manager:allow-read-text",
    "clipboard-manager:allow-write-text"
  ]
}
```

Format: `{plugin}:allow-{command}` or `{plugin}:deny-{command}`

### Plugin Migration Checklist
- ✓ `tauri-plugin-shell` → `Command.new_sidecar()` + shell commands
- ✓ `tauri-plugin-dialog` → file/message dialogs
- ✓ `tauri-plugin-fs` → file system operations
- ✓ `tauri-plugin-clipboard-manager` → read/write clipboard
- ✓ `tauri-plugin-store` → persistent key-value store
- ✓ `tauri-plugin-theme` → dark/light/system theme

---

## 10. Bundle Size Analysis

### Baseline Tauri 2 + SvelteKit Hello World
- **Rust binary:** 4.5 MB
- **WebView2 bootstrap stub:** ~200 KB
- **SvelteKit frontend:** 300 KB (base Svelte, minimal)
- **Tailwind v4 (tree-shaken):** 15 KB
- **@tauri-apps/api bundle:** 80 KB
- **Total (before sidecar):** ~5.2 MB

### With yt-dlp Sidecar
- yt-dlp binary: ~40–50 MB (standalone executable)
- **Total dist:** ~50–55 MB (NSIS installer ~12–15 MB after compression)

### Size Optimization Strategies
1. **Disable debug symbols:** `strip = true` in `Cargo.toml` [profile.release]
2. **Tree-shake unused Tailwind:** Default with v4; specify only needed colors
3. **Lazy-load async routes** in SvelteKit (code splitting)
4. **Minimize images & assets** in `src/`
5. **Pre-compress frontend** with gzip before bundling
6. **Don't include unnecessary crates:** Audit `Cargo.toml`

---

## 11. Dev Experience

### Workflow: `cargo tauri dev`
```bash
# Terminal 1: Frontend dev server (hot reload)
npm run dev

# Terminal 2: Tauri dev (watches Rust + frontend)
cargo tauri dev
```

- **Frontend hot reload:** Enabled by default (Vite)
- **Rust recompile:** On file changes in `src-tauri/src/`
- **DevTools:** F12 in dev, disabled in prod (unless `devtools` feature enabled)

### Debug Build
```bash
cargo tauri dev --debug
# or
cargo tauri build --debug
```
- Console enabled
- Source maps available
- Devtools accessible

### Logging
```rust
use tracing::{info, warn, error};
use tracing_subscriber;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    info!("App starting");
}
```

```bash
RUST_LOG=debug cargo tauri dev
```

### DevTools
- **Built-in inspector:** F12 in dev mode
- **CrabNebula DevTools (free):** Advanced debugging, log aggregation
- **Chrome DevTools:** Connect via chrome://inspect (some limitations on Tauri)

---

## 12. Theming with Tauri + Tailwind

### Approach 1: OS Theme Detection + Manual Toggle

```typescript
// stores/theme.ts
import { writable } from 'svelte/store'
import { theme as tauriTheme } from '@tauri-apps/plugin-theme'

export const currentTheme = writable<'light' | 'dark'>('light')

export async function initTheme() {
  const osTheme = await tauriTheme.getTheme()
  currentTheme.set(osTheme === 'dark' ? 'dark' : 'light')

  // Listen to OS theme changes
  tauriTheme.onThemeChanged((newTheme) => {
    currentTheme.set(newTheme === 'dark' ? 'dark' : 'light')
  })
}

export async function setTheme(t: 'light' | 'dark') {
  await tauriTheme.setTheme(t)
  currentTheme.set(t)
  localStorage.theme = t
}
```

### Approach 2: Tailwind `dark:` Classes
```html
<!-- Tailwind handles class-based dark mode -->
<div class="bg-white dark:bg-black text-black dark:text-white">
  Content
</div>
```

### Combined Setup: Svelte + Tailwind v4 + Tauri Theme Plugin
```svelte
<script>
  import { currentTheme, initTheme, setTheme } from '$lib/stores/theme'
  import { onMount } from 'svelte'

  onMount(() => {
    initTheme()
  })

  $: if (typeof document !== 'undefined') {
    if ($currentTheme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }
</script>

<button on:click={() => setTheme($currentTheme === 'dark' ? 'light' : 'dark')}>
  Toggle Theme
</button>
```

---

## 13. Recommended Dependencies (Pinned Versions)

### Rust (Cargo.toml)
```toml
# Tauri core & plugins (stable 2.x)
tauri = "2.0"
tauri-plugin-shell = "2.0"
tauri-plugin-dialog = "2.0"
tauri-plugin-fs = "2.0"
tauri-plugin-clipboard-manager = "2.0"
tauri-plugin-store = "2.0"
tauri-plugin-process = "2.0"
tauri-plugin-theme = "2.0"

# Async runtime (required for spawn, async commands)
tokio = { version = "1.35", features = ["full"] }

# Serialization
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

# Error handling
anyhow = "1.0"
thiserror = "1.0"

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

# Utilities
dirs = "5.0"                    # XDG/platform config paths
regex = "1.10"
slug = "0.1"

# Database (pick one)
rusqlite = { version = "0.31", features = ["bundled"] }
# OR async: sqlx = { version = "0.7", features = ["sqlite", "tokio-native-tls", "runtime-tokio-rustls"] }

# Date/time
chrono = { version = "0.4", features = ["serde"] }
uuid = { version = "1.6", features = ["v4", "serde"] }
```

### TypeScript/Node (package.json)
```json
{
  "@tauri-apps/api": "2.0.3",
  "@tauri-apps/plugin-shell": "2.0.0",
  "@tauri-apps/plugin-dialog": "2.0.0",
  "@tauri-apps/plugin-fs": "2.0.0",
  "@tauri-apps/plugin-clipboard-manager": "2.0.0",
  "@tauri-apps/plugin-store": "2.0.0",
  "@tauri-apps/plugin-process": "2.0.0",
  "@tauri-apps/plugin-theme": "2.0.0",
  "svelte": "5.0.0",
  "tailwindcss": "4.0.0",
  "@tailwindcss/vite": "4.0.0",
  "lucide-svelte": "0.410.0",
  "@sveltejs/kit": "2.5.0",
  "@sveltejs/adapter-static": "3.0.0",
  "vite": "5.1.0",
  "typescript": "5.4.0"
}
```

---

## Gotchas

1. **dragDropEnabled conflicts with HTML5 drag-drop:** If you need custom drag zones, set `dragDropEnabled: false` and handle HTML5 events yourself.

2. **yt-dlp binary must be in `src-tauri/binaries/`:** Relative paths in `externalBin` are from `src-tauri/`, not project root.

3. **ACL/Capabilities required in v2:** Old Tauri 1 allowlist won't work. You must define `permissions` array in `capabilities/default.json`.

4. **SvelteKit needs `ssr = false`:** In `src/routes/+layout.ts`, disable SSR so Tauri APIs work client-side.

5. **Svelte 5 uses runes (`$state`, `$derived`):** If migrating from v4, update component syntax.

6. **Tailwind v4 has no `config` function:** Use `@theme` CSS directives instead of `theme.extend`.

7. **WebView2 runtime is separate:** Bundled separately from app; `downloadBootstrapper` is default and recommended.

8. **Sidecar stdout is event-stream, not blocking:** You must use async channels + event listeners; blocking I/O will freeze the Tauri event loop.

9. **State<T> is thread-safe by design:** Tauri handles Arc wrapping; use `Mutex<T>` or `tokio::sync::Mutex<T>` inside, not Arc<Mutex<T>>.

10. **devtools feature must be enabled for prod debugging:** Add `devtools` to `tauri` features in Cargo.toml if you want inspector in release builds.

11. **Multiple concurrent sidecar spawns:** Each `spawn()` returns its own receiver; manage lifecycle (kill on app close) or processes will leak.

12. **Clipboard ops are async:** Use `.await` on `clipboard().read_text()`; no blocking variants.

---

## Status

**Status:** DONE

**Summary:** Tauri 2 + SvelteKit architecture fully specified for desktop video downloader migration. Sidecar binary bundling (Windows exe), IPC streaming patterns (Channels for high-freq, events for low-freq), state management (Mutex<T> preferred), and bundling strategy (<15 MB frontend + ~50 MB yt-dlp sidecar = ~60 MB total before compression) documented with code examples. Key migration gotchas and plugin dependencies listed.

**Unresolved questions:**
- Should we pre-bundle yt-dlp binary in repo or download at first run? (Trade-off: repo size vs install simplicity) — **Recommend bundled for reliability.**
- Do we need async SQLite (sqlx) or sync (rusqlite)? — **Recommend rusqlite with bundled feature for now; upgrade to sqlx + tokio if concurrency bottleneck emerges.**
- Will existing history.json (v2) schema migrate cleanly to SQLite? — **Yes; design migration script as separate phase.**

---

**Sources:**
- [Tauri 2 SvelteKit Setup](https://v2.tauri.app/start/frontend/sveltekit/)
- [Embedding External Binaries](https://v2.tauri.app/develop/sidecar/)
- [Calling Rust from Frontend](https://v2.tauri.app/develop/calling-rust/)
- [Tauri Configuration Reference](https://v2.tauri.app/reference/config/)
- [State Management in Tauri](https://v2.tauri.app/develop/state-management/)
- [Windows Installer Distribution](https://v2.tauri.app/distribute/windows-installer/)
- [Tauri 2 Migration Guide](https://v2.tauri.app/start/migrate/from-tauri-1/)
- [Drag & Drop Events](https://v2.tauri.app/reference/javascript/api/namespaceevent/)
- [App Size Optimization](https://v2.tauri.app/concept/size/)
- [Tailwind CSS v4 SvelteKit](https://tailwindcss.com/docs/guides/sveltekit)
- [CrabNebula DevTools](https://v2.tauri.app/develop/debug/crabnebula-devtools/)
- [Tauri 2.0 Stable Release](https://v2.tauri.app/blog/tauri-20/)
