---
title: "Health View — surface platform fragility"
description: "Visible health signals (stale fetches, expired cookies, outdated yt-dlp, login walls) via a status-bar pill + Settings health section."
status: complete
priority: P1
effort: ~1d
branch: main
tags: [gui, observability, saved-channels, cookies, yt-dlp, status-bar, settings]
created: 2026-05-02
completed: 2026-05-02
shipOrder: 1  # ship before in-app-player
blockedBy: []
blocks: []
---

# Health View

## Context

- Origin: brutal-honesty review (turn 1 in this session) — platform breakage is silent today; users only notice when "Refresh" returns zero rows.
- Touches: new `health_check.py`, `gui/status_bar_widget.py`, `gui/settings_panel.py`, `gui/main_window.py` (timer + wiring), tests.
- Reuses on-disk state: `data/saved_channels.json`, `data/history.json`, `cookies.txt` mtime, `yt_dlp.version.__version__`.

## Goal

Replace silent fragility with legible, actionable signals. App start + every channel fetch + 30-min QTimer recompute a `HealthReport`; status-bar pill (green/amber/red) reflects max severity; Settings panel lists issues with one-click fix actions.

## Approved Decisions

| Decision | Choice |
|---|---|
| Data layer | New `health_check.py`, **no Qt imports** (mirrors `saved_channels_store.py`) |
| Signals | 6 (see Phase 1) — all derived from existing on-disk state, **no new persistence** |
| Severity ladder | `info` → `warn` → `error`; pill colors: green / amber / red |
| Pill placement | Left of status text in `StatusBarWidget`, click → popover with issue list |
| Settings placement | New "Health" QGroupBox **at top** of `SettingsPanel`, above Global |
| Refresh cadence | App start + after channel fetch + 30-min `QTimer` |
| yt-dlp version check | Cached 24h on disk (`data/health_cache.json`) — single PyPI fetch per day |
| Action buttons | "Refresh cookies" (open file in OS editor), "Update yt-dlp" (frozen: open releases URL; source: `pip install -U` instructions), "Refresh @user now" (per-channel) |

## Out of Scope

- New persistence schemas for channels or history (everything reads existing data).
- Auto-refreshing cookies (out of scope; legal + browser dependence). Surface only.
- yt-dlp auto-upgrade in frozen builds (link to releases page, don't shell out).
- Notifications/system tray balloons. Status-bar pill is the only ambient surface.
- Fix actions that mutate state beyond what existing UI already does (e.g. no bulk-archive of stale channels — flag them, let user act).

## Phases

| # | Phase | File | Effort | Risk | Status |
|---|-------|------|--------|------|--------|
| 1 | `health_check.py` module — pure data, 6 signals | [phase-01-health-check-module.md](phase-01-health-check-module.md) | M (~3h) | Low | ✅ complete |
| 2 | Status-bar pill — colored dot + click popover | [phase-02-status-bar-pill.md](phase-02-status-bar-pill.md) | S (~1h) | Low | ✅ complete |
| 3 | Settings panel "Health" section + action wiring | [phase-03-settings-health-section.md](phase-03-settings-health-section.md) | S (~2h) | Low | ✅ complete |
| 4 | Tests — pure-python signals + widget smoke | [phase-04-tests.md](phase-04-tests.md) | S (~2h) | Low | ✅ complete |

**Strict order:** 1 → 2 → 3 → 4. UI phases (2, 3) consume the data layer (1).

## Implementation Notes

- Phase 1 split into two files (`health_check.py` 200 LOC + `health_signals.py` 320 LOC) per the project's <200-LOC modularization rule.
- Code review (post-implementation) flagged 3 majors — all fixed before sync-back: (1) `_extract_handle` now scans only the URL path so query-string `@`s can't poison handles; (2) `_check_no_new_downloads` skips channels without an explicit `@handle` (avoids false matches on `profile.php` / numeric IDs); (3) `MainWindow.closeEvent` now stops the 30-min `QTimer` and waits 2s on the global `QThreadPool` to prevent dangling-slot crashes on shutdown.
- Cache writes serialized via a module-level `threading.Lock` so engine-thread `record_fetch_outcome` and the GUI worker's `compute_health` can't drop each other's `dismissed`/`fetch_outcomes` updates.
- Tests: 34 added (26 data-layer + 8 widget). Coverage: `health_check.py` 87%, `health_signals.py` 85%, combined 86%. Full suite: 428/428 pass.

## Dependencies

- `requests` (or `urllib`) for PyPI version check — `urllib` only, **no new dep**.
- `QTimer` (PySide6 builtin) for the 30-min cadence.

## Success Criteria

- [ ] `python -c "import health_check; print(health_check.compute_health(...))"` runs Qt-free and returns a `HealthReport`.
- [ ] Status-bar pill renders green when no issues; amber/red on warn/error.
- [ ] Settings "Health" section lists current issues with severity badges and per-issue action buttons.
- [ ] App start, post-fetch, and 30-min timer all recompute health without UI freeze.
- [ ] Tests cover each of the 6 signals + the pill state machine + the action callbacks.

## Risk Snapshot

| Risk | Mitigation |
|---|---|
| PyPI fetch blocks UI thread | Run in `QThreadPool` (or simple `QThread`); 24h on-disk cache so it almost never runs. |
| Offline/no-network | Treat "PyPI unreachable" as `info`, not `warn`. Don't pollute pill. |
| `cookies.txt` deleted while running | `os.path.exists` guard before mtime read; absent file is its own signal only if `cookie_browser` also unset. |
| User has many stale channels (>50) | Group same-class issues in popover ("12 channels stale"); link expands list. |
| False positives on healthy channels with no new uploads | "30d no new downloads" stays `info` (not `warn`); user can dismiss per-channel. |

## Open Questions

1. Should a dismissed `info` issue stay dismissed across restarts? (Default: yes — store dismissals in `data/health_cache.json` keyed by issue id.)
2. Is "Update yt-dlp" needed in source runs at all, given developers run their own `pip install -U`? (Default: show but soften copy.)
