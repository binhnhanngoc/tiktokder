# Phase 6 — Hide Thumbnail Setting + README Updates

**Status:** pending · **Priority:** P2 · **Effort:** S (~30 min) · **Risk:** Low

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- Files: `gui/settings_panel.py` (Global section, "Write thumbnail" row), `README.md` (Settings table, History section).
- Depends on: Phase 2 (writethumbnail forced on at the source).

## Goal

Remove the now-vestigial "Write thumbnail" toggle from the Settings UI (cleaner UX since it's always-on). Update README to document the new always-on behavior, schema v3, and the rebuilt Library tab.

## Key Insights

- The actual `writethumbnail=True` is forced in Phase 2 — the setting toggle is already a no-op by the time this phase runs. Removing the UI is purely cosmetic.
- `AppConfig.write_thumbnails` field can stay in the dataclass for now (one phase of grace). Removing it would force a config-migration write; YAGNI.
- README: document schema v3 in the History section; add a brief Library description; remove the "Write thumbnail" row from the Settings table.

## Requirements

- Settings panel no longer renders the "Write thumbnail" checkbox.
- No regression to other settings rows (subtitle toggle, quality, output dir, etc.).
- README accurately reflects: always-on thumbnails, new description+thumbnail_path fields, 3-pane Library, description-aware search.
- `AppConfig.write_thumbnails` stays as a dead-but-harmless field (do not remove yet).

## Architecture

Cosmetic UI removal + documentation sync. No code path consumes the toggle anymore.

## Related Code Files

**Modify:**
- `gui/settings_panel.py` — remove the row that builds the thumbnail checkbox + signal.
- `README.md` — Settings table, History section.

**Read for context:**
- `config.py` — confirm `AppConfig.write_thumbnails` only feeds `downloader.py`'s now-ignored param.

## Implementation Steps

1. **`gui/settings_panel.py`** — locate the "Write thumbnail" QCheckBox + its label/wiring (search for `write_thumbnail` or `Write thumbnail`). Delete:
   - The QCheckBox widget construction.
   - The label/grid placement.
   - The `stateChanged` / `toggled` signal handler.
   - Any imports that go unused after deletion.
   Keep the `AppConfig.write_thumbnails` field untouched.

2. **`README.md` Settings table (line ~106)** — delete the "Write thumbnail" row.

3. **`README.md` Settings table** — under the "Write subtitles (en)" row, add a short line near the "Notes" column or beneath the table:
   > _Note: Thumbnails are always written as sidecar `.jpg`/`.webp` next to each video so the Library can show previews. The setting was removed in v1.4.0._

4. **`README.md` History section (line ~131)** — replace the schema-v2 paragraph with:
   ```markdown
   `data/history.json` persists rich `HistoryRecord` rows (schema v3) including
   platform, uploader, quality, size, downloaded-at timestamp, file path, and
   the new **description** + **thumbnail_path** fields surfaced in the Library
   preview pane. Old v1 (list of bare IDs) and v2 files are auto-migrated on
   first write — no data is lost.
   ```

5. **`README.md` Library description (line ~14)** — extend the bullet:
   ```markdown
   - **Library View** — Per-platform 3-pane: uploader sidebar (★ marks saved
     channels), sortable/filterable history table with thumbnail column, and a
     right-side preview pane showing the large thumbnail, metadata, and full
     description. Filter by quality / date range / size / file status; search
     box matches title, uploader, URL, and description text. Right-click rows
     to open file, open folder, re-download, copy URL, or remove.
   ```

6. **Bump version** in README's `**v1.3.0**` header → `**v1.4.0**` (matches the schema migration). Optional but conventional.

7. Smoke test: launch GUI → Settings tab no longer shows the thumbnail toggle. Subtitle toggle, quality combo, etc. still work.

## Todo List

- [ ] Remove "Write thumbnail" widget + wiring from `settings_panel.py`.
- [ ] Delete the "Write thumbnail" row in README's Settings table.
- [ ] Add "thumbnails always-on" note.
- [ ] Update History section to mention schema v3 + description/thumbnail_path.
- [ ] Update Library View bullet to mention 3-pane + preview + description search.
- [ ] Bump README version to v1.4.0.
- [ ] Smoke-launch GUI; confirm no broken layout in Settings.

## Success Criteria

- Settings panel renders without the thumbnail row; no Python errors at startup.
- README mentions schema v3, always-on thumbnails, and the new Library layout.
- `AppConfig.write_thumbnails` remains in the dataclass (will be cleaned up in a future config-cleanup pass).

## Risks

| Risk | Mitigation |
|---|---|
| Stale references to the removed widget elsewhere | `grep -rn "write_thumbnail" gui/` to find leftovers; remove only unused imports. |
| Future config cleanup forgets to drop the field | Tracked as "Out of Scope" in the plan; future maintenance task. |

## Security Considerations

None.

## Next Steps

→ Phase 7 — write tests for the migration, the new search behavior, and a perf smoke for the table.
