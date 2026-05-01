# Phase 5 — Search Box Matches Description Text

**Status:** pending · **Priority:** P2 · **Effort:** XS (~10 min) · **Risk:** Low

## Context

- Brainstorm: [`../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md`](../reports/brainstorm-260427-1320-library-thumbnails-descriptions.md)
- File: `gui/library_panel.py:344-347` (search match logic).
- Depends on: Phase 1 (schema), Phase 2 (data populated).

## Goal

Extend the existing search box's substring match to include `record.description` alongside title / uploader / URL.

## Key Insights

- Match logic today (line 345): `hay = " ".join(filter(None, [r.title, r.uploader, r.url])).lower()`. One-line change to add description.
- Search input placeholder text should reflect the new behavior so users discover it.
- No new widget, no debounce changes (existing 200ms debounce timer covers it).

## Requirements

- Typing a substring that matches description text returns the record.
- Case-insensitive.
- Title / uploader / URL match still works exactly as before.
- Empty / None description does not raise or false-match.

## Architecture

Pure predicate edit. The filter pipeline at `_apply_filters` is unchanged in shape.

## Related Code Files

**Modify:**
- `gui/library_panel.py` — one-line change in the search match block; placeholder text update.

## Implementation Steps

1. **`gui/library_panel.py:147`** — change placeholder:
   ```python
   self.search_input.setPlaceholderText("Search title, uploader, URL, description…")
   ```

2. **`gui/library_panel.py:345`** — add description to the haystack:
   ```python
   if needle:
       hay = " ".join(filter(None, [r.title, r.uploader, r.url, r.description])).lower()
       if needle not in hay:
           continue
   ```

3. Smoke test: type a phrase from a known Facebook description; row appears. Clear search; full table returns.

## Todo List

- [ ] Update `setPlaceholderText` to mention description.
- [ ] Append `r.description` to the haystack list.
- [ ] Smoke test against a video with a known description.

## Success Criteria

- Typing 5+ chars unique to a description returns exactly that record.
- Title / uploader / URL searches behave identically to before.
- No exception thrown on rows where `description is None`.

## Risks

| Risk | Mitigation |
|---|---|
| Long descriptions slow down filtering on 10k rows | Substring + lowercase is O(n) per row; 10k × ~2 KB = 20 MB scan = sub-100 ms on a typical CPU. Acceptable. If profiling shows otherwise, cache lowercase haystack on the record at load time. |

## Security Considerations

None — local string operation.

## Next Steps

→ Phase 6 — clean up the now-vestigial thumbnail toggle in Settings + update README.
