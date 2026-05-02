# Phase 4 — PyInstaller spec — Qt6 multimedia plugins

**Status:** completed (manual clean-VM smoke deferred) · **Priority:** P1 · **Effort:** S (~1h) · **Risk:** Med

## Context

- File: `tiktokder.spec` (lines 99-133 — GUI Analysis block).
- The frozen build silently drops Qt plugins not referenced by `hiddenimports` or copied via `collect_data_files`. Multimedia is the easy thing to forget; the dev environment hides the bug.

## Goal

Update `tiktokder.spec` so the PyInstaller bundle ships with `PySide6.QtMultimedia`, `PySide6.QtMultimediaWidgets`, and Qt's Windows multimedia plugins (mediaservice + windows-mediafoundation backend). Verify on a clean Windows test machine before tagging the next release.

## Key Insights

- PyInstaller's PySide6 hook handles **most** Qt modules but the multimedia plugin DLLs (under `PySide6/Qt/plugins/multimedia/`) are easy to miss because they're loaded dynamically by Qt.
- `collect_data_files('PySide6', subdir=os.path.join('Qt', 'plugins', 'multimedia'))` collects the plugin DLLs.
- We only need to add the modules to `hiddenimports` and the plugin dir to `datas`. No new section, no new analysis block.
- CLI build (lines 155-176) **excludes** PySide6 — leave that alone. CLI doesn't need multimedia.

## Requirements

- Frozen GUI exe plays an H.264 mp4 from the Library on a clean Windows 10/11 machine.
- No new warnings on bundle launch.
- CLI bundle size unchanged.
- GUI bundle size growth ≤ 30 MB (multimedia plugins are small).

## Architecture

Pure spec file edits.

```
tiktokder.spec  (GUI Analysis block, lines 99-133)
├── hiddenimports += [
│     'PySide6.QtMultimedia',
│     'PySide6.QtMultimediaWidgets',
│   ]
└── datas += collect_data_files('PySide6', subdir=os.path.join('Qt', 'plugins', 'multimedia'))
```

## Related Code Files

**Modify:**
- `tiktokder.spec` — GUI Analysis block only.

**Read for context:**
- `tiktokder.spec:99-133` (GUI Analysis).
- `tiktokder.spec:69-78` (existing qtawesome / qdarktheme `collect_data_files` patterns).
- `build.py` (build orchestrator — should keep working unchanged).

## Implementation Steps

1. Add a small comment block before the GUI Analysis (around line 96):
   ```python
   # PySide6 multimedia — QMediaPlayer/QVideoWidget/QAudioOutput.
   # Plugin DLLs (windows-mediafoundation, gstreamer, etc.) live under
   # PySide6/Qt/plugins/multimedia/ and are discovered at runtime — must be
   # explicitly collected for frozen builds.
   pyside6_multimedia_plugins = collect_data_files(
       'PySide6', subdir=os.path.join('Qt', 'plugins', 'multimedia')
   )
   ```
2. Append `'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets'` to the GUI `hiddenimports` list (around line 122).
3. Append `+ pyside6_multimedia_plugins` to the GUI `datas` tuple expression (around line 110).
4. Run `python build.py` (or whatever build entry exists). Verify build completes without warnings about missing plugins.
5. **Clean-machine test (manual):** copy `dist/TikTokDer/` to a Windows VM with no Python or Qt installed. Launch, double-click a Library row, confirm playback.

## Todo List

- [x] Add multimedia hidden imports to GUI Analysis.
- [x] Add multimedia plugin `collect_data_files` to GUI Analysis `datas`.
- [x] Comment block explaining why.
- [x] Plugin discovery verified locally — `collect_data_files` returns 2 DLLs (`windowsmediaplugin.dll`, `ffmpegmediaplugin.dll`). Wheel-layout fallback added: tries `plugins/multimedia` first, then `Qt/plugins/multimedia` for older PySide6 wheels.
- [ ] Local rebuild succeeds without errors. (deferred — runs in release flow)
- [ ] Clean-VM smoke test passes. (deferred — runs at next release)
- [ ] Verify CLI bundle size unchanged. (deferred)

## Success Criteria

- `dist/TikTokDer/_internal/PySide6/Qt/plugins/multimedia/` contains DLLs after build.
- Frozen GUI exe plays a Library video on a clean Windows VM.
- CLI exe still launches and exits cleanly (`TikTokDer-CLI.exe --version`).

## Risks

| Risk | Mitigation |
|---|---|
| Plugin DLLs not picked up by `collect_data_files` (PySide6 layout differences) | If subdir collect returns empty, fall back to `glob` over `PySide6.__path__[0]` and add manually. Verify with `ls dist/.../plugins/` after build. |
| GST plugins (Linux/macOS) get pulled in unnecessarily | Acceptable for now — Windows-first scope. Windows runtime won't load them. |
| Bundle size jumps >30 MB | If exceeds, scope `collect_data_files` to Windows-only plugin names. |

## Security Considerations

None — bundling change only.

## Next Steps

→ Phase 5 — tests for schema migration, debounce, fallback path, and stack widget flip.
