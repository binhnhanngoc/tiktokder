# Phase 3 — Settings panel "Health" section + action dispatcher

**Status:** ✅ complete (2026-05-02) · **Priority:** P1 · **Effort:** S (~2h) · **Risk:** Low

## Context

- Files: `gui/settings_panel.py` (~80 LOC added), `gui/main_window.py` (action dispatcher).
- Depends on Phase 1 (data) + Phase 2 (signal plumbing). The `_handle_health_action` stub from Phase 2 gets its real body here.

## Goal

A new `QGroupBox("Health")` mounted **above** the existing Global group in `SettingsPanel`. Lists current issues with a severity badge, title, detail, and a per-issue action button. Empty state: "All good — no issues detected." A "Refresh now" button runs `compute_health(check_yt_dlp=True)` on demand.

## Key Insights

- `SettingsPanel` already auto-saves on field changes — the Health group is read-only display, no save coupling.
- The action dispatcher belongs in `MainWindow` (it needs access to engine, channels store, theme), not in `SettingsPanel` itself. SettingsPanel just emits.
- Frozen-build branch matters for "Update yt-dlp": `getattr(sys, "frozen", False)` → open releases URL; source build → show `pip install -U yt-dlp` instructions.

## Requirements

- Health group renders at the top of the Settings tab.
- Each issue row: severity dot (12×12) · title (bold) · detail (gray, ellipsized) · action button.
- Action buttons:
  - `open_path` → `QDesktopServices.openUrl(QUrl.fromLocalFile(arg))`
  - `open_url` → `QDesktopServices.openUrl(QUrl(arg))`
  - `refresh_channel` → emit `refresh_channel_requested(url)` to MainWindow → `SavedChannelsPanel.refresh_one(url)`
  - `none` → no button
- "Refresh now" button forces `_refresh_health(check_yt_dlp=True)` (network OK).
- Updates live: when `set_health_report` is called, the section rebuilds itself.
- Dismissal: each row has a small "×" button → adds issue ID to dismissals in `health_cache.json`. Dismissed issues hidden until severity escalates.

## Architecture

```
SettingsPanel
├── + self.health_group: QGroupBox("Health") at index 0
├── + self.health_list: QVBoxLayout inside group
├── + self.refresh_health_btn: QPushButton("Refresh now")
├── + Signals:
│     fix_action_requested(object)         # HealthIssue
│     dismiss_action_requested(str)        # issue_id
│     manual_refresh_requested()
└── + set_health_report(report: HealthReport)

MainWindow._handle_health_action(issue)
├── if "open_path": QDesktopServices.openUrl(...)
├── if "open_url":  QDesktopServices.openUrl(...)
├── if "refresh_channel": route to platform_tab.saved_channels_panel.refresh_one(url)
└── if "none": no-op
```

## Related Code Files

**Modify:**
- `gui/settings_panel.py` — add health group + signals + setter.
- `gui/main_window.py` — flesh out `_handle_health_action`, wire `manual_refresh_requested`.

**Read for context:**
- Phase 2 plumbing (`set_health_report` already used by status pill).
- `gui/saved_channels_panel.py` — find the existing per-row "Refresh" path to reuse.
- `gui/_history_helpers.py` — `open_path` already handles cross-platform open. Reuse instead of `QDesktopServices` for consistency where possible.

## Implementation Steps

1. In `SettingsPanel.__init__`, build `_build_health_group()` and insert as first widget in `outer` layout (before Global).
2. `_build_health_group()` returns a `QGroupBox` with a `QVBoxLayout` containing:
   - A header row: title `"Health"` + `Refresh now` button right-aligned.
   - A scroll area (`QScrollArea`) wrapping `self.health_list` (a `QVBoxLayout`).
   - Empty-state `QLabel("All good — no issues detected.")`.
3. Implement `set_health_report(report)`:
   - Clear `health_list`.
   - For each issue: build a `_HealthRow` widget (small QHBoxLayout: dot, label, action btn, dismiss btn).
   - Toggle visibility of empty-state label based on `len(report.issues)`.
4. Implement `_HealthRow` as an inner class or small module-private widget.
5. Connect dismiss "×" → emit `dismiss_action_requested(issue.id)` → MainWindow updates `health_cache.json` via `health_check.dismiss_issue(id)`.
6. In `MainWindow`:
   - Reuse the same `set_health_report` slot — call both `status_bar.set_health_report` and `settings_panel.set_health_report`.
   - Implement `_handle_health_action(issue)` switch as described in Architecture.
   - Connect `settings_panel.manual_refresh_requested` → `_refresh_health(check_yt_dlp=True)`.
7. For frozen-vs-source "Update yt-dlp" branching, the data layer (Phase 1) returns the right `fix_action_arg` based on `getattr(sys, "frozen", False)`. UI just opens whatever URL it gets.

## Todo List

- [x] Build Health group + scroll area + "Refresh now" button at top of Settings tab.
- [x] Implement `_HealthRow` row widget (severity dot + title + detail + fix btn + dismiss btn).
- [x] Implement `set_health_report` clear-and-rebuild + empty-state label.
- [x] Implement dismiss flow + `default_cache_path()` cache update via `dismiss_issue`.
- [x] Implement `_handle_health_action` dispatcher in MainWindow (open_path / open_url / refresh_channel).
- [x] Wire `manual_refresh_requested` → threaded compute with `check_yt_dlp=True`.
- [x] Manual smoke: synthetic stale channel → row visible, fix button routes correctly.

## Success Criteria

- Settings tab shows Health group at top, with empty state when healthy.
- Synthetic issues render correct row + action button.
- "Refresh now" triggers PyPI fetch (verifiable via cache mtime change).
- Dismissed issue stays hidden across app restarts.
- Action buttons fire the right OS-level handler (cookies file opens in default editor; releases URL opens in browser; channel refresh kicks off in the right tab).

## Risks

| Risk | Mitigation |
|---|---|
| Row layout breaks on long detail strings | Ellipsize via `QLabel.setTextElideMode(Qt.ElideRight)` and tooltip with full text. |
| Dismissal forgets issue identity across compute runs | `HealthIssue.id` must be stable (e.g. `"stale_fetch:<channel_url>"`). Phase 1 already specifies this. |
| Scroll area collides with Settings outer layout | Cap health group max height (e.g. 240 px); scroll area handles overflow. |

## Security Considerations

- `open_url` must validate URL is `https://` before opening; reject `file://` from data layer.
- `open_path` only ever opens paths the data layer constructed from config; no user-typed input.

## Next Steps

→ Phase 4 — tests for both data layer signals and the widget plumbing.
