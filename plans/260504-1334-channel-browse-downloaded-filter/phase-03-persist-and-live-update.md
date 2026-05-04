# Phase 03 — Persist combo state + live history_changed updates

## Context Links
- Plan overview: [plan.md](plan.md)
- Brainstorm: [`../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md`](../reports/brainstorm-260504-1334-channel-browse-downloaded-filter.md)
- Depends on: [phase-01](phase-01-history-resolver-and-checkmark-column.md), [phase-02](phase-02-downloaded-filter-combo.md)

## Overview
- **Priority:** P1
- **Status:** completed
- **Description:** Add two `AppConfig` string fields, restore combo state on
  launch, save on change, and refresh `✓` column + filter live whenever
  `download_engine.history_changed` fires.

## Key Insights
- `AppConfig` is a plain `@dataclass` — adding fields is one-line each;
  serialization round-trip works automatically (see existing
  `theme_mode`, `quality_default`, `facebook_max_scrolls_default`).
- `history_changed` fires on every successful download; coalesce repeated
  fires during batch downloads with a 100 ms `QTimer.singleShot`.
- Combo restore must `blockSignals` to avoid an unnecessary filter pass
  during startup.

## Requirements
- Functional:
  - Two `AppConfig` fields: `tiktok_browse_downloaded_filter` and
    `facebook_browse_downloaded_filter`. Default `"all"`.
  - Combo state writes back through the existing settings-persist path on
    every `currentIndexChanged`.
  - On `history_changed`: re-render every `✓` cell + re-apply filter.
  - Coalesce: rapid signal bursts collapse to one re-render within 100 ms.
- Non-functional:
  - No I/O on the signal path beyond what `engine` already does.
  - Restore path is idempotent — calling twice does not double-fire filters.

## Architecture
```
config.py  → AppConfig fields added
MainWindow.__init__:
  ├─ panel.set_downloaded_filter(config.<platform>_browse_downloaded_filter)
  ├─ panel.downloaded_combo.currentIndexChanged → save_config slot
  └─ engine.history_changed → panel._on_history_changed (coalesced via QTimer)

BaseBrowserPanel:
  ├─ set_downloaded_filter(mode)        # programmatic, signal-blocked
  ├─ _on_history_changed(): start 100ms one-shot
  └─ _refresh_downloaded_state():
        for row in table:
            video = row.userrole
            update _COL_DOWNLOADED cell + tooltip
        _apply_filters()
```

## Related Code Files
- Modify: `config.py`, `gui/base_browser_panel.py`, `gui/main_window.py`.
- Read for context: existing `MainWindow` config-save wiring (search for
  `save_config` or `settings_changed`).

## Implementation Steps
1. **Add `AppConfig` fields** in `config.py:82` block:
   ```python
   tiktok_browse_downloaded_filter: str = "all"     # all | new | downloaded
   facebook_browse_downloaded_filter: str = "all"
   ```
2. **Add public setter** on `BaseBrowserPanel`:
   ```python
   def set_downloaded_filter(self, mode: str) -> None:
       idx = self.downloaded_combo.findData(mode)
       if idx < 0:
           return
       self.downloaded_combo.blockSignals(True)
       self.downloaded_combo.setCurrentIndex(idx)
       self.downloaded_combo.blockSignals(False)
       self._apply_filters()
   ```
3. **Add coalesced live refresh** on `BaseBrowserPanel`:
   ```python
   self._history_refresh_timer = QTimer(self)
   self._history_refresh_timer.setSingleShot(True)
   self._history_refresh_timer.setInterval(100)
   self._history_refresh_timer.timeout.connect(self._refresh_downloaded_state)

   @Slot()
   def on_history_changed(self) -> None:
       self._history_refresh_timer.start()

   def _refresh_downloaded_state(self) -> None:
       for row in range(self.table.rowCount()):
           title_item = self.table.item(row, _COL_TITLE)
           video = title_item.data(Qt.ItemDataRole.UserRole) if title_item else None
           if isinstance(video, VideoInfo):
               self.table.setItem(row, _COL_DOWNLOADED, self._make_downloaded_item(video))
       self._apply_filters()
   ```
4. **Wire in `MainWindow.__init__`** (after panels exist):
   ```python
   for tab, fld in (
       (self.tiktok_tab,   "tiktok_browse_downloaded_filter"),
       (self.facebook_tab, "facebook_browse_downloaded_filter"),
   ):
       panel = tab.channels_panel.browser_panel
       panel.set_downloaded_filter(getattr(self.config, fld))
       panel.downloaded_combo.currentIndexChanged.connect(
           lambda _i, p=panel, f=fld: self._save_browse_filter(p, f)
       )
       self.engine.history_changed.connect(panel.on_history_changed)
   ```
5. **Add `_save_browse_filter` slot** on `MainWindow`:
   ```python
   def _save_browse_filter(self, panel, field_name: str) -> None:
       setattr(self.config, field_name, panel.downloaded_combo.currentData())
       save_config(self.config)   # use whatever existing saver is in use
   ```
6. **Compile check** + smoke test: change combo on TikTok tab → relaunch
   app → combo restores to chosen state.

## Todo List
- [x] `AppConfig` gains two string fields with defaults.
- [x] `set_downloaded_filter` setter added.
- [x] `on_history_changed` slot + coalescing timer added.
- [x] `_refresh_downloaded_state` re-renders cells + reapplies filter.
- [x] `MainWindow` restores combo state at init.
- [x] `MainWindow` saves combo state on change.
- [x] `MainWindow` connects `engine.history_changed` to both panels.
- [x] py_compile passes.
- [x] Manual: relaunch keeps combo state.
- [x] Manual: completing a download flips its row's `✓` without manual refresh.

## Success Criteria
1. Selecting `New only` on TikTok tab, relaunching app → combo opens on
   `New only`. Same for Facebook independently.
2. Downloading a video that's currently visible in the panel flips its
   `✓` cell within ~100 ms of completion.
3. Filter remains in effect after live refresh (downloaded video disappears
   from `New only` view automatically).
4. No frozen UI during batch downloads (verify with 5+ rapid completions).

## Risk Assessment
- **Risk:** unknown name of existing config saver function.
  - Mitigation: grep for `save_config|write_config|persist` in `config.py`
    and `gui/main_window.py`; use whichever is canonical. Worst case,
    inline a `json.dumps(asdict(config))` write to the same path.
- **Risk:** lambda captures in `connect` could share `panel`/`fld` across
  iterations.
  - Mitigation: default-arg binding in lambda (`p=panel, f=fld`) shown above.
- **Risk:** `history_changed` may fire during shutdown.
  - Mitigation: timer.start() is no-op if widget destroyed; Qt prints a
    benign warning at worst.

## Security Considerations
None — local filesystem config only.

## Next Steps
Phase 04 covers tests + docs sync.
