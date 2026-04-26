---
title: "Phase 04 — Channel/Page sub-tab split"
priority: P0
effort: 1h
status: planned
depends: []
---

# Phase 04 — Channel/Page Sub-Tab Split + Quality Column

## Context Links
- Brainstorm: `plans/reports/brainstorm-260426-1417-app-enhancements.md` (§ Channel UX, § Quality column)
- Affected file: `gui/channel_browser.py` (currently 182 LOC — splitting required to stay <200 per file)

## Overview
Split monolithic `ChannelBrowser` into two platform-specific panels (`tiktok-browser-panel.py`, `facebook-browser-panel.py`), wrapped in a `QTabWidget` parent (`channel_browser.py`). Add `Quality` column populated cheap (yt-dlp flat metadata only — no extra calls). Each panel persists its last URL across tab switches.

## Key Insights
- Existing `ChannelBrowser` already routes by `detect_platform`; the dispatch logic moves into the parent.
- ~70% of code is shared (table layout, row formatting, select/deselect, emit signal). Extract into a `_BaseBrowserPanel` mixin/superclass to keep DRY.
- Quality column: yt-dlp's `extract_flat="in_playlist"` returns `height`/`format` info inconsistently. We display `height` if present (`"720p"`), else `—`. No extra network calls. **Cheap-only contract** must be preserved.
- Last-URL persistence per panel is in-memory only this session (no config write). Acceptable per brainstorm.

## Requirements

### Functional
- Top-level "Channel / Page" tab now contains a `QTabWidget` with two sub-tabs: `TikTok` and `Facebook`.
- Each sub-tab has its own URL input, Browse button, video table, and selection controls.
- Each panel emits `download_requested(list[str])` independently; parent re-emits to MainWindow.
- Switching sub-tabs preserves URL text and table contents.
- Video table includes `Quality` column (after Duration, before Views).
- Quality value: from `entry.get("height")` if int → `f"{h}p"` (e.g. `720p`); else from `entry.get("format")` first numeric height match; else `"—"`.

### Non-Functional
- Each new GUI file ≤ 200 LOC.
- Top-level `channel_browser.py` becomes a thin parent wrapper ≤ 80 LOC.
- No regression: `MainWindow.channel_browser.url_input` and `MainWindow.channel_browser._on_browse()` remain valid (or replaced with equivalent shim) — see step 6.

## Architecture

### File Layout
```
gui/
├── channel_browser.py             (was: monolith. now: thin parent ~70 LOC)
├── browser-panels/                (new sub-package)
│   ├── __init__.py
│   ├── base_browser_panel.py      (shared logic ~120 LOC)
│   ├── tiktok_browser_panel.py    (~60 LOC)
│   └── facebook_browser_panel.py  (~80 LOC, includes PLAYWRIGHT_AVAILABLE check)
```

> **Naming:** Per project convention (kebab-case for Python is non-standard; the repo already uses snake_case e.g. `download_engine.py`, `channel_fetcher.py`). New files use **snake_case** to match.

Revised:
```
gui/
├── channel_browser.py
├── base_browser_panel.py
├── tiktok_browser_panel.py
└── facebook_browser_panel.py
```

### Class Hierarchy
```
BaseBrowserPanel(QWidget)        # url input, table, select/deselect, _on_video_found, _on_download
├── TikTokBrowserPanel           # ChannelFetcher wiring; placeholder text
└── FacebookBrowserPanel         # FacebookFetcher wiring; PLAYWRIGHT_AVAILABLE guard

ChannelBrowser(QWidget)          # holds QTabWidget with two sub-panels
  emits download_requested via re-emit from each panel
  exposes .url_input (alias to active panel's input) and _on_browse() shim for back-compat
```

### Quality Column Population
```python
def _quality_from_entry(entry: dict) -> str:
    h = entry.get("height")
    if isinstance(h, int) and h > 0:
        return f"{h}p"
    fmt = entry.get("format") or ""
    m = re.search(r"(\d{3,4})p", fmt)
    return f"{m.group(1)}p" if m else "—"
```

`VideoInfo` (in `channel_fetcher.py`) gains a `quality: str | None = None` field. `ChannelFetcher.run` and `FacebookFetcher.run` populate it from flat metadata.

## Related Code Files

### To Create
- `gui/base_browser_panel.py` — shared widget logic.
- `gui/tiktok_browser_panel.py` — TikTok-specific instantiation.
- `gui/facebook_browser_panel.py` — Facebook-specific (Playwright check, error message).

### To Modify
- `gui/channel_browser.py` — strip down to parent `QTabWidget` wrapper. Re-export `ChannelBrowser` for `MainWindow` import compatibility.
- `channel_fetcher.py` — `VideoInfo.quality: str | None = None`; populate in `run()`.
- `facebook_fetcher.py` — same `quality` population.
- `gui/main_window.py` — minor: pass cookie_browser to inner panels via `ChannelBrowser` constructor (already does).

### Not Touched This Phase
- `download_engine.py`, `downloader.py` — quality column is metadata-only; download path unchanged.

## Implementation Steps
1. Create `gui/base_browser_panel.py` extracting shared widgets (URL input, table, select buttons, signals).
2. Add `Quality` column (index 3) to base table; update column count from 5 → 6: `["", "Title", "Duration", "Quality", "Views", "Date"]`.
3. Add `_quality_from_entry` helper.
4. Create `gui/tiktok_browser_panel.py` extending base, wires `ChannelFetcher`.
5. Create `gui/facebook_browser_panel.py` extending base, wires `FacebookFetcher` + Playwright guard.
6. Rewrite `gui/channel_browser.py` as thin `QTabWidget` parent. Provide `url_input` property that returns the *currently active sub-panel's* QLineEdit (so `MainWindow._on_channel_url` shim still works); provide `_on_browse()` that activates the right sub-tab based on detected platform and forwards.
7. Add `quality: str | None` to `VideoInfo` dataclass.
8. Populate `quality` in both fetchers.
9. Run app smoke: paste a TikTok channel URL, switch to FB sub-tab, paste FB page URL, verify both panels independent.
10. Run `pytest test_channel_fetcher.py -v`.

## Todo
- [ ] Create `base_browser_panel.py`.
- [ ] Create `tiktok_browser_panel.py`.
- [ ] Create `facebook_browser_panel.py`.
- [ ] Rewrite `channel_browser.py` as parent wrapper with sub-panel state preservation.
- [ ] `VideoInfo.quality` field.
- [ ] Populate quality in `channel_fetcher.py` + `facebook_fetcher.py`.
- [ ] `MainWindow._on_channel_url` shim verification.
- [ ] Manual app smoke (TikTok then FB) — confirm tab state persists.
- [ ] Run targeted pytest.

## Success Criteria
- `gui/channel_browser.py` ≤ 80 LOC.
- Each new panel file ≤ 200 LOC.
- Pasting `https://www.tiktok.com/@user` activates TikTok sub-tab (when entered via Download tab cross-link); pasting an FB page activates Facebook sub-tab.
- Quality column shows e.g. `720p` for entries with height metadata, `—` otherwise.
- No regression: existing `test_channel_fetcher.py` passes.
- Switching sub-tabs preserves URL text + table.

## Risk & Mitigation
- **`MainWindow` cross-link `_on_channel_url` calls `channel_browser._on_browse()`** — shim must dispatch to active sub-panel. Mitigation: document and unit-test the shim.
- **PLAYWRIGHT_AVAILABLE check duplicated in two places** — Facebook panel owns the check; parent does not check.
- **Table column index changes break test assertions** — update tests in same commit.

## Security
- No new external input handled; quality is read from yt-dlp metadata only.

## Next Steps
- Phase 07 Polish: drag-drop URLs land on Download tab regardless of which sub-tab is active here.
- Phase 08 docs: update README to mention sub-tabs.
