# Phase 1 — `health_check.py` module (pure data layer)

**Status:** ✅ complete (2026-05-02) · **Priority:** P1 · **Effort:** M (~3h) · **Risk:** Low

## Context

- Files: new `health_check.py` (~150 LOC), reads `saved_channels_store.SavedChannel`, `history_store.HistoryRecord`, `config.AppConfig`.
- Mirrors `saved_channels_store.py` discipline: **zero Qt imports**, dataclasses + pure functions, atomic disk writes for the cache.

## Goal

Provide a single pure function `compute_health(channels, records, config) -> HealthReport` that returns a list of `HealthIssue` for the 6 signals below. The function is fully unit-testable without Qt and can be invoked from CLI (`python -m health_check`) for debugging.

## Key Insights

- **All signals derive from existing on-disk state.** No new persistence — only one tiny cache file (`data/health_cache.json`) for the 24h yt-dlp PyPI lookup and dismissal IDs.
- `retry_policy.py` already classifies `LoginRequired` — we don't re-classify, just observe whether the last fetch raised it. Persist the last-error class per-channel by appending one field to `SavedChannel`? **No** — keep `SavedChannel` clean. Use a sidecar map in `health_cache.json` keyed by channel URL.
- `cookies_file` mtime check beats parsing the cookie expiry (which yt-dlp fights with anyway).

## Requirements

- Pure-python module, no PySide6/QtCore imports anywhere.
- Returns deterministic `HealthReport` for given inputs.
- Network call (PyPI version) is opt-in via `compute_health(check_yt_dlp=True)`; default reads cached value.
- All file reads are tolerant: missing/corrupt cache → empty cache, never raises.
- One CLI smoke entry: `python -m health_check` prints the report as text.

## Architecture

```
health_check.py
├── @dataclass HealthIssue(id, severity, title, detail, fix_action_kind, fix_action_arg)
│     severity: Literal["info", "warn", "error"]
│     fix_action_kind: Literal["open_path", "open_url", "refresh_channel", "none"]
├── @dataclass HealthReport(issues: list[HealthIssue], computed_at: str)
│     .max_severity() -> "info"|"warn"|"error"|None
├── compute_health(channels, records, config, *, check_yt_dlp=False) -> HealthReport
│     internally calls 6 signal functions:
│       _check_stale_channels
│       _check_auth_walls
│       _check_no_new_downloads
│       _check_login_required_marker
│       _check_cookies_age
│       _check_yt_dlp_version (uses cache; spawns network only if check_yt_dlp=True and cache stale)
├── load_health_cache() / save_health_cache() — mirrors history_store atomic write
└── if __name__ == "__main__": pretty-print report
```

## Related Code Files

**Create:**
- `health_check.py` — main module.

**Read for context:**
- `saved_channels_store.py:66-110` (`SavedChannel` shape, `last_fetched_at`, `last_fetched_video_ids`).
- `history_store.py:29-44` (`HistoryRecord` shape).
- `config.py` (`AppConfig` for `cookies_file`, `tiktok_cookies_file`, `cookie_browser`).
- `retry_policy.py` (`LoginRequired` exception class — observe, don't import in health_check.py).

**Modify:**
- None in this phase. The cache file is created lazily by `health_check.py`.

## Signal Definitions

| ID | Severity | Trigger | Fix action |
|---|---|---|---|
| `stale_fetch` | `info` if 14–30d, `warn` if >30d | `now - last_fetched_at` per channel | `refresh_channel` |
| `auth_wall_likely` | `warn` | `last_fetched_video_ids == []` AND cookies set AND last fetch within 7d | `open_path` (cookies file) |
| `no_new_downloads` | `info` | No `HistoryRecord.downloaded_at` in last 30d for an uploader with ≥1 saved channel | `refresh_channel` |
| `login_required_recent` | `error` | Sidecar map in `health_cache.json` shows last fetch raised `LoginRequired` | `open_path` (cookies file) |
| `cookies_old` | `warn` if >60d, `error` if >120d | `os.path.getmtime(cookies_file)` | `open_path` (cookies file) |
| `yt_dlp_outdated` | `info` if 1 minor behind, `warn` if ≥2 minor or ≥90d old | Cached PyPI version vs `yt_dlp.version.__version__` | `open_url` (releases page) or instructions |

## Implementation Steps

1. Create `health_check.py` with `HealthIssue` + `HealthReport` dataclasses and the `Severity` literal.
2. Implement `_load_cache` / `_save_cache` mirroring `history_store._read_history_file` (tolerant load, atomic write via `tempfile` + `os.replace`).
3. Implement each `_check_*` function — all pure, all take `(channels, records, config, cache)` and return `list[HealthIssue]`. Use `datetime.now(timezone.utc)` for "now"; accept an injectable `now` kwarg for testing.
4. Implement `compute_health` as the orchestrator: loads cache, calls each `_check_*`, optionally refreshes yt-dlp PyPI cache (urllib + 5s timeout, swallow all network errors silently), returns `HealthReport`.
5. Add `record_fetch_outcome(channel_url, exception_class_name)` helper so `download_engine.py` and `channel_fetcher.py` can poke the sidecar map without importing Qt.
6. Add `__main__` block: pretty-print the report (Rich-style fallback to plain `print` if Rich unavailable — keep KISS).
7. Type-check / smoke-run: `python -m health_check` from project root.

## Todo List

- [x] Create `health_check.py` skeleton (dataclasses + module docstring).
- [x] Implement `_load_cache` / `_save_cache` (atomic write).
- [x] Implement 6 `_check_*` signal functions (extracted into `health_signals.py` per the <200-LOC rule).
- [x] Implement `compute_health` orchestrator + `check_yt_dlp` opt-in path.
- [x] Implement `record_fetch_outcome` helper + `dismiss_issue` + public `default_cache_path()`.
- [x] Add `__main__` CLI entry.
- [x] Manual smoke: `python -m health_check` prints non-empty report when fixtures planted.

## Success Criteria

- `import health_check` does not import `PySide6.*`.
- `compute_health([], [], config)` returns a `HealthReport` with `issues == []` and a non-null `computed_at`.
- Each signal function is independently testable (Phase 4 covers this).
- 24h cache prevents re-hitting PyPI within the cache window.

## Risks

| Risk | Mitigation |
|---|---|
| Network call slows app start | Default `check_yt_dlp=False`; the GUI Phase 2 calls with `check_yt_dlp=True` from a worker thread, never the GUI thread. |
| `health_cache.json` corruption | Tolerant load returns empty cache; same pattern as `history_store`. |
| Coupling to retry_policy exception names | Use string-class-name marker, not the class itself. Keeps health_check decoupled. |

## Security Considerations

- PyPI fetch is HTTPS-only; use `urllib.request.urlopen(..., timeout=5)`. Don't follow non-HTTPS redirects. Validate response is JSON before parsing.
- Cookie file paths are read-only access (mtime); never read contents.
- No user input flows into network requests.

## Next Steps

→ Phase 2 wires the data into the status-bar pill.
