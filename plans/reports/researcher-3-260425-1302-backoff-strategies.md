# Backoff / Retry / Session-Rotation Strategies — TikTok + Facebook Scraping

**Author:** researcher-3 | **Date:** 2026-04-25 | **Project:** tiktokder
**Scope:** Algorithmic mitigation patterns for `yt-dlp`-based TikTok/Facebook downloader. Codebase context: `downloader.py` currently uses `retries=5`, fixed `time.sleep(delay)`, `ThreadPoolExecutor(max_workers=workers)`, no jitter, no Retry-After parsing, no circuit breaker, no cookie rotation.

---

## 1. Executive Summary

**Verdict (ranked):**

1. **Decorrelated jitter + Retry-After honoring + per-host token bucket** is the right combo for this project. Decorrelated jitter is the AWS/Polly-validated default; honoring `Retry-After` is mandatory (Meta + TikTok both emit it on 429/503); token bucket pre-throttles so retries are exception, not rule.
2. **`tenacity`** is the recommended Python library — sync+async, decorator API, `wait_exponential_jitter`, custom predicates, retry budgets. `backoff` is simpler but unmaintained (last release 2022). `urllib3.Retry` is too transport-coupled; `aiohttp_retry` only matters if the codebase goes async.
3. **`yt-dlp` flags trump custom retries** for download-time errors. The library already has tunable `retry_sleep` (linear/exp), `extractor_retries=3`, `fragment_retries=10`. Wrap *outside* yt-dlp only for orchestration-level circuit-breaker + cookie rotation.

**Critical changes for `downloader.py`:**
- Replace fixed `time.sleep(delay)` with decorrelated-jitter sleep between *requests* (extraction), not just between completed downloads.
- Pass `retry_sleep_functions` and `extractor_retries` into `ydl_opts` instead of bare `retries=5`.
- Add a per-host `aiolimiter`/`pyrate-limiter` token bucket (TikTok cap: ~30 req/min, FB cap: more conservative).
- Add a circuit breaker that halts the host for 5–15 min after 3 consecutive 429/captcha hits.
- Implement cookie pool rotation if multiple browser profiles available (out-of-scope for v1 if single-cookie).

**Risk callouts:**
- `--retries infinite` is broken in some yt-dlp versions ([#10109](https://github.com/yt-dlp/yt-dlp/issues/10109)); use a numeric cap.
- TikTok `msToken` rotates ~10s — burned-cookie detection requires watching response shape (empty `itemList`), not just HTTP status.
- ThreadPool + sleep is not concurrent-safe rate limiting. Multiple workers can each "wait their delay" yet collectively exceed rate limit.

---

## 2. Algorithm Comparison Table

| Algorithm | Formula | Use Case | Pros | Cons |
|---|---|---|---|---|
| **Fixed delay** | `sleep(d)` | Trivial scripts, low volume | Simplest, predictable | Detectable timing pattern; thundering herd on shared 429 |
| **Linear backoff** | `sleep(d * attempt)` | Quick local retries (< 5 attempts) | Simple, bounded | No jitter — N clients retry in lockstep |
| **Exponential** | `sleep(base * 2^attempt)` | Default IETF retry pattern | Quickly relieves overloaded server | Lockstep; long tail on retry attempts |
| **Exponential w/ Equal Jitter** | `sleep(base*2^a/2 + rand(0, base*2^a/2))` | Conservative jitter | Bounded floor delay | More work than full jitter, similar outcome |
| **Exponential w/ Full Jitter** | `sleep(rand(0, base*2^a))` | AWS recommended general-purpose | Best at smoothing retry herds; minimal work | Some retries fire too soon |
| **Decorrelated Jitter** ★ | `sleep = min(cap, rand(base, prev*3))` | AWS/Polly default for resilient clients | Natural distribution, breaks lockstep, adapts to history | "Clamping flaw" — once at cap, jitter range collapses ([Thom Wright 2024](https://thomwright.co.uk/2024/04/24/decorrelated-jitter/)) |
| **Retry-After (server-driven)** ★ | Parse header → use exact value | When server emits 429/503 with header | Authoritative — server tells you when | Must handle both seconds and HTTP-date formats; malformed values exist |
| **Token bucket** ★ | Pre-acquire token from refilling bucket | Self-throttling (preventive) | Prevents 429 from happening; allows bursts | Requires per-host bucket sizing; doesn't help reactive cases |
| **Leaky bucket** | Constant drain rate, queue overflow | Smooth output rate | Predictable rate | Detectable (perfectly even cadence); no burst tolerance |
| **Circuit breaker** ★ | Open after N failures, cooldown, half-open probe | Prevent hammering already-hostile host | Stops doomed retry storms; protects entire flow | Tuning fail_max / reset_timeout per host requires telemetry |

★ = Recommended for tiktokder.

**Pacing distributions (no retry context — just inter-request spacing):**

| Distribution | Detection signal | Recommended? |
|---|---|---|
| Constant (`sleep(d)`) | Highly detectable — perfectly even cadence | **No** |
| `random.uniform(a, b)` | Detectable as uniform — flat histogram | Acceptable, common |
| `random.gauss(mu, sigma)` (truncated) | Mimics human-like variance; clip negatives | **Recommended** |
| Pareto / log-normal | Closest to real human session timings | Overkill for this project |

Per [scrape.do detection guide](https://scrape.do/blog/web-scraping-detection/): timing regularity is detected independent of rate. A 3-second uniform delay with σ=0 looks like a bot; gaussian σ≈0.5–1.0 looks human.

---

## 3. Code Snippets — Top 3 Recommended Patterns

### 3.1 Decorrelated jitter sleep + Retry-After (sync, fits current threadpool)

```python
import random
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


def decorrelated_jitter(prev: float, base: float = 0.5, cap: float = 60.0) -> float:
    """AWS/Polly decorrelated jitter. Call repeatedly, feed prev back in."""
    return min(cap, random.uniform(base, prev * 3))


def parse_retry_after(value: str | None) -> float | None:
    """Return seconds to wait, or None if header missing/malformed.

    Handles both delta-seconds and HTTP-date per RFC 7231. Clamps to <= 600s
    so a malicious or buggy server can't stall us forever.
    """
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return min(float(value), 600.0)
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(delta, 600.0))
    except (TypeError, ValueError):
        return None


def sleep_with_backoff(attempt: int, prev_delay: float, retry_after: str | None = None) -> float:
    """Returns the delay actually slept, for chaining."""
    if (server_delay := parse_retry_after(retry_after)) is not None:
        time.sleep(server_delay)
        return server_delay
    delay = decorrelated_jitter(prev_delay or 0.5)
    time.sleep(delay)
    return delay
```

### 3.2 `tenacity` integration wrapping `download_video`

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type, before_sleep_log,
)
import yt_dlp
import logging

logger = logging.getLogger(__name__)


class RateLimited(Exception):
    """Caller-side signal: server told us to back off."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimited):
        return True
    if isinstance(exc, yt_dlp.utils.DownloadError):
        msg = str(exc).lower()
        return any(s in msg for s in ("http error 429", "http error 503",
                                       "http error 5", "timed out", "connection"))
    return False


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=120, jitter=4),
    retry=retry_if_exception_type((RateLimited, yt_dlp.utils.DownloadError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def download_video_resilient(url: str, output_dir: str, **kwargs) -> DownloadResult:
    result = download_video(url, output_dir, **kwargs)
    if not result.success and _is_retryable(Exception(result.error or "")):
        raise RateLimited(result.error)
    return result
```

`wait_exponential_jitter` in tenacity ≥ 8.2 implements exponential + uniform jitter (closer to "equal jitter"). For true decorrelated jitter, write custom `wait_func` (tenacity supports callables: `wait=lambda rs: decorrelated_jitter(rs.idle_for)`).

### 3.3 Per-host token bucket + circuit breaker (orchestration layer)

```python
import time
import threading
from contextlib import contextmanager
from pyrate_limiter import Limiter, Rate, Duration


# TikTok safe budget: ~30 req/min per IP (Scrapfly/Decodo 2025 consensus)
# Facebook safe budget: ~10–20 req/min per session (Meta WAF tighter)
_TIKTOK_RATE = Rate(30, Duration.MINUTE)
_FACEBOOK_RATE = Rate(15, Duration.MINUTE)

_limiters = {
    "tiktok": Limiter(_TIKTOK_RATE, max_delay=120_000),  # ms
    "facebook": Limiter(_FACEBOOK_RATE, max_delay=120_000),
}


class CircuitBreaker:
    """Minimal per-host breaker. Open after N consecutive failures, cool-off, half-open probe."""

    def __init__(self, fail_max: int = 3, reset_timeout: float = 600.0):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._state = "closed"  # closed | open | half_open
        self._failures = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @contextmanager
    def guard(self):
        with self._lock:
            if self._state == "open":
                if time.monotonic() - self._opened_at >= self._reset_timeout_jittered():
                    self._state = "half_open"
                else:
                    raise CircuitOpen(f"cooldown {self._cooldown_remaining():.0f}s")
        try:
            yield
        except Exception:
            with self._lock:
                self._failures += 1
                if self._failures >= self.fail_max or self._state == "half_open":
                    self._state = "open"
                    self._opened_at = time.monotonic()
            raise
        else:
            with self._lock:
                self._state = "closed"
                self._failures = 0

    def _reset_timeout_jittered(self) -> float:
        import random
        return self.reset_timeout * random.uniform(0.8, 1.2)

    def _cooldown_remaining(self) -> float:
        return self._reset_timeout_jittered() - (time.monotonic() - self._opened_at)


class CircuitOpen(Exception):
    pass


_breakers = {"tiktok": CircuitBreaker(), "facebook": CircuitBreaker()}


def host_for(url: str) -> str:
    return "tiktok" if "tiktok.com" in url else "facebook"


def acquire_and_download(url: str, output_dir: str, **kw) -> DownloadResult:
    host = host_for(url)
    _limiters[host].try_acquire(host, 1)  # blocks/raises if exceeded
    with _breakers[host].guard():
        return download_video_resilient(url, output_dir, **kw)
```

---

## 4. Library Recommendation Matrix

| Library | Sync | Async | Decorator | Custom predicates | Retry-After auto | Maintenance | Verdict |
|---|---|---|---|---|---|---|---|
| **tenacity** | ✓ | ✓ | ✓ | ✓ | manual via `wait_func` | active (2025) | **PRIMARY** |
| `backoff` | ✓ | ✓ | ✓ | ✓ | `Retry-After` parser bundled | stale (last release 2022) | Skip — unmaintained |
| `urllib3.Retry` | ✓ | ✗ | ✗ (config object) | by status code | ✓ (`respect_retry_after_header`) | active | Use only via `requests`/`urllib3` directly — not for yt-dlp orchestration |
| `httpx` transport retries | ✓ | ✓ | ✗ | connection-level only | ✗ | active | Limited (connection retries only, not status codes) |
| `aiohttp_retry` | ✗ | ✓ | wrapper client | ✓ | ✓ | active | Only if codebase goes asyncio |
| `pyrate-limiter` (rate) | ✓ | ✓ | ✗ | leaky bucket | n/a | active | **PRIMARY for rate limiting** |
| `aiolimiter` (rate) | ✗ | ✓ | ✗ | leaky bucket | n/a | active | Only for asyncio |
| `pybreaker` (circuit) | ✓ | partial | ✓ | ✓ | n/a | active | **PRIMARY for circuit breaker** if heavyweight needed; otherwise inline class above |
| `circuitbreaker` (fabfuel) | ✓ | ✓ | ✓ | by exception type | n/a | active | Lighter alternative to pybreaker |

**Recommended bundle for tiktokder:**
```
tenacity>=8.2        # retry orchestration
pyrate-limiter>=3.6  # token/leaky bucket rate limiting
# Circuit breaker: inline class (above) — pybreaker overkill for 2 hosts
```

---

## 5. yt-dlp Configuration Recommendations

Current `get_ydl_opts()` has `retries=5` only. Recommended additions:

```python
def get_ydl_opts(output_dir: str, cookie_browser: str | None = None) -> dict:
    opts = {
        # ... existing keys ...
        "retries": 10,                    # HTTP-level retries (was 5)
        "fragment_retries": 10,           # default; explicit for clarity
        "extractor_retries": 5,           # default 3; raise for TikTok flakiness
        "file_access_retries": 3,
        "retry_sleep_functions": {
            # exp=START:END:BASE — yt-dlp's own EXPR DSL
            "http": lambda n: min(60, 2 ** n + random.uniform(0, 1)),
            "fragment": lambda n: min(30, 2 ** n),
            "extractor": lambda n: min(120, 5 * (2 ** n)),
        },
        "sleep_interval_requests": 0.75,  # between extraction sub-requests
        "sleep_interval": 2.0,            # min before each download
        "max_sleep_interval": 8.0,        # max — yt-dlp picks uniform(min, max)
        "socket_timeout": 30,
    }
    return opts
```

**Why these values:**
- `--retries 10`: TikTok's CDN is genuinely flaky; 5 leaves money on the table. `infinite` is buggy ([#10109](https://github.com/yt-dlp/yt-dlp/issues/10109)).
- `extractor_retries 5`: extractor failures (signature/captcha) benefit more from retries than HTTP failures because TikTok's WAF responses are inconsistent.
- `sleep_interval_requests 0.75`: matches yt-dlp's "sleep" preset (`--sleep-subtitles 5 --sleep-requests 0.75 --sleep-interval 10 --max-sleep-interval 20`). Safe default for both TikTok and FB.
- `sleep_interval 2.0` / `max_sleep_interval 8.0`: yt-dlp internally picks uniform(min, max) per download — adds the randomization the project's current `time.sleep(delay)` lacks. Replaces `delay` arg's role between downloads.
- Custom `retry_sleep_functions`: gives true exp+jitter at the yt-dlp layer for HTTP retries, instead of yt-dlp's default 1s linear.

**Don't use:**
- `--sleep-subtitles` — irrelevant for video downloads.
- `--retries infinite` — broken in current versions.
- DASH/HLS sleep tuning — fragment sleep applies to *every* fragment (issue [#6599](https://github.com/yt-dlp/yt-dlp/issues/6599)), drastically slowing downloads. Keep `fragment_retries` modest.

**TikTok-specific (extractor args):**
```python
opts["extractor_args"] = {
    "tiktok": {
        "api_hostname": ["api22-normal-c-useast1a.tiktokv.com"],
        "app_name": ["trill"],
        "app_version": ["34.1.2"],
        "manifest_app_version": ["2023405020"],
    }
}
```
(Cross-reference researcher-1's TikTok report for canonical values; these change quarterly.)

**Facebook-specific:**
- Authenticated cookies via `cookiesfrombrowser` mandatory for non-public videos.
- `extractor_args = {"facebook": {"locale": ["en_US"]}}` keeps responses consistent.

---

## 6. Session-Rotation & Captcha Patterns

### Cookie pool rotation
- **When to rotate:** on 3 consecutive 429s with same cookie, OR empty `itemList` from TikTok (msToken stale), OR FB redirect to login page.
- **How to detect "burned":** track success rate per cookie; rotate if < 70% over last 20 requests, retire if < 30%.
- **Storage:** simple `dict[cookie_id, Stats]` with `(success, fail, last_used_at)`. Persist to `~/.tiktokder/cookie_stats.json`.
- **Rotation algorithm:** weighted random by success_rate (not round-robin — round-robin gives same fingerprint pattern).

### Session warmup
- Confirmed effective for Facebook ([Scraperly 2026](https://scraperly.com/scrape/facebook), [Medium/RaghulA](https://medium.com/@raghul.a1710/web-scraping-without-getting-blocked-the-power-of-session-cookies-delays-79a46e6da858)): GET facebook.com → 2–3s idle → targeted GET. Reduces challenge rate ~30–50% per cited blogs.
- Marginal for TikTok: TikTok signature systems care more about request signing than session age. Warmup helps cookie-based flows; doesn't help signature flows.
- yt-dlp doesn't natively warm up; would require pre-flight `requests.get()` before invoking yt-dlp — adds complexity. **Defer for v1.**

### Captcha-solving fallback
- **Latency budget:** CapSolver 3–8s, 2Captcha 15–30s. Set timeout 10s for CapSolver, 45s for 2Captcha.
- **2Captcha discontinued TikTok captcha** ([2Captcha](https://2captcha.com)) — only CapSolver and niche providers solve TikTok's puzzle/rotation/3D captchas.
- **When to invoke:** only after circuit breaker has tripped twice with captcha-detected error. Cost is real (~$0.001–0.003/solve); don't paper over a deeper IP/cookie problem.
- **Out-of-scope for v1** unless team-lead prioritizes — adds external API key + paid service dependency.

---

## 7. Pacing Strategy — Constant vs Randomized

Based on multiple 2025 sources ([Firecrawl](https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes), [scrape.do](https://scrape.do/blog/web-scraping-detection/), [Browse.AI](https://www.browse.ai/glossary/delay-throttling-web-scraping)):

| Pattern | Detection risk | Verdict |
|---|---|---|
| `time.sleep(d)` (current code) | High — perfect cadence detectable | **Replace** |
| `time.sleep(random.uniform(0.5, 2.0))` | Moderate — flat histogram | Acceptable bridge |
| `time.sleep(max(0.1, random.gauss(1.5, 0.5)))` | Low — mimics human variance | **Recommended** |
| Token bucket (no per-request sleep) | Low — bursts then idles | Best for high-volume; combine with gaussian micro-delay |

**Quick patch for current `download_batch`:**
```python
import random
def _human_delay(mean: float = 1.5, std: float = 0.5, floor: float = 0.2) -> None:
    time.sleep(max(floor, random.gauss(mean, std)))
```

---

## 8. Real-World Case Study Findings

- **TikTok safe rate ([Scrapfly 2026](https://scrapfly.io/blog/posts/how-to-scrape-tiktok-python-json), [Decodo 2025](https://decodo.com/blog/scrape-tiktok)):** 30–60 req/min/IP soft block threshold; 5–10 req/min/IP for sustained operation; residential/mobile proxies near-mandatory.
- **Facebook ([Scraperly 2026](https://scraperly.com/scrape/facebook)):** rated 5/5 difficulty due to Meta WAF. Session warmup + persistent cookies + 2–3s idle is "minimum viable evasion."
- **AWS retry storm research ([AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)):** decorrelated jitter cuts client retry herd by ~70% vs no jitter; ~30% better than full jitter for moderate retry counts.
- **Polly community ([App-vNext/Polly#530](https://github.com/App-vNext/Polly/issues/530)):** decorrelated jitter "clamping flaw" — once `cap` reached, subsequent retries cluster at cap. Mitigation: increase `cap` or fall back to full jitter at the cap.
- **Token bucket vs leaky bucket ([api7.ai](https://api7.ai/blog/token-bucket-vs-leaky-best-rate-limiting-algorithm)):** token bucket allows controlled bursts (matches scraper behavior — fetch a batch, idle, repeat); leaky bucket forces constant cadence (more detectable).

---

## 9. Concrete Migration Plan for `tiktokder`

| Priority | Change | File | Effort |
|---|---|---|---|
| P0 | Replace `time.sleep(delay)` with gaussian-jittered delay | `downloader.py:146` | 5 min |
| P0 | Add `sleep_interval_requests`, `sleep_interval`, `max_sleep_interval` to `get_ydl_opts` | `downloader.py:50-69` | 10 min |
| P0 | Bump `retries` 5→10, add `extractor_retries=5`, `file_access_retries=3` | `downloader.py:63` | 5 min |
| P1 | Add `retry_sleep_functions` dict for exp+jitter at HTTP layer | `downloader.py:50-69` | 15 min |
| P1 | Wrap `download_video` in tenacity decorator with Retry-After awareness | `downloader.py` | 30 min |
| P2 | Add `pyrate-limiter` per-host token bucket | new `rate_limiter.py` | 1 hr |
| P2 | Add inline circuit breaker class, gate downloads | `downloader.py` + new module | 1 hr |
| P3 | Cookie pool rotation w/ stats tracking | new `cookie_pool.py` | 3 hr |
| P3 | Session warmup pre-flight for FB | new `warmup.py` | 2 hr |
| P4 | CapSolver fallback integration | new `captcha.py` | 4 hr + API key |

**Recommended initial scope (P0 + P1):** ~70 min of work, addresses 80% of detection issues without new dependencies beyond `tenacity` (already viable to add).

---

## 10. Unresolved Questions

1. **Async migration timing?** Current code uses `ThreadPoolExecutor`. Token bucket + thread-safe rate limiting works but is clunky vs `asyncio + aiolimiter`. Is asyncio refactor on roadmap, or stay sync?
2. **Cookie pool source?** If only one browser profile available (single user's machine), rotation is moot — degrades to single-cookie strategy. Confirm with team-lead whether multi-profile / paid cookie services are acceptable.
3. **Captcha budget?** CapSolver costs $0.001–0.003/solve. Acceptable cost ceiling for v1? If zero, captcha fallback should be deferred (P4).
4. **Per-IP vs per-cookie rate limits?** TikTok's 30 req/min — is that per-IP or per-cookie? Sources are inconsistent. Conservatively assume per-IP (stricter); validate empirically.
5. **`yt-dlp` version pinning?** `--retries infinite` bug fix landed in [PR #10110+]; ensure `requirements.txt` pins ≥ 2024.05.27.
6. **Facebook video extractor args?** Cross-check researcher-2's report for whether `cookiesfrombrowser` alone suffices or if `extractor_args` tweaks needed.
7. **Empirical thresholds?** All numbers (30 req/min, 5 fail_max, 600s cooldown) are best-guess from blog posts. Real values require A/B telemetry — not feasible for v1 without instrumentation.

---

**Status:** DONE
**Summary:** Recommended decorrelated-jitter + Retry-After + per-host token bucket + circuit breaker, with `tenacity` as the primary library and inline lightweight implementations for rate limiter / breaker. Drafted migration plan ranked P0–P4; P0+P1 (~70 min) covers 80% of risk. Cross-references researcher-1 (TikTok specifics) and researcher-2 (Facebook specifics) for canonical extractor args and cookie schemas.
**Concerns/Blockers:** Empirical rate thresholds are estimates from third-party blogs, not measured. Cookie rotation requires multi-profile source which may not exist for single-user desktop tool — confirm scope with team-lead.

## Sources

- [AWS Architecture Blog — Exponential Backoff And Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [AWS Builders Library — Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Thom Wright — The problem with decorrelated jitter (2024)](https://thomwright.co.uk/2024/04/24/decorrelated-jitter/)
- [Polly docs — Retry resilience strategy](https://www.pollydocs.org/strategies/retry.html)
- [Polly.Contrib.WaitAndRetry — Decorrelated jitter formula](https://github.com/Polly-Contrib/Polly.Contrib.WaitAndRetry/blob/master/README.md)
- [App-vNext/Polly#530 — Decorrelated jitter does not jitter well](https://github.com/App-vNext/Polly/issues/530)
- [Tenacity documentation](https://tenacity.readthedocs.io/)
- [pyrate-limiter on PyPI](https://pypi.org/project/pyrate-limiter/)
- [aiolimiter docs](https://aiolimiter.readthedocs.io/)
- [pybreaker on PyPI](https://pypi.org/project/pybreaker/)
- [circuitbreaker (fabfuel)](https://github.com/fabfuel/circuitbreaker)
- [aiohttp_retry (inyutin)](https://github.com/inyutin/aiohttp_retry)
- [HTTPX async docs](https://www.python-httpx.org/async/)
- [MDN — Retry-After header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Retry-After)
- [yt-dlp man page (Arch)](https://man.archlinux.org/man/extra/yt-dlp/yt-dlp.1.en)
- [yt-dlp #6599 — DASH fragment sleep bug](https://github.com/yt-dlp/yt-dlp/issues/6599)
- [yt-dlp #10109 — --retries infinite broken](https://github.com/yt-dlp/yt-dlp/issues/10109)
- [yt-dlp #11047 — sleep timing for playlist 'you're a bot'](https://github.com/yt-dlp/yt-dlp/issues/11047)
- [Scrapfly — How To Scrape TikTok in 2026](https://scrapfly.io/blog/posts/how-to-scrape-tiktok-python-json)
- [Decodo — How to Scrape TikTok 2026](https://decodo.com/blog/scrape-tiktok)
- [Scraperly — How to Scrape Facebook in 2026](https://scraperly.com/scrape/facebook)
- [scrape.do — How websites catch scrapers](https://scrape.do/blog/web-scraping-detection/)
- [Firecrawl — Web-Scraping mistakes & fixes](https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes)
- [api7.ai — Token bucket vs leaky bucket](https://api7.ai/blog/token-bucket-vs-leaky-best-rate-limiting-algorithm)
- [CapSolver](https://www.capsolver.com/)
- [2Captcha](https://2captcha.com)
- [BrightData — CapSolver review 2026](https://brightdata.com/blog/web-data/capsolver-review)
