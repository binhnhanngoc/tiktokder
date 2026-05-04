# Phase 2 — Populate Date column from yt-dlp timestamp

## Context Links

- Target: `channel_fetcher.py` (TikTok flat-playlist extraction)
- Display: `gui/base_browser_panel.py::_format_date` already accepts `YYYYMMDD`
- Out of scope: `facebook_fetcher.py` (Playwright scrape — no per-video metadata available without full enrichment pass)

## Overview

- **Priority:** P2
- **Status:** pending
- **Description:** Populate the Date column for TikTok channel listings using `entry["timestamp"]` (epoch) from yt-dlp flat-playlist. Document Facebook gap explicitly.

## Key Insights

- `extract_flat: "in_playlist"` returns minimal metadata. For TikTok, entries usually carry `timestamp` (epoch int) but rarely the pre-formatted `upload_date` string. Current code reads only `upload_date` → almost always None → "—" in the table.
- `_format_date` in `BaseBrowserPanel` expects `YYYYMMDD` (8 chars). Convert epoch → `datetime.utcfromtimestamp(ts).strftime("%Y%m%d")` to match.
- Facebook fetcher uses Playwright DOM scraping — only has href URLs. Adding per-video enrichment would require a yt-dlp `extract_info(url, download=False)` call per video (slow + risk of triggering login walls). Out of scope; declare gap in the docstring.
- Adding a helper `_upload_date_from_entry(entry)` keeps `run()` readable and makes the conversion unit-testable in isolation.

## Requirements

### Functional
- TikTok flat-playlist fetch populates `VideoInfo.upload_date` as `YYYYMMDD` when `timestamp` is present.
- Existing pre-formatted `upload_date` from yt-dlp (if/when present) is preferred over derived value.
- Missing/zero/invalid timestamps → `None` (renders as "—").
- Facebook fetcher leaves `upload_date=None` (unchanged); docstring updated to call out the limitation.

### Non-functional
- Pure helper, no side effects.
- Robust to missing keys, non-int values, future timestamps within reason.

## Architecture

```
ChannelFetcher.run()
  for entry in entries:
    upload_date = entry.get("upload_date") or _upload_date_from_entry(entry)
    VideoInfo(upload_date=upload_date, ...)
```

```python
def _upload_date_from_entry(entry: dict) -> str | None:
    ts = entry.get("timestamp")
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y%m%d")
    except (OverflowError, OSError, ValueError):
        return None
```

## Related Code Files

**Modify:**
- `channel_fetcher.py` — add `_upload_date_from_entry` helper; use it in `run()`.

**Read (no edits):**
- `gui/base_browser_panel.py::_format_date` — confirm format expectation.
- `facebook_fetcher.py` — confirm gap.

**Create:** none.

## Implementation Steps

1. Add `from datetime import datetime, timezone` at top of `channel_fetcher.py`.
2. Add module-private `_upload_date_from_entry(entry: dict) -> str | None` near `quality_from_entry`. Use `datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y%m%d")` (modern API; `utcfromtimestamp` is deprecated 3.12+).
3. In `run()`, replace `upload_date=entry.get("upload_date")` with:
   ```python
   upload_date=entry.get("upload_date") or _upload_date_from_entry(entry)
   ```
4. Add a one-line docstring note in `facebook_fetcher.py` (`FacebookFetcher` class) explicitly documenting that `upload_date` is always `None` because the Playwright scrape has no per-video metadata access; users wanting populated dates need to switch to the (future) yt-dlp-based Facebook path or accept the gap.

## Todo List

- [ ] Add `_upload_date_from_entry` helper.
- [ ] Wire helper into `ChannelFetcher.run()`.
- [ ] Update `FacebookFetcher` docstring with the documented gap.
- [ ] Manual smoke: browse a TikTok channel, confirm Date column shows `YYYY-MM-DD` for non-empty rows.

## Success Criteria

- TikTok browse: Date column populated for the majority of rows (>80% on a typical creator's recent uploads).
- Edge: rows where yt-dlp returns no `timestamp` still show "—" (not a fake date, not a crash).
- `tz=timezone.utc` ensures consistent date across users in different timezones (`upload_date` is conventionally UTC in yt-dlp).
- Facebook browse: unchanged behavior, but the gap is documented.

## Risks

- **Timezone drift**: TikTok `timestamp` is UTC epoch. Using UTC → date may differ by ±1 day from local-time perception near midnight. Acceptable; matches yt-dlp convention.
- **Sparse population on older fetches**: yt-dlp doesn't always include `timestamp` in flat-playlist mode for every uploader. No mitigation — rows fall back to "—" cleanly.
- **Future schema change in yt-dlp**: unlikely but the helper isolates the field name.

## Security Considerations
None.

## Next Steps

- Phase 1 (filter row) consumes this — date filter becomes meaningful.
- Optional follow-up (separate plan): add per-video enrichment for Facebook via a slow background pass. Not in this plan.
