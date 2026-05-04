# Phase 01 — `update_checker.py` core module

**Priority:** P2 · **Status:** todo · **Effort:** ~1h

## Context Links
- Brainstorm: [`plans/reports/brainstorm-260504-1602-app-update-checker.md`](../reports/brainstorm-260504-1602-app-update-checker.md) — sections "Public API", "Network Specifics"
- SSOT: `version.py` — `__version__`, `__version_info__`

## Overview
Pure-logic module: HTTP fetch (stdlib `urllib.request`), version compare, 24h cache gate. **No Qt imports.** Importable from CLI/tests without a display server. All errors → `None`; never raises.

## Key Insights
- 60 req/hr unauth GitHub limit ≫ 1/day per user → cache makes rate worry moot.
- `/releases/latest` returns 404 when no Release object exists, even if tags exist. Fallback hits `/tags?per_page=10`, filters strict `^v\d+\.\d+\.\d+$`, picks max tuple.
- Tuple compare on `(major, minor, patch)` is correct because `version.py` already enforces SemVer §2 (no leading zeros).
- Module is **frozen-dataclass + 3 functions** — keeps it ~120 LOC and trivially testable.

## Requirements

**Functional:**
- `latest_release(timeout=5.0) -> ReleaseInfo | None` — fetches, parses, returns. Try `/releases/latest` first; on 404 fall back to `/tags`.
- `is_newer(latest, current) -> bool` — strict `>` on `(int,int,int)` tuples.
- `should_check_now(last_check_ts, interval_h=24) -> bool` — `True` when `time.time() - last_check_ts >= interval_h*3600`. `0.0` (never checked) → `True`.
- All network/parse errors caught → return `None`. Tests cover: 200, 404→tags-200, 404→tags-404, timeout, garbage JSON, empty tags list, only pre-release tags.

**Non-functional:**
- Stdlib only.
- File < 200 LOC (target ~120).
- Public API frozen-dataclass `ReleaseInfo` with the five fields specified in brainstorm.
- HTTP headers: `User-Agent: TikTokDer/{__version__}`, `Accept: application/vnd.github+json`.

## Architecture

```
update_checker.py
├── ReleaseInfo (frozen dataclass)
├── _GITHUB_REPO = "binhnhanngoc/tiktokder"
├── _RELEASES_URL / _TAGS_URL constants
├── _SEMVER_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
├── _http_get_json(url, timeout) -> dict | list | None    # private
├── _parse_release_payload(data) -> ReleaseInfo | None    # private
├── _parse_tags_payload(data) -> ReleaseInfo | None       # private (fallback)
├── latest_release(timeout=5.0) -> ReleaseInfo | None
├── is_newer(latest, current) -> bool
└── should_check_now(last_check_ts, interval_h=24) -> bool
```

## Related Code Files

**Create:**
- `update_checker.py` — module per layout above
- `test_update_checker.py` — pytest with `unittest.mock.patch` over `urllib.request.urlopen`

**Read (no edits):**
- `version.py` — for `__version__` in `User-Agent`

## Implementation Steps

1. **Create `update_checker.py`** with module docstring, imports (`json`, `re`, `time`, `urllib.request`, `urllib.error`, `dataclasses.dataclass`).
2. **Define `ReleaseInfo`** (frozen dataclass) with the five fields. Order matters for tests — keep `version` first.
3. **Build `_http_get_json(url, timeout)`** — `urllib.request.Request` with both headers, `urlopen(req, timeout=timeout)`, decode UTF-8, `json.loads`. Catch `urllib.error.URLError`, `urllib.error.HTTPError`, `socket.timeout`, `json.JSONDecodeError`, `UnicodeDecodeError`, `ValueError` → `None`. **HTTPError** must be caught separately to detect 404 vs other failures: re-raise 404 as a sentinel so the caller knows to try the fallback.
   - Cleanest pattern: return `("ok", data)` / `("404", None)` / `("err", None)` tuple, OR set a module-level pattern: `_http_get_json` returns `dict|list|None` for "got something parsable or unrecoverable error", and a sibling `_http_get_json_or_404(url, timeout)` returns the same tuple. Pick the simpler one — recommend the tuple variant since 404 is the only status that matters specially.
4. **Build `_parse_release_payload(data)`** — pull `tag_name`, regex-strip leading `v`, parse 3-int tuple, return `ReleaseInfo` with `is_tag_fallback=False`. Reject if `tag_name` doesn't match `_SEMVER_TAG_RE`.
5. **Build `_parse_tags_payload(data)`** — `data` is a list. Filter each tag's `name` by `_SEMVER_TAG_RE`, parse tuples, pick `max()`. Return `ReleaseInfo(html_url=f"https://github.com/{_GITHUB_REPO}/releases/tag/v{ver}", body="", is_tag_fallback=True)`. If no tags match → `None`.
6. **Build `latest_release(timeout=5.0)`** — call `_http_get_json_or_404(_RELEASES_URL, timeout)`. On `("ok", data)` → `_parse_release_payload`. On `("404", _)` → fall back: `_http_get_json_or_404(_TAGS_URL, timeout)`. On `("err", _)` → `None`.
7. **Build `is_newer(latest, current)`** — one-liner: `return latest > current`.
8. **Build `should_check_now(last_check_ts, interval_h=24)`** — one-liner: `return (time.time() - last_check_ts) >= interval_h * 3600`.
9. **Compile-check** — `python -c "import update_checker"`.
10. **Write `test_update_checker.py`** — patch `urllib.request.urlopen` with `MagicMock` returning a context-manager whose `read()` yields canned bytes; cover the eight cases listed under Requirements.
11. **Run tests** — `python -m pytest test_update_checker.py -v`.

## Todo List

- [ ] Create `update_checker.py` skeleton (imports + dataclass)
- [ ] Implement `_http_get_json_or_404` with proper exception handling
- [ ] Implement `_parse_release_payload`
- [ ] Implement `_parse_tags_payload`
- [ ] Implement public `latest_release`
- [ ] Implement `is_newer`, `should_check_now`
- [ ] Compile-check passes
- [ ] Write `test_update_checker.py` (≥8 test cases)
- [ ] Coverage on all branches (200, 404+tags-200, 404+tags-404, timeout, JSON garbage, empty tags, pre-release-only tags, mixed)
- [ ] All tests green; file < 200 LOC

## Success Criteria

- `python -m pytest test_update_checker.py -v` → all green
- `wc -l update_checker.py` < 200
- `python -c "from update_checker import latest_release; print(latest_release())"` returns `ReleaseInfo(...)` or `None` (against live API or `/tags` fallback) without raising

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| `urlopen` raises `HTTPError` *as a subclass of URLError* — order of except matters | Catch `HTTPError` before `URLError`; check `e.code == 404` for fallback signal |
| Network test flakes against live API | Tests mock `urlopen` exclusively; never hit the network |
| Tag list contains 100+ pre-release tags before any stable | `per_page=10` with stable-only regex is acceptable; if a repo ever has 10+ pre-releases queued before a stable, the fallback will silently miss it (acceptable trade-off; primary path is `/releases/latest`) |
| Body field non-string in response | `dict.get("body", "")` and coerce `str()` defensively |

## Security Considerations

- No auth — public API only. No tokens stored anywhere.
- `User-Agent` is constant `TikTokDer/{__version__}` — no fingerprinting beyond version.
- Response body is markdown rendered later via `QTextBrowser.setMarkdown` (not raw HTML), so even a malicious release body can't execute scripts. Out-of-scope for this phase but worth noting.

## Next Steps

Phase 02 (config persistence) can run in parallel. Phase 03 imports `ReleaseInfo` from this module — must wait.
