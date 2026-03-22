## Code Review: Standalone Build & Packaging Changes

### Scope
- Files: `tiktokder.spec`, `build.py`, `downloader.py`, `facebook_fetcher.py`, `gui/channel_browser.py`, `main.py`
- LOC changed: ~130 (code files only, excluding plans/reports)
- Focus: Correctness, security, edge cases, missing dependencies

### Overall Assessment
Solid implementation. The dual-entry-point spec, optional Playwright guard, and ffmpeg warning are well-structured. A few edge cases need attention.

---

### High Priority

**1. `PlaywrightTimeout` undefined when Playwright missing (`facebook_fetcher.py:110`)**

When `PLAYWRIGHT_AVAILABLE = False`, the name `PlaywrightTimeout` is never defined. The early return on line 49 makes this unreachable *today*, but it is fragile -- any refactor that removes the guard will cause a `NameError` at runtime instead of a clean error.

Fix: define a sentinel in the `except ImportError` branch:

```python
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeout = Exception  # fallback so except clause doesn't NameError
```

**2. CLI `--facebook-page` silently passes page URL to yt-dlp (`main.py:73`)**

`--facebook-page` sends the page URL directly to `download_batch()`. yt-dlp cannot enumerate videos from a Facebook page -- it only downloads individual video URLs. The comment on line 68-69 acknowledges this but the code does nothing about it: no Playwright import, no page-scraping logic, no warning. Result: yt-dlp will likely fail with a cryptic extraction error.

Recommendation: Either (a) import and use `FacebookFetcher` in CLI mode (with Playwright check), or (b) print a clear warning that `--facebook-page` currently only works for direct video URLs, not page-level scraping.

**3. `build.py` uses hardcoded relative paths (`build.py:11-12`)**

`shutil.rmtree("build")` and `shutil.rmtree("dist")` operate relative to CWD. If the script is invoked from a different directory (e.g., `python path/to/build.py`), it will clean the wrong directories or fail silently. Consider using `Path(__file__).parent` as the base.

```python
root = Path(__file__).parent
for dirname in ("build", "dist"):
    path = root / dirname
```

---

### Medium Priority

**4. ffmpeg check runs at module import time (`downloader.py:17-22`)**

`shutil.which("ffmpeg")` executes on import, not on first use. This means:
- The warning fires even for `--help` or when the module is imported but not used
- In frozen builds (PyInstaller), `shutil.which` may not find PATH-based executables reliably depending on how the exe is launched

Consider deferring to a lazy check on first `download_video()` call, or wrapping in a function.

**5. `block_cipher = None` is deprecated (`tiktokder.spec:20`)**

PyInstaller deprecated `cipher` argument. It is ignored in modern versions but produces a deprecation warning. Can be removed for cleaner output.

**6. Missing `hookspath` for CLI Analysis (`tiktokder.spec:67-88`)**

GUI Analysis has `hookspath=[]` explicitly, CLI Analysis also has it implicitly (not listed). Consistent but fine. However, neither includes `hooksconfig` -- if any hook needs config in the future, this will be a stumbling point.

---

### Low Priority

**7. Duplicate Playwright error messages**

The "Playwright required" message exists in three places: `facebook_fetcher.py:51-53`, `gui/channel_browser.py:95-97`, and the docstring. Consider extracting to a constant to keep messages in sync.

**8. `build.py` doesn't capture stderr**

`subprocess.run(cmd)` inherits stdout/stderr, which is fine for interactive use. But if build output needs to be logged, `capture_output=True` or `subprocess.PIPE` would be needed.

---

### Positive Observations
- Playwright import guard is clean and idiomatic
- Dual entry-point spec with shared COLLECT is well-designed for onedir bundling
- curl_cffi + certifi + yt_dlp hidden imports are correctly handled
- Excluding playwright (~200MB) from build is the right call
- ffmpeg warning message is user-friendly and actionable

### Recommended Actions (prioritized)
1. **Fix** `PlaywrightTimeout` fallback definition -- prevents future NameError
2. **Fix** CLI `--facebook-page` to warn/fail clearly for page-level scraping
3. **Fix** `build.py` to use `__file__`-relative paths
4. **Consider** deferring ffmpeg check to first download call
5. **Consider** removing deprecated `block_cipher`

### Unresolved Questions
- Is `--facebook-page` intended for page scraping (requires Playwright, not available in CLI) or just individual Facebook video URLs? The CLI has no Playwright integration path.
- Should the frozen build bundle ffmpeg, or is PATH-lookup sufficient for the target audience?
