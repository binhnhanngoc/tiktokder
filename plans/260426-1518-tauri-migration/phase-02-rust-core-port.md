# Phase 02 — Rust Core Port (config / url_parser / retry / path_builder / fb_resolver)

## Context Links
- Plan: [plan.md](plan.md)
- Phase 01: [phase-01-workspace-bootstrap.md](phase-01-workspace-bootstrap.md)
- Source modules: `config.py`, `url_parser.py`, `retry_policy.py`, `path_builder.py`, `facebook_resolver.py`

## Overview
- **Priority:** High
- **Status:** pending
- **Effort:** 2d
- Port 5 pure-logic Python modules to Rust. No Tauri wiring yet — pure libraries with unit tests. These are the foundation for Phase 03 engine.

## Key Insights
- All 5 modules are pure (no PySide6, no yt-dlp). Port is mechanical.
- Regex patterns are the source of truth — copy verbatim, don't paraphrase.
- `FB_LOGIN_WALL_MARKERS` tuple is a fixed string list — port to `&[&'static str]`.
- Decorrelated jitter math: `prev = min(cap, uniform(base, prev*3))`.
- Retry-After parsing: `Retry-After:\s*(\d+)` regex. HTTP-date format intentionally unsupported.

## Requirements

### Functional parity with Python originals
| Python | Rust | Test parity |
|--------|------|-------------|
| `validate_tiktok_url` / `validate_facebook_url` / `validate_url` | `url_parser::validate_*` | port `test_tiktokder.py` URL tests |
| `is_channel_url` / `is_facebook_page_url` / `is_page_or_channel_url` | same | same |
| `detect_platform` → `Option<Platform::{TikTok,Facebook}>` | enum-typed | same |
| `extract_video_id` | `Option<String>` | same |
| `read_batch_file` | `read_batch_file(path) -> Result<Vec<String>>` | port |
| `build_user_url` | same | port |
| `slugify_uploader` | same; preserve NFKC + 80-char cap | port `test_path_builder.py` |
| `platform_slug_from_url` | same | port |
| `build_output_template` | same | port |
| `parse_retry_after` | `Option<f64>` | port `test_retry_policy.py` |
| `decorrelated_jitter` / `retry_after_aware_wait` / `with_retry` | async equivalents | port |
| `resolve_fb_shortlink` | async; rquest impersonation | port `test_facebook_resolver.py` |
| `AppConfig` load/save + portable detection + legacy migration | same | port `test_config.py` |
| `PlatformDefaults` / `get_platform_defaults` / `get_max_retry_attempts` | same | port |
| `FB_LOGIN_WALL_MARKERS` | `pub const` | reused by classify.rs in phase 03 |

## Architecture

### Crate layout (within `src-tauri/`)
```
src-tauri/src/
├── url_parser.rs           ~200 LOC
├── path_builder.rs         ~150 LOC
├── retry.rs                ~180 LOC
├── fb_resolver.rs          ~120 LOC
├── config.rs               ~250 LOC
└── lib.rs                  pub mod url_parser; pub mod path_builder; ...
```

### Module APIs (Rust signatures)

```rust
// url_parser.rs
#[derive(Debug, Copy, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum Platform { TikTok, Facebook }

pub fn detect_platform(url: &str) -> Option<Platform>;
pub fn validate_url(url: &str) -> bool;
pub fn validate_tiktok_url(url: &str) -> bool;
pub fn validate_facebook_url(url: &str) -> bool;
pub fn is_channel_url(url: &str) -> bool;
pub fn is_facebook_page_url(url: &str) -> bool;
pub fn is_page_or_channel_url(url: &str) -> bool;
pub fn extract_video_id(url: &str) -> Option<String>;
pub fn read_batch_file(path: &Path) -> std::io::Result<Vec<String>>;
pub fn build_user_url(username: &str) -> Result<String, ParseError>;

// path_builder.rs
pub fn slugify_uploader(name: Option<&str>) -> String;
pub fn platform_slug_from_url(url: &str) -> String;
pub fn build_output_template(url: &str, info: Option<&serde_json::Value>, base_dir: &Path) -> PathBuf;
pub const UNKNOWN_UPLOADER: &str = "unknown_uploader";

// retry.rs
#[derive(Debug, thiserror::Error)]
pub enum DownloadError {
    #[error("login required: {0}")] LoginRequired(String),
    #[error("private: {0}")] Private(String),
    #[error("not found: {0}")] NotFound(String),
    #[error("rate limited (retry_after={retry_after:?}): {msg}")]
    RateLimited { msg: String, retry_after: Option<f64> },
    #[error("transient: {0}")] Transient(String),
    #[error("permanent: {0}")] Permanent(String),
}

pub fn parse_retry_after(msg: &str) -> Option<f64>;
pub fn is_retryable(e: &DownloadError) -> bool;
pub async fn with_retry<F, Fut, T>(max_attempts: u32, base: f64, cap: f64, f: F) -> Result<T, DownloadError>
where F: FnMut() -> Fut, Fut: Future<Output = Result<T, DownloadError>>;

// fb_resolver.rs
pub fn is_fb_shortlink(url: &str) -> bool;
pub async fn resolve_fb_shortlink(url: &str, timeout: Duration) -> (String, ResolveStatus);
#[derive(Debug, PartialEq)] pub enum ResolveStatus { Ok, LoginRequired, Unknown }

// config.rs
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AppConfig { /* same fields as Python AppConfig */ }
impl Default for AppConfig { /* matches Python defaults, incl. portable detection */ }
pub fn load_config() -> AppConfig;
pub fn save_config(c: &AppConfig) -> std::io::Result<()>;
pub fn config_dir() -> PathBuf;
pub fn data_dir() -> PathBuf;
pub fn migrate_legacy_data_dir();

#[derive(Debug, Clone, Copy)]
pub struct PlatformDefaults { /* delay_mean/std/floor, workers, retries */ }
pub const TIKTOK_DEFAULTS: PlatformDefaults = ...;
pub const FACEBOOK_DEFAULTS: PlatformDefaults = ...;
pub const FB_LOGIN_WALL_MARKERS: &[&str] = &[
    r#"id="login_form""#, r#"id="loginbutton""#, "You must log in to continue",
    r#"class="uiInterstitialContent""#, "login.php",
];
pub fn get_platform_defaults(url: &str) -> PlatformDefaults;
pub fn get_max_retry_attempts(url: &str) -> u32;
```

## Related Code Files

### Create (Rust)
- `src-tauri/src/url_parser.rs`
- `src-tauri/src/path_builder.rs`
- `src-tauri/src/retry.rs`
- `src-tauri/src/fb_resolver.rs`
- `src-tauri/src/config.rs`
- `src-tauri/tests/url_parser.rs` (integration tests)
- `src-tauri/tests/path_builder.rs`
- `src-tauri/tests/retry.rs`
- `src-tauri/tests/fb_resolver.rs`
- `src-tauri/tests/config.rs`

### Cargo deps (add to `src-tauri/Cargo.toml`)
```toml
regex = "1"
once_cell = "1"            # or std::sync::LazyLock if MSRV >= 1.80
url = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "1"
anyhow = "1"
rand = "0.8"
chrono = { version = "0.4", features = ["serde"] }
dirs = "5"
unicode-normalization = "0.1"
rquest = "2"               # version pinned by phase-01 spike result
tokio = { version = "1", features = ["time", "rt", "macros"] }

[dev-dependencies]
tempfile = "3"
mockito = "1"              # for fb_resolver HTTP mocking
tokio = { version = "1", features = ["macros", "rt-multi-thread", "test-util"] }
```

### Read for porting reference
- `url_parser.py` — copy regexes verbatim into `Regex::new()`. Compile lazily via `LazyLock`/`once_cell::Lazy`.
- `path_builder.py` — slugify uses `unicode_normalization::UnicodeNormalization::nfkc`.
- `retry_policy.py` — translate decorrelated_jitter to: `let next = (rng.gen_range(base..=(prev*3.0).max(base))).min(cap);`.
- `facebook_resolver.py` — port to `rquest::Client` with `chrome131` impersonation; HEAD/GET with `redirect(Policy::none())`.
- `config.py` — handle PyInstaller frozen-detection equivalent: in Tauri use `tauri::path::resolve_directory` or detect via `dirs::config_dir()` plus a portable fallback (env var or co-located file) — keep portable-mode flag.
- `history_store.py` — schema fields used by `AppConfig.history_max_entries` (DEFAULT_MAX_ENTRIES = 10000).

### Do not modify
- Anything Python.

## Implementation Steps

### Step 1 — `url_parser.rs`
1. Copy 5 regex patterns from `url_parser.py:9-42`. Test compile with `cargo test`.
2. `LazyLock<Regex>` for each pattern. Match via `Regex::is_match`.
3. `detect_platform`: short-circuit by trying TikTok patterns first.
4. Username validation regex: `^[\w.]+$`. Map to `[A-Za-z0-9_.]+` for Rust regex.
5. `read_batch_file`: `BufRead::lines`, skip empty/`#`-prefixed, dedup via `HashSet` while preserving order.
6. Tests: 1:1 port of all `test_tiktokder.py` URL test cases (the 67 tests). Use `rstest` parameterized cases for the URL match tables.

### Step 2 — `path_builder.rs`
1. Constants: `UNKNOWN_UPLOADER`, `_MAX_SLUG_LEN = 80`, three regex consts.
2. `slugify_uploader`:
   - NFKC: `name.nfkc().collect::<String>()`.
   - Replace path-sep / reserved / whitespace runs with `_`.
   - Collapse underscore runs.
   - Trim `._ ` from both ends.
   - Truncate to 80 graphemes (UTF-8 aware: `s.chars().take(80).collect()`).
   - Empty → `UNKNOWN_UPLOADER`.
3. `platform_slug_from_url`: parse via `url::Url::parse`, walk path segments, prefer `@handle`, else first non-skip segment.
4. `build_output_template(url, info, base_dir) -> PathBuf`: returns `base_dir/<platform>/<slug>/%(id)s_%(title).50s.%(ext)s` — keep yt-dlp template tokens literal in the path.

### Step 3 — `retry.rs`
1. Define `DownloadError` enum (typed exceptions equivalent).
2. `parse_retry_after`: `Regex::new(r"(?i)Retry-After:\s*(\d+)")`.
3. `is_retryable`: only `RateLimited` + `Transient`.
4. `decorrelated_jitter` as a stateful struct: `Jitter { prev: f64, base: f64, cap: f64 }` with `next(&mut self, rng) -> Duration`.
5. `with_retry<F, Fut, T>`: loop up to `max_attempts`, await `f()`, on retryable error pick wait = `RateLimited.retry_after.unwrap_or(jitter.next())` clamped to `cap`, `tokio::time::sleep(wait).await`, retry. Reraise on terminal error or attempt cap.

### Step 4 — `fb_resolver.rs`
1. `is_fb_shortlink`: `Regex::new(r"(?i)^https?://fb\.watch/")`.
2. `resolve_fb_shortlink`:
   - Build `rquest::Client::builder().impersonate(rquest::Impersonate::Chrome131).redirect(rquest::redirect::Policy::none()).timeout(timeout).build()?`.
   - GET → response.
   - 3xx: read `Location` header; if contains `/login` or `login.php` (case-insensitive) → `LoginRequired`; else `Ok` with location.
   - 200: read body up to `_BODY_SCAN_LIMIT = 50_000` bytes; scan for any `FB_LOGIN_WALL_MARKERS` substring.
   - Anything else / network error → fail-open `Unknown`.
3. Test with `mockito` (or `wiremock-rs`) — register a 302 to `/login.php` and assert `LoginRequired`; register a 200 with `id="login_form"` and assert `LoginRequired`.

### Step 5 — `config.rs`
1. `AppConfig` struct with serde derives. Defaults match Python (output_dir, workers=3, delay=0.5, quality_default="best", theme_mode="system", history_max_entries=10000, etc.).
2. Path resolution:
   - `config_dir()` — when running as a portable bundle (detect via `std::env::current_exe()` + a `portable.flag` sibling file, OR Tauri runtime `is_portable` heuristic), use `<exe-dir>/data`. Otherwise `dirs::config_dir().join("tiktokder")`.
   - `data_dir()` — same logic (history.db lives here in phase 04).
3. `migrate_legacy_data_dir()`:
   - Source: `~/.tiktokder/{config.json,history.json}` (legacy); `<old-portable-root>/data/{config.json,history.json}` (current PyInstaller).
   - Destination: new `config_dir()`.
   - Idempotent. Move files only if dest absent. Remove empty legacy dir.
4. `load_config()` → reads `config.json`; on missing/corrupt → `AppConfig::default()`. Filter unknown fields via serde `deny_unknown_fields = false` and explicit field set.
5. `save_config()` → atomic write (write to `.tmp` + rename).
6. `PlatformDefaults` const + `get_platform_defaults` / `get_max_retry_attempts` mirror Python.

### Step 6 — Glue in `lib.rs`
```rust
pub mod url_parser;
pub mod path_builder;
pub mod retry;
pub mod fb_resolver;
pub mod config;
```

### Step 7 — Tests
1. **url_parser**: ~40 cases parameterized via `rstest`; cover TikTok/FB validity, channel detection, page detection, extract_video_id, batch file reader. Acceptance: 100% pass against Python equivalents.
2. **path_builder**: ~20 cases; slugify Unicode + reserved chars + truncation + path traversal protection; uploader extraction from URL; outtmpl composition.
3. **retry**: parse_retry_after table, jitter monotonic-ish sequence (within bounds), with_retry honors `RateLimited.retry_after`, terminal error escapes, attempt cap.
4. **fb_resolver**: mockito-mock 302→login, 200+marker, 200 clean, 5xx → Unknown, timeout → Unknown.
5. **config**: load defaults on missing file; load round-trips through save; migration moves files; portable detection.

## Todo
- [ ] `url_parser.rs` + tests pass
- [ ] `path_builder.rs` + tests pass
- [ ] `retry.rs` + tests pass
- [ ] `fb_resolver.rs` + tests pass (mockito)
- [ ] `config.rs` + tests pass (tempfile)
- [ ] `lib.rs` exports all 5 modules
- [ ] `cargo clippy --all-targets` clean (deny warnings)
- [ ] `cargo fmt` applied

## Success Criteria
- All ported tests pass; no regressions vs Python behaviors documented above.
- `cargo build --release` succeeds; binary size before Tauri linkage < 5 MB.
- No `unwrap()` in non-test code (use `?` + typed errors).

## Risk Assessment
- **Regex differences (Python vs Rust regex crate):** Python `\w` matches Unicode word chars by default; Rust `regex` crate matches ASCII unless `(?u)`. Patterns above use `[\w.]` — explicitly add `(?-u:[\w.])` or rewrite to `[A-Za-z0-9_.]` to match Python's ASCII-mode-effective behavior on TikTok handles. Audit each.
- **NFKC normalization differences:** Python `unicodedata` and Rust `unicode-normalization` should match; fuzz a few non-Latin examples to confirm.
- **rquest API drift:** Phase 01 spike pins the version. If breaking pre-phase-02, freeze in `Cargo.lock`.
- **Decorrelated jitter RNG seed:** Use `rand::thread_rng()` for prod; tests inject a deterministic seed via `rand::rngs::StdRng::seed_from_u64`.

## Security
- No `unsafe` blocks.
- Atomic writes: file written to `<path>.tmp.<pid>.<rand>` then `std::fs::rename`. On Windows, ensure no other handle holds the dest.
- `read_batch_file` enforces UTF-8; reject batch files > some sane size (5 MB) to prevent OOM.

## Next Steps
- Phase 03 plugs these modules into the engine and yt-dlp.exe sidecar wrapper.
