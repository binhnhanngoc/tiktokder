---
title: "TikTok Cookies Parity with Facebook"
description: "Add tiktok_cookies_file (Netscape) parallel to FB cookies.txt; rename cookies_file→facebook_cookies_file; extract apply_cookies() helper."
status: completed
priority: P2
effort: 1.5h
branch: main
tags: [cookies, tiktok, facebook, yt-dlp, settings, parity]
created: 2026-04-27
blockedBy: []
blocks: []
---

# TikTok Cookies Parity — Implementation Plan

## Goal
Mirror FB's `cookies_file` UX onto TikTok so users can supply a Netscape `cookies.txt` as a robust fallback to the existing `cookie_browser` (DB-extraction) path. Defensive fix to lift anonymous rate limits on profile scrapes and downloads.

## Source Report
- `plans/reports/brainstorm-260427-0013-tiktok-cookies-parity.md`

## Out of Scope
- aria2c / external downloader integration (YAGNI, no perf complaint)
- Auto cookie expiry detection (existing `retry_policy.py` classifies `login_required`)
- Auto-export from browser (encrypted Chrome cookies too fragile)
- Unified cookie struct across all platforms (Approach B — defer until 3rd platform)

## Phases

| # | Phase | Priority | Effort | Status | Depends |
|---|-------|----------|--------|--------|---------|
| 1 | Config field + rename + migration shim | P2 | S | completed | — |
| 2 | `apply_cookies()` helper + wire to yt-dlp | P2 | S | completed | 1 |
| 3 | Settings UI path picker | P2 | S | completed | 1 |
| 4 | Tests + README sync | P2 | XS | completed | 2,3 |

## Architecture Decision
- **Precedence:** `cookiefile` (file path) > `cookiesfrombrowser` (browser DB) > none
- **Helper location:** start in `downloader.py`; if file >200 LOC after change, extract to `yt_dlp_helpers.py`
- **Migration:** read old `cookies_file` key on load, write as `facebook_cookies_file` on first save (one-shot shim, can remove in N+2 release)
- **Symmetry:** `tiktok_cookies_file` and `facebook_cookies_file` follow identical naming/UI patterns under their respective Settings groups

## Phase Files
- [Phase 01 — Config + Migration](./phase-01-config-and-migration.md)
- [Phase 02 — Helper + yt-dlp Wiring](./phase-02-helper-and-wiring.md)
- [Phase 03 — Settings UI](./phase-03-settings-ui.md)
- [Phase 04 — Tests + Docs](./phase-04-tests-and-docs.md)

## Success Criteria
- TikTok download with `tiktok_cookies_file` set → `[cookies] Loading cookie jar from ...` in yt-dlp verbose log
- TikTok profile scrape with cookies returns more videos than anonymous baseline on a known large account
- FB cookies path still works after rename (regression-free)
- Old config files (with `cookies_file`) load without error and migrate on save
- All existing tests pass; new test covers `apply_cookies()` precedence
