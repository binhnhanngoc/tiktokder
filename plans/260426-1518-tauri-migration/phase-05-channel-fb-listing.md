# Phase 05 — Channel/Page listing (TikTok flat-playlist + Facebook page enumeration)

## Context Links
- Plan: [plan.md](plan.md)
- Source: `channel_fetcher.py` (TikTok flat-playlist), `facebook_fetcher.py` (Playwright — TO BE ELIMINATED)
- Phase 03: `ytdlp::run_pre_pass` reused
- Phase 01 spike: validates whether yt-dlp.exe alone covers FB pages

## Overview
- **Priority:** High
- **Status:** pending
- **Effort:** 2d
- Replace both Python channel/page fetchers with one yt-dlp.exe-driven pipeline. Drop Playwright entirely. Handles both TikTok profiles and Facebook pages via `--flat-playlist -J`. If FB page enumeration fails (per spike), implement rquest-based HTML scrape fallback.

## Key Insights
- `yt-dlp --flat-playlist -J <url>` returns one JSON document with `entries: [...]` — no streaming. For long lists (1000+), this is a single large JSON parse — acceptable since the original Python channel_fetcher reads it the same way.
- Streaming results to UI is achieved by emitting one `channel:video-found` event per entry from BE *after* the JSON parse, allowing the UI to populate progressively.
- TikTok profiles: confirmed working via yt-dlp.
- Facebook pages: spike-validated. If yt-dlp's FB extractor fails on pages (likely without cookies), use `--cookies-from-browser` first; fallback to rquest scrape.

## Requirements

### Functional
- Input: a TikTok channel URL (`tiktok.com/@user`) or Facebook page URL (`facebook.com/<page>` / `m.facebook.com/<page>`).
- Output: stream of `VideoInfo` events to the requesting UI, then a `finished` event with total count.
- Cancellation supported (kill the yt-dlp process).
- Quality field populated when yt-dlp returns `height` or a format string with `\d{3,4}p`.
- Limit: configurable (default 100; matches Python `limit=30/50` defaults loosely — bump for parity with current UX which scrolls).

### Types
```rust
#[derive(Clone, serde::Serialize)]
pub struct VideoInfo {
    pub url: String,
    pub title: String,
    pub duration: Option<u64>,
    pub view_count: Option<u64>,
    pub upload_date: Option<String>,    // YYYYMMDD
    pub video_id: String,
    pub quality: Option<String>,
}
```

## Architecture

```
src-tauri/src/channel/
├── mod.rs          public API: list_channel(url, cancel_token, on_event) -> Result<usize>
├── ytdlp_list.rs   shared --flat-playlist runner
├── tiktok.rs       URL normalization (build_user_url) + invoke
├── facebook.rs     URL normalization (page tab variants) + invoke + fallback
└── fallback.rs     rquest scraping fallback for FB pages (only if needed)
```

### Flow

```
list_channel(url, token, channel) {
    let platform = detect_platform(url)?;
    if matches!(platform, Platform::TikTok) {
        return ytdlp_list::run(url, &token, channel, /*workers*/1).await;
    }
    // Facebook
    let fb_url = facebook::normalize_for_listing(url);     // append /reels or sk=reels_tab
    match ytdlp_list::run(&fb_url, &token, channel.clone(), 1).await {
        Ok(n) if n > 0 => Ok(n),
        Ok(0) | Err(_) => fallback::scrape_fb_page(&fb_url, &token, channel).await,
    }
}
```

### `ytdlp_list::run`
1. Spawn sidecar with `["--flat-playlist","-J","--no-warnings","--impersonate","Chrome-136", url]` and `--cookies-from-browser` if configured.
2. Read full stdout to memory (cap 32 MB to defend OOM on a malicious feed).
3. `serde_json::from_slice` into a partial `Playlist { entries: Vec<RawEntry> }`.
4. For each entry: build `VideoInfo` (port `quality_from_entry` and the URL-fallback logic from `channel_fetcher.py:79-92`), emit via channel.
5. Return count. Cancellation: kill child + drop iterator.

### `quality_from_entry` (port)
```rust
fn quality_from_entry(e: &serde_json::Value) -> Option<String> {
    if let Some(h) = e.get("height").and_then(|v| v.as_i64()) {
        if h > 0 { return Some(format!("{}p", h)); }
    }
    let fmt = e.get("format").and_then(|v| v.as_str()).unwrap_or("");
    static RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(\d{3,4})p").unwrap());
    RE.captures(fmt).and_then(|c| c.get(1)).map(|m| format!("{}p", m.as_str()))
}
```

### URL-fallback (when entry lacks `url`/`webpage_url`)
```rust
let url = e.get("url").or_else(|| e.get("webpage_url"))
    .and_then(|v| v.as_str()).map(String::from)
    .unwrap_or_else(|| {
        let id = e.get("id").and_then(|v| v.as_str()).unwrap_or("");
        if channel_url.contains("facebook.com") || channel_url.contains("fb.com") || channel_url.contains("fb.watch") {
            format!("https://www.facebook.com/video/{id}")
        } else {
            format!("https://www.tiktok.com/@_/video/{id}")
        }
    });
```

### Facebook URL normalization (`facebook::normalize_for_listing`)
Port from `facebook_fetcher.py:122-131`:
- if URL already contains `sk=reels` / `sk=videos` / `/reels` / `/videos` → return as-is.
- else append `?sk=reels_tab` (or `&` if URL already has `?`).

### Fallback: rquest scrape (`fallback.rs`)
Only if Phase 01 spike result indicates yt-dlp FB page enumeration is unreliable.
- Build `rquest::Client` with Chrome impersonation.
- GET the page URL (with `?sk=reels_tab`).
- Regex out `/reel/\d+` / `/videos/\d+` / `watch/?v=\d+` from response body (port `_VIDEO_LINK_RE` + cleaners from `facebook_fetcher.py:24-150`).
- One pass — no scrolling (no headless browser). Document this as a known limitation.

## Related Code Files

### Create
- `src-tauri/src/channel/mod.rs`
- `src-tauri/src/channel/ytdlp_list.rs`
- `src-tauri/src/channel/tiktok.rs`
- `src-tauri/src/channel/facebook.rs`
- `src-tauri/src/channel/fallback.rs` (only if needed)
- `src-tauri/tests/channel_quality_from_entry.rs`
- `src-tauri/tests/channel_url_fallback.rs`
- `src-tauri/tests/channel_fb_normalize.rs`

### Read for context
- `channel_fetcher.py` (full)
- `facebook_fetcher.py` (full — for fallback regex set)
- `gui/base_browser_panel.py` / `gui/tiktok_browser_panel.py` / `gui/facebook_browser_panel.py` (for UX expectations)

### Update
- `src-tauri/src/commands.rs` — add `list_channel(url, channel)` and `cancel_channel_listing(id)`.
- `src-tauri/src/lib.rs` — register commands.

## Implementation Steps

### Step 1 — Tauri command
```rust
#[tauri::command]
async fn list_channel(state: State<'_, AppState>, url: String, on_event: Channel<ChannelEvent>) -> Result<u32, String> {
    let token = CancellationToken::new();
    state.channels.lock().insert(url.clone(), token.clone());
    let n = channel::list_channel(&url, token, on_event).await.map_err(|e| e.to_string())?;
    state.channels.lock().remove(&url);
    Ok(n)
}

#[derive(Clone, serde::Serialize)]
#[serde(tag="type", rename_all="snake_case")]
enum ChannelEvent {
    VideoFound { video: VideoInfo },
    Error      { message: String },
    Finished   { total: u32 },
}
```

### Step 2 — `ytdlp_list::run`
1. Build argv (above).
2. Spawn sidecar; collect stdout to bytes with cap.
3. Parse JSON. If parse fails or `entries` empty → return `Ok(0)`.
4. Iterate, emit `VideoFound` per entry, honor cancel token between emits.

### Step 3 — TikTok path
1. Accept `tiktok.com/@user` or bare `@user` (use `build_user_url`).
2. Delegate to `ytdlp_list::run`.

### Step 4 — Facebook path
1. Normalize URL.
2. Try `ytdlp_list::run` once.
3. On 0 entries OR error → fallback (only if Phase 01 spike marked it needed).

### Step 5 — Fallback (conditional)
1. rquest GET → body bytes.
2. Run port of `_VIDEO_LINK_RE`, `_clean_video_url`, `_extract_id`.
3. Dedup, emit each as `VideoFound`.
4. Single pass — no scroll-load. Acceptable trade-off for eliminating Playwright (~150 MB).

### Step 6 — Tests
1. `quality_from_entry`: numeric height, 720p in format, missing both → `None`.
2. URL fallback: tiktok vs facebook context, missing `url` key.
3. FB normalize: vanilla page URL, page with `?sk=videos`, page with `/reels`, edge case `profile.php?id=`.
4. Mock yt-dlp output via fake binary (test fixture) for end-to-end.

## Todo
- [ ] `ytdlp_list::run` parses real yt-dlp JSON
- [ ] TikTok profile listing emits VideoFound stream + Finished
- [ ] FB page listing path picked correctly per spike outcome
- [ ] Cancellation kills the running yt-dlp process
- [ ] Quality string produced when present in entries
- [ ] Tests: 100% pass on quality + url-fallback + normalize matrices

## Success Criteria
- Search a TikTok profile in dev → table populates progressively, all visible.
- Search a public FB page → entries appear (or fallback emits known-page reels).
- Spike-confirmed user-facing UX matches Python parity for the platforms each path covers.

## Risk Assessment
- **FB page enumeration without cookies returns nothing.** Mitigation: prompt the user via Settings to choose a cookie browser; many FB pages need login to list.
- **JSON > 32 MB cap.** Bump to 64 MB if any user reports a hit; surface as a typed error.
- **Fallback scrape becomes brittle when FB changes markup.** Document; the same fragility existed in Playwright. No regression.
- **Drop of scroll-loading reduces FB result count.** Accept; original Playwright-based scroll was capped at 10 cycles. Document the limit explicitly.

## Security
- Same ACL as engine (sidecar-only).
- Body-size cap on rquest fallback (e.g. 5 MB) to defend OOM.

## Next Steps
- Phase 07 wires this into the Channel/Page tab UI.
