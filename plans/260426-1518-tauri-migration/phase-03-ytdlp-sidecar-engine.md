# Phase 03 — yt-dlp.exe Sidecar Engine

## Context Links
- Plan: [plan.md](plan.md)
- Source: `downloader.py`, `download_engine.py`, `retry_policy.py`, `facebook_resolver.py`
- Phase 02 deliverable: `retry.rs`, `fb_resolver.rs`, `path_builder.rs`, `config.rs`

## Overview
- **Priority:** Critical (the heart of the app)
- **Status:** pending
- **Effort:** 3d
- Wrap yt-dlp.exe as a sidecar with structured progress streaming, error classification, per-platform pacing, retry, FB shortlink pre-resolution, and concurrent queue management. Replaces 600+ LOC of `downloader.py` + `download_engine.py`.

## Key Insights
- yt-dlp's `--progress-template "download:%(progress)j"` emits one **JSON line per progress tick** to stdout — no stderr races. With `--newline`, lines are LF-terminated, not CR-overwritten.
- Pre-pass: `yt-dlp -J --skip-download` returns the full info dict on stdout — use this to extract `uploader`/`channel` BEFORE running the real download, then pass `-o <built-template>` to control output path.
- Errors land on stderr with prefixes like `ERROR:` / `WARNING:`. Exit 0 = success; non-zero = failure (yt-dlp does not have stable numeric codes — classify from stderr text).
- Cancellation = `Child::kill()` + `wait()`. On Windows, `Child::kill` issues `TerminateProcess` (no graceful drain), which is acceptable since yt-dlp's partial files are auto-cleaned on next run.
- One process per URL. `tokio::sync::Semaphore::new(workers)` gates concurrency.
- Per-URL workdir is unnecessary because we set `-o <full-template>` per call; yt-dlp writes directly to the per-uploader folder.

## Requirements

### Functional
- `engine::add_urls(urls, force) -> ()` — queue with dedup against history (consult phase-04 store).
- `engine::cancel_url(url)` / `engine::cancel_all()` — kill child + drop queue.
- `engine::retry_urls(urls, force)` — re-queue (clear dedup).
- Per-URL events streamed via `tauri::ipc::Channel<ProgressEvent>` (one channel per add_urls call).
- App-wide events emitted via `app.emit`: `queue:changed`, `download:finished`, `all:finished`, `history:changed`.
- Per-platform jitter: TikTok mean 1.5s std 0.5 floor 0.2; FB mean 3.0s std 1.5 floor 0.5.
- Per-platform retry budget: TikTok 3 outer, FB 2 outer (matches Python).
- yt-dlp inner retries: pass via `--retries 10` (TikTok) or `--retries 2` (FB); `--extractor-retries 5`, `--fragment-retries 10`, `--socket-timeout 30`.
- TLS fingerprinting: yt-dlp standalone .exe supports `--impersonate Chrome-136` (verified in spike). If absent on chosen yt-dlp version, drop and document.
- Error classification reproduces Python `_classify_error` mapping.
- FB shortlink pre-resolution before yt-dlp invocation (reuse `fb_resolver.rs`).

### Non-functional
- Up to 10 concurrent yt-dlp processes (worker cap).
- Cancel responds in < 500 ms.
- Progress events at most 10/s/URL (debounce in BE before emitting to Channel).

## Architecture

### Module layout
```
src-tauri/src/engine/
├── mod.rs              DownloadEngine struct, queue, semaphore, public API
├── ytdlp.rs            Sidecar Command builder, stdout/stderr stream, JSON line parser
├── progress.rs         ProgressEvent enum + Channel sink
├── classify.rs         stderr → DownloadError classifier (port _classify_error)
└── job.rs              one-URL state machine (Queued → Running → Finished/Failed/Cancelled)
```

### Types
```rust
// progress.rs
#[derive(Clone, serde::Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ProgressEvent {
    Started   { url: String },
    Progress  { url: String, downloaded_bytes: u64, total_bytes: Option<u64>, speed: Option<f64>, eta: Option<u64>, percent: f32 },
    Finished  { url: String, video_id: Option<String>, title: Option<String>, file_path: Option<String>, size_bytes: Option<u64> },
    Failed    { url: String, kind: String /* matches Python ErrorKind */, message: String },
    Cancelled { url: String },
    Skipped   { url: String, video_id: String, reason: String },
}

// engine/mod.rs
pub struct DownloadEngine {
    cfg: Arc<RwLock<EngineConfig>>,
    sem: Arc<Semaphore>,
    queued: Arc<Mutex<HashMap<String, JobState>>>,
    children: Arc<Mutex<HashMap<String, tauri_plugin_shell::CommandChild>>>,
    history: Arc<HistoryStore>,        // from phase 04
    app: AppHandle,
}

#[derive(Clone, Debug)]
pub struct EngineConfig {
    pub output_dir: PathBuf,
    pub max_workers: usize,
    pub delay_override: Option<f64>,
    pub cookie_browser: Option<String>,
    pub quality: Quality,
    pub write_subs: bool,
    pub write_thumb: bool,
    pub history_max_entries: usize,
    pub ffmpeg_path: Option<PathBuf>,
}

pub enum Quality { Best, P1080, P720, P480, Audio }
```

### yt-dlp argv builder (`ytdlp.rs`)

```rust
pub fn build_args(url: &str, outtmpl: &Path, cfg: &EngineConfig, retries: u32, force: bool) -> Vec<String> {
    let mut a: Vec<String> = vec![
        "--newline".into(),
        "--progress-template".into(), "download:%(progress)j".into(),
        "--output".into(), outtmpl.to_string_lossy().into_owned(),
        "--retries".into(), retries.to_string(),
        "--extractor-retries".into(), "5".into(),
        "--fragment-retries".into(), "10".into(),
        "--socket-timeout".into(), "30".into(),
        "--no-warnings".into(),
        "--no-playlist".into(),
        "--impersonate".into(), "Chrome-136".into(),
        "--format".into(), format_for_quality(cfg.quality).into(),
    ];
    if force { a.push("--force-overwrites".into()); }
    if cfg.write_subs {
        a.extend(["--write-subs", "--write-auto-subs", "--sub-langs", "en", "--sub-format", "srt/best"].map(String::from));
    }
    if cfg.write_thumb { a.push("--write-thumbnail".into()); }
    if let Some(b) = &cfg.cookie_browser { a.extend(["--cookies-from-browser".into(), b.clone()]); }
    if let Some(f) = &cfg.ffmpeg_path { a.extend(["--ffmpeg-location".into(), f.to_string_lossy().into_owned()]); }
    if matches!(cfg.quality, Quality::Audio) {
        a.extend(["--extract-audio", "--audio-format", "m4a", "--audio-quality", "0"].map(String::from));
    }
    a.push(url.into());
    a
}

fn format_for_quality(q: Quality) -> &'static str {
    match q {
        Quality::Best  => "b",
        Quality::P1080 => "bv*[height<=1080]+ba/b[height<=1080]",
        Quality::P720  => "bv*[height<=720]+ba/b[height<=720]",
        Quality::P480  => "bv*[height<=480]+ba/b[height<=480]",
        Quality::Audio => "ba/b",
    }
}
```

### Pre-pass + path build flow (per-URL)

```
1. shortlink? → fb_resolver::resolve_fb_shortlink(url, 5s)
   - "login_required" → emit Failed{LoginRequired}; done.
   - "ok" with canonical url → swap url.
   - "unknown" → keep url.
2. yt-dlp -J --skip-download --no-warnings --impersonate Chrome-136 [--cookies-from-browser X] <url>
   - parse JSON from stdout.
   - extract uploader/channel/uploader_id/creator → slug.
   - on failure → classify, emit Failed; done.
3. outtmpl = build_output_template(url, info, output_dir)
4. yt-dlp <build_args>(url, outtmpl, cfg, retries, force)
   - stream stdout: parse JSON-line `{"status":"downloading","downloaded_bytes":N,"total_bytes":M,...}`.
   - emit Progress events (debounced 100 ms).
   - on stderr lines: collect last N lines for error attribution.
5. exit code:
   - 0 → re-parse `info` (already have it from step 2) for video_id/title/path → emit Finished + persist HistoryRecord.
   - non-zero → classify(stderr_collected) → emit Failed; let `with_retry` decide retry.
```

### Concurrency
```rust
// engine/mod.rs:add_urls
for url in urls {
    let permit = sem.clone().acquire_owned().await?;
    let jh = tokio::spawn(async move {
        let _permit = permit;                    // released on drop
        let res = run_one(...).await;
        // post-platform-aware jitter sleep BEFORE returning the permit:
        // (port: download_engine._on_worker_finished QTimer logic)
        let pd = get_platform_defaults(&url);
        let mean = cfg.delay_override.unwrap_or(pd.delay_mean);
        sleep_jitter(mean, pd.delay_std, pd.delay_floor).await;
        res
    });
    spawned.push(jh);
}
```

Note: Python applies the inter-download delay between *finishing one* and *starting next replacement* at fixed worker capacity. In Rust we approximate by holding the permit across a post-completion sleep — same observed behavior under steady-state.

### Stderr classification (`classify.rs`)

```rust
pub fn classify(stderr: &str) -> DownloadError {
    use crate::config::FB_LOGIN_WALL_MARKERS;
    let lc = stderr.to_lowercase();
    if FB_LOGIN_WALL_MARKERS.iter().any(|m| stderr.contains(m))
        || (lc.contains("login") && (lc.contains("required") || lc.contains("redirect")))
    { return DownloadError::LoginRequired(stderr.into()); }
    if lc.contains("private") { return DownloadError::Private(stderr.into()); }
    if stderr.contains("404") || stderr.contains("Video unavailable") || lc.contains("not found")
    { return DownloadError::NotFound(stderr.into()); }
    if stderr.contains("HTTP Error 429") || lc.contains("rate limit") || lc.contains("too many requests") {
        let retry_after = retry::parse_retry_after(stderr);
        return DownloadError::RateLimited { msg: stderr.into(), retry_after };
    }
    if stderr.contains("HTTP Error 5") || lc.contains("connection") || lc.contains("timeout") || lc.contains("temporarily")
    { return DownloadError::Transient(stderr.into()); }
    DownloadError::Transient(stderr.into())     // unknown → retry once (matches Python)
}
```

## Related Code Files

### Create
- `src-tauri/src/engine/mod.rs`
- `src-tauri/src/engine/ytdlp.rs`
- `src-tauri/src/engine/progress.rs`
- `src-tauri/src/engine/classify.rs`
- `src-tauri/src/engine/job.rs`
- `src-tauri/src/commands.rs` (Tauri command handlers — start_download, cancel_url, cancel_all, list_active)
- Tests:
  - `src-tauri/tests/engine_argv.rs` (build_args matrix)
  - `src-tauri/tests/engine_classify.rs` (port `_classify_error` cases)
  - `src-tauri/tests/engine_progress_parse.rs` (synthetic stdout JSON lines)
  - `src-tauri/tests/engine_smoke.rs` (gated behind `#[ignore]`, runs against a fake yt-dlp shim binary)

### Read for context
- `downloader.py:195-251` (yt-dlp opts mapping → argv flags)
- `downloader.py:93-124` (`_classify_error`)
- `downloader.py:273-340` (`_do_download` flow → mirror in Rust)
- `download_engine.py:18-79` (DownloadWorker — progress emission semantics)
- `download_engine.py:149-213` (queue + jitter + start_next pattern)

### Cargo deps additions
```toml
tauri-plugin-shell = "2"     # already present
tokio = { version = "1", features = ["full"] }
tokio-util = "0.7"           # CancellationToken
futures = "0.3"
```

## Implementation Steps

### Step 1 — `progress.rs`
1. Define `ProgressEvent` enum (above).
2. Helper: `emit_event(channel: &Channel<ProgressEvent>, ev: ProgressEvent)` that maps `Channel<T>::send` errors to logged warnings (frontend may have unsubscribed).

### Step 2 — `ytdlp.rs`
1. `build_args` per spec.
2. `pub async fn run_pre_pass(app: &AppHandle, url: &str, cfg: &EngineConfig) -> Result<serde_json::Value, DownloadError>` — spawns sidecar with `["-J","--skip-download","--no-warnings","--impersonate","Chrome-136", url]`, reads full stdout, `serde_json::from_slice`, on non-zero exit classify stderr.
3. `pub async fn run_download(...)` — spawn child via `tauri_plugin_shell::ShellExt::shell().sidecar("yt-dlp")?.args(args).spawn()`. Returns `(CommandChild, ProcessStream)`.
4. JSON line parser: `BufReader::new(stdout).lines()` → for each line starting `download:` strip prefix, `serde_json::from_str` into `RawProgress { status, downloaded_bytes, total_bytes, total_bytes_estimate, eta, speed, filename, ... }`. Compute percent. Debounce 100 ms.
5. Stderr collector: read concurrently via `tokio::select!` or two `tokio::spawn` tasks; keep last 4 KB.
6. `wait_for_exit() -> ExitStatus` then drop the streams.

### Step 3 — `classify.rs`
1. Port the 5-class classifier (above).
2. Tests: feed sample stderr fixtures from `test_tiktokder.py` + `test_retry_policy.py`.

### Step 4 — `job.rs`
1. `Job { url, state, child: Option<CommandChild>, channel: Channel<ProgressEvent> }`.
2. State machine transitions guarded by `tokio::sync::Mutex`.
3. `cancel(self)` → `child.kill().await`.

### Step 5 — `engine/mod.rs`
1. Construct with `Arc<HistoryStore>` (phase 04) — but stub with a trait now to avoid blocking on phase 04.
   ```rust
   pub trait HistoryGate: Send + Sync {
       fn contains(&self, video_id: &str) -> bool;
       fn record(&self, rec: HistoryRecord);
   }
   ```
2. `add_urls(urls, force, channel)` — for each url:
   - dedup against `queued + history` unless `force`.
   - acquire semaphore permit.
   - spawn `run_one(url, cfg, channel.clone(), permit)`.
3. `run_one`:
   - `with_retry(max_attempts, base=2.0, cap=60.0, || run_attempt(url))` from `retry.rs`.
   - on `RateLimited.retry_after` → `with_retry` honors it.
4. `run_attempt`:
   - shortlink resolve → maybe LoginRequired bail.
   - pre-pass → info JSON.
   - build outtmpl from info.
   - run_download → stream events to channel.
   - on success: build `HistoryRecord`, emit `Finished`, return Ok.
   - on failure: emit `Failed { kind }`, return Err for `with_retry`.
5. `cancel_url(url)` / `cancel_all()`: lock children map, kill, drop.
6. `set_config(new)` → atomic swap (matches Python `_apply_settings` behavior).

### Step 6 — Tauri commands (`commands.rs`)
```rust
#[tauri::command]
async fn add_urls(state: State<'_, AppState>, urls: Vec<String>, force: bool, on_event: Channel<ProgressEvent>) -> Result<(), String>;

#[tauri::command]
async fn cancel_url(state: State<'_, AppState>, url: String) -> Result<(), String>;

#[tauri::command]
async fn cancel_all(state: State<'_, AppState>) -> Result<(), String>;

#[tauri::command]
async fn engine_status(state: State<'_, AppState>) -> EngineStatus;     // queue size, active count

#[tauri::command]
async fn set_engine_config(state: State<'_, AppState>, cfg: EngineConfig) -> Result<(), String>;
```

Register in `lib.rs::run`. Construct `AppState { engine: DownloadEngine }` in `.setup(...)` and `.manage()` it.

### Step 7 — Tests
1. `engine_argv.rs`: build_args produces expected argv for {best, 1080p, audio} × {force on/off, subs on/off, thumb on/off, fb cookie set, ffmpeg set}. Snapshot via `insta`.
2. `engine_classify.rs`: 1:1 mapping of `_classify_error` cases.
3. `engine_progress_parse.rs`: feed canned JSON lines, assert ProgressEvent stream.
4. `engine_smoke.rs` (`#[ignore]`): spawns a Python or shell shim that emits realistic progress JSON + exits 0 — verifies end-to-end channel receipt.

### Step 8 — Wire to `lib.rs`
- Initialize `tracing_subscriber` in `setup()`.
- Construct `DownloadEngine`, place in app state.
- Register all commands.

## Todo
- [ ] `progress.rs` event enum + Channel emit helper
- [ ] `ytdlp.rs` pre-pass + download runner with stdout JSON streaming
- [ ] `classify.rs` ported + tests pass
- [ ] `job.rs` state machine
- [ ] `engine/mod.rs` queue, semaphore, retry integration
- [ ] `commands.rs` Tauri handlers
- [ ] Smoke E2E: `cargo test -- --ignored engine_smoke` green using fake shim
- [ ] Cancel kills child within 500 ms (timed test)
- [ ] No memory leak on 100-URL run (spot check via `wmic process` or task manager)

## Success Criteria
- Drive a 5-URL TikTok download from a Tauri command, observe Progress + Finished events arriving, files land in `<output_dir>/tiktok/<uploader>/<id>_<title>.mp4`.
- 1 URL with `force=true` overwrites existing file.
- Cancel during a download produces a `Cancelled` event and partial file disposition.
- LoginRequired surfaces fast for `fb.watch` shortlinks pointing at login walls.
- Concurrent downloads respect `max_workers` (verified via process count).

## Risk Assessment
- **`--impersonate Chrome-136` not supported in chosen yt-dlp version.** yt-dlp added impersonation backends progressively; current stable supports Chrome-110/120/131/136 depending on build. Spike confirms which is available; if Chrome-136 absent, downgrade to Chrome-131 (matches our shortlink resolver).
- **`--progress-template` JSON parse drift between yt-dlp versions.** Pin yt-dlp.exe SHA in build script; expose `--update` only via Settings (deferred).
- **Stderr can interleave with stdout when both heavy.** yt-dlp guarantees progress on stdout only with `--progress-template`; warnings on stderr. Race-free as long as we read both streams concurrently.
- **Windows `kill()` leaves orphaned child trees.** yt-dlp doesn't fork; single process per child. Confirmed safe.
- **JSON debounce eats final progress event.** Always flush a final Progress event when status flips to "finished" before emitting Finished (handled in step 2.4).
- **`-J` pre-pass doubles request volume per URL.** Mitigation: cache info dict; skip pre-pass when URL already mapped to a known uploader (rare). Accept as the cost of per-uploader path correctness.

## Security
- No shell-string interpolation: argv built as `Vec<String>`, no `cmd /c`.
- Cookie source restricted to enum `{None, Chrome, Firefox, Edge}`; rejected at command boundary.
- ACL: only `binaries/yt-dlp` and `binaries/ffmpeg` sidecars allowed.
- yt-dlp output paths are within `cfg.output_dir`; reject if `outtmpl` resolves outside (defense vs malicious uploader names — slugify already strips path separators).

## Next Steps
- Phase 04 swaps the stub `HistoryGate` for real SQLite-backed `HistoryStore`.
- Phase 05 reuses `ytdlp.rs::run_pre_pass` with `--flat-playlist` for channel/page enumeration.
