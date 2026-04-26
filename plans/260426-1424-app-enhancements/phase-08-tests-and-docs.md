---
title: "Phase 08 — Tests + docs"
priority: P1
effort: 1h 15m
status: planned
depends: [01, 02, 03, 04, 05, 06, 07]
---

# Phase 08 — Tests + Docs Catch-up

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ Success Metrics)
- All prior phases.

## Overview
Final verification gate. Ensure the full test suite passes, add coverage for any gaps left by per-phase tests, and update README + project docs to reflect new layout, Settings options, and History tab.

## Key Insights
- Per-phase TODOs already cover most unit tests. This phase is integration + regression + docs.
- New cross-cutting tests:
  - History v1→v2 migration end-to-end (touched files).
  - Engine: download → record persisted with platform-aware path.
  - Folder layout + dedup smoke (drop a file in flat root + nested, verify dedup picks up both).

## Requirements

### Functional
- All previously-passing tests still pass: `test_tiktokder.py`, `test_config.py`, `test_channel_fetcher.py`, `test_download_engine.py`, `test_facebook_resolver.py`, `test_retry_policy.py`.
- New test files exist and pass:
  - `test_history_records.py` (Phase 01) — schema migration, FIFO cap, record round-trip.
  - `test_path_builder.py` (Phase 02) — slugify, template, fallback.
  - quality + subs/thumb assertions in `test_tiktokder.py` extension (Phase 03).
- New integration test `test_engine_history_integration.py`:
  - Stub `download_video` to return a fake `DownloadResult` + info dict.
  - Run `engine.add_urls`; assert `add_history_record` is called with expected fields.
  - Assert `history_changed` signal fires.
- README updated:
  - Mention sub-tabs.
  - Document new `Default Quality`, `Write subtitles`, `Write thumbnail` settings.
  - Document folder layout: `downloads/{platform}/{uploader}/...`.
  - Mention drag-and-drop and Import/Export.
  - Mention History tab.

### Non-Functional
- Coverage: maintain or improve current `coverage_output.txt` baseline.
- Tests run in <30s on dev machine (skip slow network tests via existing markers).

## Test Catalogue (consolidated)

### Phase 01 deliverables (`test_config.py` + `test_history_records.py`)
- `test_load_history_v1_returns_id_set`
- `test_load_history_v2_returns_id_set`
- `test_load_history_records_returns_records`
- `test_save_history_records_round_trip`
- `test_history_v1_to_v2_migration_lazy`
- `test_history_fifo_cap_at_max_entries`
- `test_history_malformed_json_returns_empty`

### Phase 02 deliverables (`test_path_builder.py`)
- `test_slugify_strips_path_chars`
- `test_slugify_empty_returns_unknown_uploader`
- `test_slugify_truncates_to_80`
- `test_platform_slug_from_url_tiktok`
- `test_platform_slug_from_url_facebook`
- `test_build_output_template_tiktok_with_uploader`
- `test_build_output_template_facebook_no_uploader_falls_back_to_url_slug`
- `test_get_downloaded_ids_walks_recursively`

### Phase 03 deliverables (extension to `test_tiktokder.py`)
- `test_get_ydl_opts_quality_best_default`
- `test_get_ydl_opts_quality_720p_format`
- `test_get_ydl_opts_quality_audio_postprocessor`
- `test_get_ydl_opts_subs_flags_set_when_enabled`
- `test_get_ydl_opts_thumb_flag_set_when_enabled`

### Phase 04 deliverables (`test_channel_fetcher.py` extension)
- `test_video_info_quality_field_populated_when_height_present`
- `test_video_info_quality_field_dash_when_metadata_missing`

### Phase 07 deliverables (new `test_engine_history_integration.py`)
- `test_engine_persists_record_on_success`
- `test_engine_emits_history_changed_signal`
- `test_engine_uses_quality_from_settings`
- `test_engine_dedup_skips_v2_recorded_id`

## Docs Updates

### `README.md` patches
- Section `Output` — replace flat layout example with tree.
- Add `Settings` subsection covering Default Quality, Subs, Thumb.
- Add `History` subsection.
- Add `Drag and Drop` subsection in Quick Start.
- Bump version to `v1.2.0`.

### `docs/` directory (per project rules — review status)
- `docs/codebase-summary.md` (if exists): refresh module list (new `path_builder.py`, `gui/history_tab.py`, etc.).
- `docs/system-architecture.md` (if exists): note 4-tab GUI layout.
- `docs/project-changelog.md` (if exists): append v1.2.0 entry summarizing all 7 features.
- `docs/development-roadmap.md` (if exists): mark this batch as complete.

> Check actual presence of `docs/*.md` before editing. If absent, skip silently — no need to fabricate them per YAGNI.

## Related Code Files

### To Create
- `test_history_records.py`
- `test_path_builder.py`
- `test_engine_history_integration.py`

### To Modify
- `test_tiktokder.py` (quality/subs/thumb extensions, recursive dedup)
- `test_channel_fetcher.py` (quality field)
- `test_download_engine.py` (signal + record assertions if not in new file)
- `README.md`
- `docs/*.md` (only if files exist)

## Implementation Steps
1. Run `pytest -v` to capture pre-phase baseline pass/fail.
2. Author missing tests per catalogue above (most authored within their phase; this step closes any gaps).
3. Run `pytest -v --cov` to confirm coverage hasn't regressed.
4. Update README.
5. Inspect `docs/` — patch any present files; skip absent ones.
6. Run a final manual smoke matching Success Metrics from `plan.md`:
   - Download a TikTok video at 720p → file at `downloads/tiktok/<user>/...` ≤720p height.
   - Download FB video → file at `downloads/facebook/<page>/...`.
   - History tab populates within 1s.
   - Re-queue same URL → marked `Skipped`.
   - Drop `urls.txt` on Download tab → imports.
   - Settings persistence across restart.
7. Commit per phase; final commit `chore: docs + tests catch-up for app-enhancements batch`.

## Todo
- [ ] Capture baseline test pass rate.
- [ ] Author/close-out any per-phase test gaps.
- [ ] Author `test_engine_history_integration.py`.
- [ ] Run full pytest with coverage.
- [ ] Update README sections (Output, Settings, History, Drag-drop).
- [ ] Update `docs/*` if files exist.
- [ ] Manual smoke walk-through.
- [ ] Final per-phase commits + summary commit.

## Success Criteria
- `pytest -v` passes 100% (104 existing + ~20 new).
- Coverage equal or higher than baseline.
- README reflects every new feature without dangling old layout examples.
- Manual smoke checks all pass.
- Plan status changes from `planned` → `completed`.

## Risk & Mitigation
- **Test snowball — too many tests, brittle** — author one happy-path + 1–2 edge cases per feature; not exhaustive enumeration. Per YAGNI.
- **Doc drift between code and README** — verify by running every command in the README during smoke walk-through.
- **`docs/*.md` absence vs presence ambiguity** — script-check existence; don't fabricate files.

## Security
- N/A — test/docs phase. No new attack surface.

## Next Steps
- Mark plan completed: update `plan.md` frontmatter `status: completed`, set `completed: 2026-04-DD`.
- Run `/ck:journal` per workflow Step 10 (handled by orchestration after this phase).
- Open follow-up plan if user requests deferred items: pause/resume, dark mode, scheduling, REST API, dark-mode, mp3 audio option, multi-language subtitles.

## Unresolved Questions
- None at plan-write time. Locked decisions in `plan.md` cover the four open questions from the brainstorm. If user wants to revisit (e.g. raise history cap, switch audio default to mp3), that's a parameter change in `AppConfig` defaults — not a phase rework.
