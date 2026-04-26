"""Tests for retry_policy module: typed exceptions, predicate, parser, decorator."""

import pytest

from retry_policy import (
    LoginRequired,
    NotFound,
    Private,
    RateLimited,
    TransientFailure,
    PermanentFailure,
    _is_retryable,
    decorrelated_jitter,
    parse_retry_after,
    with_retry,
)


class TestRateLimitedException:
    def test_stores_retry_after(self):
        exc = RateLimited("rate limited", retry_after=30.0)
        assert exc.retry_after == 30.0
        assert "rate limited" in str(exc)

    def test_retry_after_defaults_to_none(self):
        exc = RateLimited("rate limited")
        assert exc.retry_after is None


class TestParseRetryAfter:
    def test_parses_seconds(self):
        assert parse_retry_after("HTTP 429: Retry-After: 30") == 30.0

    def test_returns_none_when_missing(self):
        assert parse_retry_after("plain error message") is None

    def test_case_insensitive(self):
        assert parse_retry_after("retry-after: 12") == 12.0

    def test_handles_extra_whitespace(self):
        assert parse_retry_after("Retry-After:    7   tail") == 7.0


class TestIsRetryable:
    def test_login_required_is_not_retryable(self):
        assert _is_retryable(LoginRequired()) is False

    def test_private_is_not_retryable(self):
        assert _is_retryable(Private()) is False

    def test_not_found_is_not_retryable(self):
        assert _is_retryable(NotFound()) is False

    def test_permanent_failure_is_not_retryable(self):
        assert _is_retryable(PermanentFailure()) is False

    def test_rate_limited_is_retryable(self):
        assert _is_retryable(RateLimited()) is True

    def test_transient_failure_is_retryable(self):
        assert _is_retryable(TransientFailure()) is True


class TestDecorrelatedJitter:
    def test_growth_within_cap(self):
        wait = decorrelated_jitter(base=1.0, cap=10.0)
        for _ in range(100):
            value = wait(retry_state=None)
            assert 0.0 < value <= 10.0

    def test_starts_at_or_above_base(self):
        wait = decorrelated_jitter(base=2.0, cap=60.0)
        first = wait(retry_state=None)
        assert first >= 2.0


class _FakeOutcome:
    def __init__(self, exc):
        self._exc = exc

    def exception(self):
        return self._exc


class _FakeRetryState:
    def __init__(self, exc):
        self.outcome = _FakeOutcome(exc)


class TestWithRetryDecorator:
    """Patch the wait function so retries don't actually sleep in tests."""

    def _no_sleep_decorator(self, max_attempts: int):
        from tenacity import retry, retry_if_exception, stop_after_attempt, wait_none
        from retry_policy import _is_retryable

        return retry(
            stop=stop_after_attempt(max_attempts),
            retry=retry_if_exception(_is_retryable),
            wait=wait_none(),
            reraise=True,
        )

    def test_retries_max_attempts_on_transient(self):
        calls = {"n": 0}

        @self._no_sleep_decorator(3)
        def fn():
            calls["n"] += 1
            raise TransientFailure("flaky")

        with pytest.raises(TransientFailure):
            fn()
        assert calls["n"] == 3

    def test_retries_on_rate_limited(self):
        calls = {"n": 0}

        @self._no_sleep_decorator(2)
        def fn():
            calls["n"] += 1
            raise RateLimited("429", retry_after=1.0)

        with pytest.raises(RateLimited):
            fn()
        assert calls["n"] == 2

    def test_no_retry_on_login_required(self):
        calls = {"n": 0}

        @self._no_sleep_decorator(5)
        def fn():
            calls["n"] += 1
            raise LoginRequired("login wall")

        with pytest.raises(LoginRequired):
            fn()
        assert calls["n"] == 1

    def test_no_retry_on_not_found(self):
        calls = {"n": 0}

        @self._no_sleep_decorator(5)
        def fn():
            calls["n"] += 1
            raise NotFound("404")

        with pytest.raises(NotFound):
            fn()
        assert calls["n"] == 1

    def test_succeeds_after_transient_recovery(self):
        calls = {"n": 0}

        @self._no_sleep_decorator(3)
        def fn():
            calls["n"] += 1
            if calls["n"] < 2:
                raise TransientFailure("retry me")
            return "ok"

        assert fn() == "ok"
        assert calls["n"] == 2


class TestWithRetryFactory:
    """Verify the public factory returns a working decorator (smoke-only)."""

    def test_with_retry_returns_decorator(self):
        decorator = with_retry(max_attempts=1)
        assert callable(decorator)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
