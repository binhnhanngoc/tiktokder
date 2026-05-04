---
type: brainstorm
date: 2026-05-04
slug: app-update-checker
status: approved
current_version: 1.9.0
repo: github.com/binhnhanngoc/tiktokder
---

# Brainstorm — In-App Update Checker

## Problem Statement

TikTokDer (PySide6 desktop + CLI, currently v1.9.0) ships as a Windows portable ZIP via `build.py`. Users have no in-app way to learn that a new version exists; they must visit the repo manually. Need a lightweight "check for updates" feature that respects YAGNI/KISS — no self-updating, no infrastructure.

## Requirements (Confirmed)

| # | Requirement | Decision |
|---|-------------|----------|
| 1 | Release info source | GitHub Releases API (`/repos/binhnhanngoc/tiktokder/releases/latest`) |
| 2 | Aggressiveness | **Notify only** — link to release page, user installs manually |
| 3 | Trigger | Background on startup (24h-cached) **+** manual via Help menu |
| 4 | Scope | GUI only (CLI users typically `git pull`) |
| 5 | Opt-out | Checkbox in update dialog → `update_check_enabled=False` (default ON, no first-run prompt) |
| 6 | About tab badge | Show update status pill in Help → About (latest / available / unknown) |
| 7 | Release publishing | Adopt Option A: `gh release create` post-tag (~30 sec/release) |

## Approaches Evaluated

### A. Notify-only via GitHub Releases API ✅ CHOSEN
- **Pros:** Zero infra, free, stdlib `urllib` only, ~250 new LOC total, robust to network failure.
- **Cons:** Requires actually publishing GitHub Releases (currently flagged out-of-scope in `release-process.md`).

### B. Notify + in-app ZIP download
- **Pros:** Smoother UX (no browser).
- **Cons:** ~150 extra LOC, need progress UI, raises "where do I extract this?" question. Marginal benefit over `QDesktopServices.openUrl()`.

### C. Full self-update (download + replace + relaunch)
- **Pros:** Best UX in theory.
- **Cons:** Windows file-lock on running EXE, AV false-positives on unsigned PyInstaller binaries, requires helper EXE for swap, code-signing problem becomes critical. **Not viable** for unsigned portable build.

### D. Custom JSON manifest (S3 / GitHub Pages)
- **Pros:** Decoupled from GitHub Releases, supports staged rollouts.
- **Cons:** Hosting + maintenance burden. YAGNI.

## Final Solution

**Notify-only, GitHub Releases API, with `/tags` fallback.**

### Module Layout

| File | Status | LOC est. | Role |
|---|---|---|---|
| `update_checker.py` | new | ~120 | Pure logic (no Qt). Fetch + version compare + cache gate. Stdlib `urllib.request` only. |
| `gui/update_dialog.py` | new | ~90 | `QDialog` with current vs latest, release notes (`QTextBrowser.setMarkdown`), 4 buttons. |
| `gui/main_window.py` | edit | +~40 | Help menu item, `QTimer.singleShot` startup hook, `QThread` worker. |
| `gui/help_dialog.py` | edit | +~30 | About tab: update-status pill (latest / available / unknown) + "Check now" button. |
| `config.py` | edit | +3 fields | Persistence for last-check / skipped-version / opt-out. |

Total: ~280 new LOC, zero new dependencies.

### Public API (`update_checker.py`)

```python
@dataclass(frozen=True)
class ReleaseInfo:
    version: tuple[int, int, int]
    version_str: str          # "1.9.1"
    html_url: str             # release page or repo URL on tag fallback
    body: str                 # markdown release notes ("" if tag fallback)
    is_tag_fallback: bool     # True when /releases/latest 404'd

def latest_release(timeout: float = 5.0) -> ReleaseInfo | None: ...
def is_newer(latest: tuple[int,int,int], current: tuple[int,int,int]) -> bool: ...
def should_check_now(last_check_ts: float, interval_h: int = 24) -> bool: ...
```

All network errors → return `None`. Never raises.

### Network Specifics

- Endpoint 1: `https://api.github.com/repos/binhnhanngoc/tiktokder/releases/latest`
- Endpoint 2 (fallback on 404): `https://api.github.com/repos/binhnhanngoc/tiktokder/tags?per_page=10` → filter `^v\d+\.\d+\.\d+$`, pick highest by tuple compare
- Headers: `User-Agent: TikTokDer/{__version__}`, `Accept: application/vnd.github+json`
- Timeout: 5s connect+read
- Rate budget: 60 req/hr unauthenticated → 24h cache means ~1/day per user, no concern

### Config Additions (`config.py`)

```python
last_update_check_at: float = 0.0       # epoch seconds, 0 = never
skipped_update_version: str = ""        # "1.9.1" if user clicked Skip
update_check_enabled: bool = True       # opt-out flag
```

### Flow Diagram

```
App launch
  └─ MainWindow.show()
      └─ QTimer.singleShot(2000, self._check_updates_background)
          └─ if not update_check_enabled: return
          └─ if not should_check_now(last_update_check_at): return
          └─ QThread → update_checker.latest_release()
              ├─ GET /releases/latest (5s timeout)
              ├─ on 404 → GET /tags fallback
              └─ on any error → return None
          └─ ALWAYS write last_update_check_at = now
          └─ if result and is_newer(result.version, __version_info__):
              if result.version_str != skipped_update_version:
                  show UpdateAvailableDialog (modal, parented)

Help → "Check for Updates…"
  └─ Same worker, but:
      ├─ Ignore should_check_now gate
      ├─ Ignore skipped_update_version gate
      └─ Always show outcome:
          ├─ Newer       → UpdateAvailableDialog
          ├─ Up-to-date  → QMessageBox.information
          └─ Net error   → QMessageBox.warning
```

### UpdateAvailableDialog

- **Layout:** Header (current vs latest), `QTextBrowser` with markdown release notes, opt-out `QCheckBox`, button row.
- **Buttons:**
  - `Open Release Page` → `QDesktopServices.openUrl(html_url)` + close
  - `Skip This Version` → write `skipped_update_version` + close
  - `Remind Me Later` → close
- **Checkbox:** "Don't check automatically" → toggles `update_check_enabled` on close.

### Menu Wiring (`gui/main_window.py:534-571`)

Insert before "About" (after the existing `addSeparator()`):
```python
help_menu.addAction(
    icon("mdi6.update"),
    "Check for &Updates…",
    self._on_check_updates_manual,
)
help_menu.addSeparator()
```

## Implementation Considerations

### Threading
- HTTP call **must** run off main thread (5s timeout could freeze UI). Use `QThread` + signal/slot for result. `QtConcurrent.run` also acceptable but adds dep.
- Dialog construction stays on main thread; signal payload is `ReleaseInfo | None`.

### Markdown Rendering
- PySide6 6.4+ supports `QTextBrowser.setMarkdown(text)` natively. App already requires 6.6.0+ per README — no concern.
- Set `setOpenExternalLinks(True)` so links in release notes open in browser.

### Release Process Update (Required — Confirmed)

Add to `docs/release-process.md` (post-tag), starting with **Option A (manual)**:
```bash
gh release create vX.Y.Z dist/TikTokDer-portable-X.Y.Z.zip \
  --title "vX.Y.Z" --notes-from-tag
```

**Effort:** ~30 sec/release, no code changes. `gh auth login` once.

Future optimization paths if release cadence demands it:
- **Option B** — wire into `build.py --release` flag (~15 min, ~10 LOC)
- **Option C** — `.github/workflows/release.yml` triggered on tag push (~45 min)

Tag fallback in checker remains as a safety net even after Releases are published (covers "tag pushed but `gh release create` forgotten").

### Testing
- Unit: `is_newer`, `should_check_now`, version regex parse, tag-list filtering. Pure functions, easy.
- Integration: mock `urllib.request.urlopen` returning canned JSON for 200, 404, timeout, garbage payload.
- Manual: run app with `last_update_check_at=0` and current `__version__="0.0.1"` to force "newer" path.

### About Tab Badge (`gui/help_dialog.py`)

Add to the About tab (existing `TAB_ABOUT`), under the version line:

```
Version 1.10.0  [● Up to date]      ← green pill when current == latest
Version 1.10.0  [▲ v1.11.0 available]  ← amber pill, clickable → opens dialog
Version 1.10.0  [○ Last checked: 2 days ago]  ← grey pill when offline/stale
                [Check now]                   ← always-visible button
```

- Pill state derives from `(last_update_check_at, latest cached ReleaseInfo, __version_info__)`
- Cache the last `ReleaseInfo` in memory on `MainWindow` so About tab can read it without re-fetching
- "Check now" button → calls `MainWindow._on_check_updates_manual()` (same path as menu item)
- Pill updates live when manual check completes (Qt signal from worker)

## Success Criteria

- [ ] Background check runs at startup, never blocks UI ≥ 100ms
- [ ] Manual menu item works regardless of cache or skip state
- [ ] Network failure (offline/timeout) is silent in background, surfaced in manual mode
- [ ] Skip-version persists across launches
- [ ] Opt-out persists across launches; manual check still works after opt-out
- [ ] No new pip dependencies in `requirements.txt`
- [ ] Works without GitHub Release published (tag fallback)
- [ ] About tab pill reflects current state on open and updates after manual check
- [ ] All new code under 200 LOC per file (per CLAUDE.md rule)

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| GitHub Release not published yet → 404 | High at first | `/tags` fallback (already in design) |
| User offline / corp firewall blocks api.github.com | Medium | Silent fail in background; clear message in manual |
| GitHub API rate limit | Very low | 24h cache; well below 60/hr unauth limit |
| Pre-release tag picked up by `/tags` fallback | Low | Regex `^v\d+\.\d+\.\d+$` excludes `-rc`, `-beta` |
| User running source build with newer `__version__` than published | Low | Tuple compare returns False → silent |
| Modal dialog blocks first launch flow | Low | 2000ms delay after `show()`; only fires when result is positive |

## Out of Scope (Explicit YAGNI)

- Self-replacing EXE / auto-relaunch
- In-app ZIP download with progress bar
- CLI integration (banner, `--check-update` flag)
- Pre-release / beta channel toggle
- Update history log
- Delta/patch updates
- Code signing (separate concern, tracked in release-process.md)

## Next Steps

1. Update `docs/release-process.md`: add `gh release create` step (or commit to `/tags` fallback as primary forever — designer's call).
2. Implement per Module Layout table above.
3. Test against real repo (will currently exercise `/tags` fallback until first GH Release exists).
4. Update `docs/system-architecture.md` to mention `update_checker.py` module.
5. Bump to v1.10.0 (MINOR — new feature, no breaking change).

## Unresolved Questions

_All previously-open questions resolved 2026-05-04:_

1. ✅ Publish GitHub Releases — yes, Option A (manual `gh release create`, ~30 sec/release).
2. ✅ Opt-out default `True` — accepted, no first-run prompt.
3. ✅ About tab badge — yes, add pill + "Check now" button.

No outstanding questions.
