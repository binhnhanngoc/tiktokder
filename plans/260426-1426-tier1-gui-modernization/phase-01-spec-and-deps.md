# Phase 01 — Spec & Dependencies

## Context Links

- Synthesis: `plans/reports/research-summary-260426-1408-modern-python-desktop-gui.md` §1, §3, §6, §8 (Tier-1 items 1–2)
- Spec file: `tiktokder.spec`
- Build script: `build.py`
- Requirements: `requirements.txt`

## Overview

- **Priority:** P2 (foundation)
- **Status:** completed
- **Effort:** ~1h
- Disable UPX in PyInstaller spec; add three MIT/BSD-licensed deps; smoke-test the resulting build.

## Key Insights

- UPX-compressed PyInstaller binaries trigger 30–50% more AV false-positives. Trade ~15–25% bundle growth for far fewer Defender problems.
- `pyqtdarktheme` (MIT), `qtawesome` (MIT), `darkdetect` (BSD-3) are all permissive. Combined ~40 KB on top of existing PySide6 footprint.
- Hidden imports usually unnecessary for these libs (no dynamic discovery), but qtawesome ships icon font data files that PyInstaller's hook normally collects automatically — verify before adding manual `collect_data_files`.

## Requirements

**Functional**
- `requirements.txt` lists pyqtdarktheme, qtawesome, darkdetect with floor versions.
- `tiktokder.spec` has `upx=False` in both `EXE()` calls and the `COLLECT()` block.
- `build.py` runs end-to-end on Windows; `dist/TikTokDer/TikTokDer.exe` launches and shows the existing UI (no theme work yet).

**Non-functional**
- Record bundle size before/after for the dist folder and the zip.
- No code edits to GUI modules in this phase — purely deps/spec.

## Architecture

Pure tooling change. No runtime code touched. Build matrix: source run + onedir frozen build.

## Related Code Files

**Modify**
- `requirements.txt`
- `tiktokder.spec`

**Read for context**
- `build.py`
- `app.py` (sanity-check entry stays the same)

**Create**
- None

**Delete**
- None

## Implementation Steps

1. **Add deps** in `requirements.txt` (alphabetical inside the existing flat list):
   ```
   darkdetect>=0.8.0
   pyqtdarktheme>=2.1.0
   qtawesome>=1.3.0
   ```
2. **Edit `tiktokder.spec`:**
   - Line ~57: `upx=True` → `upx=False` in GUI `EXE()`.
   - Line ~98: `upx=True` → `upx=False` in CLI `EXE()`.
   - Line ~113: `upx=True` → `upx=False` in `COLLECT()`.
3. **Hidden imports check:** add `qtawesome` to GUI `hiddenimports` only if a smoke import test (`python -c "import qtawesome"` inside the frozen exe context) fails after step 4. Default: skip.
4. **Install + freeze sanity:**
   - `pip install -r requirements.txt` in dev env.
   - `python -c "import qdarktheme, qtawesome, darkdetect; print('ok')"`.
5. **Build:** `python build.py`. Capture: build duration, `dist/TikTokDer/` size, `dist/TikTokDer-portable.zip` size.
6. **Smoke test frozen build:** double-click `dist/TikTokDer/TikTokDer.exe`; confirm window opens and closes cleanly. CLI: `dist/TikTokDer/TikTokDer-CLI.exe --help`.
7. **Record metrics** in a short paragraph appended to phase file Todo (size delta + AV scan note if available).

## Todo List

- [x] Update `requirements.txt` with three new deps (substituted `pyqtdarktheme-fork>=2.3.6` for Python 3.13 support; same API/license)
- [x] Flip three `upx=True` flags in `tiktokder.spec`
- [x] `pip install -r requirements.txt`
- [x] Verify imports in source run
- [ ] Run `python build.py` — capture build time + folder size + zip size *(manual follow-up)*
- [ ] Launch frozen GUI exe, confirm no regressions *(manual follow-up)*
- [ ] Launch frozen CLI exe with `--help`, confirm output *(manual follow-up)*
- [ ] Document bundle size delta (before/after) in this file's Todo or a follow-up note *(manual follow-up)*
- [ ] If any frozen run fails on `import qtawesome` → add to spec `hiddenimports`, rebuild *(deferred — only if smoke fails)*

## Success Criteria

- `pip install -r requirements.txt` exits 0 in a fresh venv.
- Frozen GUI launches, frozen CLI prints help.
- Spec has zero remaining `upx=True` lines.
- Size delta recorded (expect +15–25% folder, similar on zip).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| qtawesome icon font data missing in frozen build | Med | Med (icons fail in phase 04) | If failure: add `collect_data_files('qtawesome')` to GUI Analysis `datas`; document in this phase. |
| Bundle size growth pushes dist over the user's perception threshold | Low | Low | Documented trade-off; mitigation belongs in Tier-3 (Inno Setup compresses better than UPX anyway). |
| pyqtdarktheme version drift breaking API (`setup_theme`) | Low | Med | Pin floor `>=2.1.0` (stable API since 2.x); revisit if upstream rewrites. |
| Existing `pip install` breaks because `playwright` is heavy | Low | Low | No change to playwright pin; Tier-1 only adds tiny deps. |

## Security Considerations

- All three new deps are MIT/BSD; no telemetry. Confirmed via researcher-4 §3.
- UPX-off does not change attack surface — it removes a signature pattern AV vendors flag.

## Next Steps

- Phase 02 (tokens + spacing) and Phase 04 (icon helper) can start in parallel once deps install cleanly.
- Phase 03 (theme bootstrap) waits on Phase 02 (consumes tokens).
