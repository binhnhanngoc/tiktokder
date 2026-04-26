# Phase 04 — History store (SQLite + JSON v2 import)

## Context Links
- Plan: [plan.md](plan.md)
- Source: `history_store.py` (schema v2 + v1 migration), `download_engine.py:247-279` (`_build_record`)
- Phase 02: `config.rs::data_dir()`
- Phase 03 stub: `HistoryGate` trait

## Overview
- **Priority:** High
- **Status:** pending
- **Effort:** 1d
- Replace JSON history with SQLite. One-shot import of legacy `history.json` (both v1 list-of-ids and v2 entries shapes). FIFO cap. Atomic via SQLite transactions.

## Key Insights
- SQLite removes JSON-rewrite cost on every download (currently O(n) on each finish). Indexed lookup of video_id is O(log n).
- Schema v2 fields map 1:1 to columns. `downloaded_at` stays ISO 8601 TEXT (sortable, timezone-preserving).
- `rusqlite` (sync) chosen — simplest. Wrap calls in `tokio::task::spawn_blocking` from the async engine.
- FIFO cap via single SQL: `DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY downloaded_at DESC LIMIT N)`.

## Requirements

### Functional
- `HistoryStore::new(path)` opens or creates the DB; runs schema migrations.
- `contains(video_id) -> bool` for engine dedup.
- `add(record)` inserts and FIFO-trims to `max_entries`.
- `list(filter, search, limit, offset) -> Vec<HistoryRecord>` for the History tab.
- `remove(video_id)` for context-menu remove action.
- `count(filter) -> u64` for stats footer.
- One-shot import: on first launch, if SQLite empty AND legacy `history.json` exists at `data_dir()/history.json` OR `~/.tiktokder/history.json` → import all records, then rename legacy file to `history.json.imported`.

### Non-functional
- `add` latency < 5 ms on a 10k-row DB.
- `list` with search latency < 50 ms.
- DB file < 5 MB at 10k rows.

## Architecture

```
src-tauri/src/history/
├── mod.rs              HistoryStore struct + public API
├── schema.sql          embedded via include_str!
└── import_v2.rs        one-shot JSON → SQLite migrator
```

### Schema

```sql
CREATE TABLE IF NOT EXISTS history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id      TEXT    NOT NULL,
    platform      TEXT,
    uploader      TEXT,
    title         TEXT,
    url           TEXT,
    quality       TEXT,
    file_path     TEXT,
    size_bytes    INTEGER,
    downloaded_at TEXT,                              -- ISO 8601 with tz
    UNIQUE(video_id)                                 -- enforces dedup at DB level
);

CREATE INDEX IF NOT EXISTS idx_history_downloaded_at ON history(downloaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_platform      ON history(platform);
CREATE INDEX IF NOT EXISTS idx_history_uploader      ON history(uploader);

CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT);
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('version', '1');
```

### Rust API
```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct HistoryRecord {
    pub video_id: String,
    pub platform: Option<String>,
    pub uploader: Option<String>,
    pub title: Option<String>,
    pub url: Option<String>,
    pub quality: Option<String>,
    pub file_path: Option<String>,
    pub size_bytes: Option<i64>,
    pub downloaded_at: Option<String>,
}

#[derive(Debug, Default, Clone, serde::Deserialize)]
pub struct HistoryFilter {
    pub platform: Option<String>,
    pub search: Option<String>,           // matches title/uploader/url substring
    pub limit:  Option<u32>,
    pub offset: Option<u32>,
}

pub struct HistoryStore { conn: Mutex<rusqlite::Connection>, max_entries: usize }

impl HistoryStore {
    pub fn open(path: &Path, max_entries: usize) -> rusqlite::Result<Self>;
    pub fn contains(&self, video_id: &str) -> rusqlite::Result<bool>;
    pub fn add(&self, rec: &HistoryRecord) -> rusqlite::Result<()>;
    pub fn list(&self, f: &HistoryFilter) -> rusqlite::Result<Vec<HistoryRecord>>;
    pub fn count(&self, f: &HistoryFilter) -> rusqlite::Result<u64>;
    pub fn remove(&self, video_id: &str) -> rusqlite::Result<()>;
    pub fn clear(&self) -> rusqlite::Result<()>;
    pub fn import_legacy(&self, path: &Path) -> anyhow::Result<usize>;     // returns # imported
}
```

### Engine integration
- `HistoryStore` implements the `HistoryGate` trait from phase 03.
- Engine wraps each `add` in `tokio::task::spawn_blocking`.
- After successful download, engine builds `HistoryRecord` from the info dict (port `_build_record`):
  - `video_id` from yt-dlp `id`.
  - `platform` from `detect_platform(url)`.
  - `uploader` priority: `uploader` → `channel` → `uploader_id` → `creator`.
  - `quality` = if `info.height > 0` → `format!("{}p", height)` else cfg.quality literal.
  - `size_bytes` priority: `requested_downloads[0].filesize` → `filesize_approx` → `info.filesize` → `info.filesize_approx`.
  - `file_path` = `requested_downloads[0].filepath` → `info.filename`.
  - `downloaded_at` = `chrono::Local::now().to_rfc3339()`.

## Related Code Files

### Create
- `src-tauri/src/history/mod.rs`
- `src-tauri/src/history/schema.sql`
- `src-tauri/src/history/import_v2.rs`
- `src-tauri/tests/history_store.rs` (CRUD, FIFO cap, search)
- `src-tauri/tests/history_import.rs` (v1 list, v2 dict, malformed)

### Read for context
- `history_store.py` (full file — schema, atomic write, migration logic)
- `download_engine.py:247-279` (`_build_record`)
- `gui/history_tab.py:218 lines` (filter + search semantics — keep parity)

### Update
- `src-tauri/src/engine/mod.rs` — replace stubbed `HistoryGate` with real `Arc<HistoryStore>`.
- `src-tauri/src/lib.rs` — open store in `setup()`, run import once, manage in app state.

### Cargo deps
```toml
rusqlite = { version = "0.31", features = ["bundled", "chrono"] }   # bundled SQLite ~1 MB
chrono = { version = "0.4", features = ["serde"] }
```

## Implementation Steps

### Step 1 — Schema + open
1. `HistoryStore::open(path)` opens connection (file path under `data_dir()/history.db`), runs `conn.execute_batch(include_str!("schema.sql"))`.
2. Pragmas: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;`.

### Step 2 — CRUD
1. `add` uses `INSERT OR REPLACE INTO history(...) VALUES(?, ?, ...) ON CONFLICT(video_id) DO UPDATE SET ...` — keeps the latest entry per video_id.
2. After insert, run FIFO trim if row count > `max_entries`.
3. `list` builds query dynamically from `HistoryFilter`. Search uses `LIKE '%' || ? || '%' COLLATE NOCASE` against title/uploader/url.
4. `contains` uses `SELECT 1 FROM history WHERE video_id=? LIMIT 1`.

### Step 3 — Legacy import
1. `import_legacy(json_path)` — read file, parse via serde:
   - If top-level array of strings → v1; create one record per id with only `video_id` set.
   - If `{"schema":2,"entries":[...]}` → v2; map each entry through `serde_json::from_value::<HistoryRecord>` (ignore unknown fields).
2. Wrap import in a single SQL transaction.
3. After successful import, rename source file → `history.json.imported.<timestamp>` (don't delete — user safety).
4. Trigger from `lib.rs::setup()`:
   - Try `data_dir()/history.json`; if missing, try `home_dir().join(".tiktokder/history.json")`.
   - Skip if SQLite already has rows (migration is one-shot).

### Step 4 — Tauri commands
```rust
#[tauri::command] fn history_list(state: State<...>, filter: HistoryFilter) -> Result<Vec<HistoryRecord>, String>;
#[tauri::command] fn history_count(state: State<...>, filter: HistoryFilter) -> Result<u64, String>;
#[tauri::command] fn history_remove(state: State<...>, video_id: String) -> Result<(), String>;
#[tauri::command] fn history_clear(state: State<...>) -> Result<(), String>;
```

Register; emit `history:changed` from each mutating command after success (engine emits its own after `add`).

## Todo
- [ ] Schema applies cleanly to a fresh file
- [ ] CRUD round-trips with no UNIQUE conflicts on duplicate inserts
- [ ] FIFO trim caps row count at `max_entries`
- [ ] List returns rows sorted by `downloaded_at DESC`
- [ ] Search matches title/uploader/url substring case-insensitive
- [ ] v1 list-of-ids file imports
- [ ] v2 dict file imports
- [ ] Malformed JSON falls back to empty (logs warning, doesn't crash)
- [ ] Legacy file renamed after import; second startup is a no-op

## Success Criteria
- Drive 50 fake downloads → all visible in History tab in chronological order.
- Search "tiktok" filters as expected; clear search restores all.
- Restart app → state preserved. Legacy `history.json` shows up as `.imported.*` and is no longer ingested.

## Risk Assessment
- **`UNIQUE(video_id)` could collide if a video is downloaded twice.** Use `INSERT OR REPLACE` so the latest record overwrites. Matches Python's set-based dedup behavior.
- **Concurrent writes from parallel downloads.** rusqlite + WAL handles this; wrap each `add` in a short transaction.
- **Disk full on append.** Surface as a toast in UI; engine continues (history is best-effort, never fails the download — match Python).

## Security
- DB file lives under `data_dir()` (per-user); no exposure to other users.
- All SQL parameterized; no string interpolation.
- Search input length capped at 200 chars at command boundary.

## Next Steps
- History tab in phase 07 calls these commands.
