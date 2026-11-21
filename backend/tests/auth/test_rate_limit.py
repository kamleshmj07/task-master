"""Tests for the auth rate limiter."""

from task_master.auth.rate_limit import RateLimiter


class TestRateLimiter:
    def test_allows_requests_up_to_the_limit(self) -> None:
        limiter = RateLimiter("2/minute")

        assert [limiter.hit("client"), limiter.hit("client")] == [True, True]

    def test_blocks_requests_over_the_limit(self) -> None:
        limiter = RateLimiter("1/minute")
        limiter.hit("client")

        assert limiter.hit("client") is False

    def test_counts_keys_separately(self) -> None:
        limiter = RateLimiter("1/minute")
        limiter.hit("one")

        assert limiter.hit("two") is True

    def test_reports_window_length(self) -> None:
        assert RateLimiter("5/hour").window_seconds == 3600
