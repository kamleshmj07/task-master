"""Tests for security headers, API-wide rate limits and security logs."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from task_master.config import Settings
from task_master.main import create_app
from tests.conftest import clear_rate_limit_windows

pytestmark = pytest.mark.anyio


def make_settings(**fields: object) -> Settings:
    """Test settings with the given overrides."""
    base: dict[str, object] = {
        "environment": "test",
        "cors_origins": ["http://test.local"],
        "database_url": SecretStr("postgresql+asyncpg://unused@localhost/unused"),
        "auth_secret": SecretStr("test-auth-secret"),
    }
    return Settings.model_validate(base | fields)


def client_for(settings: Settings) -> AsyncClient:
    """An HTTP client for an app built from `settings` (no lifespan)."""
    transport = ASGITransport(app=create_app(settings))
    return AsyncClient(transport=transport, base_url="https://test")


class TestHeaders:
    async def test_every_response_is_hardened(self) -> None:
        async with client_for(make_settings()) as client:
            response = await client.get("/health")

        assert {
            name: response.headers.get(name)
            for name in (
                "x-content-type-options",
                "x-frame-options",
                "content-security-policy",
                "cache-control",
            )
        } == {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
            "cache-control": "no-store",
        }

    async def test_hsts_only_in_production(self) -> None:
        async with client_for(make_settings()) as client:
            response = await client.get("/health")

        assert "strict-transport-security" not in response.headers

    async def test_hsts_in_production(self) -> None:
        settings = make_settings(
            environment="production",
            cors_origins=["https://app.example.com"],
            auth_secret=SecretStr("x" * 32),
        )
        async with client_for(settings) as client:
            response = await client.get("/health")

        assert response.headers["strict-transport-security"].startswith("max-age=")

    async def test_errors_are_hardened_too(self) -> None:
        async with client_for(make_settings()) as client:
            response = await client.get("/nope")

        assert (response.status_code, response.headers["x-frame-options"]) == (
            404,
            "DENY",
        )


class TestProductionSurface:
    @pytest.mark.db
    async def test_hides_the_api_schema_in_production(self, migrated_db: str) -> None:
        settings = make_settings(
            environment="production",
            cors_origins=["https://app.example.com"],
            auth_secret=SecretStr("x" * 32),
            database_url=SecretStr(migrated_db),
        )
        try:
            async with client_for(settings) as client:
                response = await client.get("/openapi.json")
        finally:
            await clear_rate_limit_windows(migrated_db)

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "fields",
        [
            {"cors_origins": ["http://app.example.com"]},
            {"cors_origins": []},
            {"cors_origins": ["*"]},
            {"auth_secret": SecretStr("short")},
        ],
    )
    def test_refuses_development_defaults_in_production(
        self, fields: dict[str, object]
    ) -> None:
        production = {
            "environment": "production",
            "cors_origins": ["https://app.example.com"],
            "auth_secret": SecretStr("x" * 32),
        }

        with pytest.raises(ValueError, match="Production"):
            make_settings(**(production | fields))


class TestRateLimits:
    async def test_reads_are_limited_per_session(self) -> None:
        async with client_for(make_settings(api_rate_limit="2/minute")) as client:
            headers = {"Authorization": "Bearer not-a-real-token"}
            statuses = [
                (await client.get("/nope", headers=headers)).status_code
                for _ in range(3)
            ]

        assert statuses == [404, 404, 429]

    async def test_sessions_have_separate_budgets(self) -> None:
        async with client_for(make_settings(api_rate_limit="1/minute")) as client:
            first = await client.get("/nope", headers={"Authorization": "Bearer a"})
            second = await client.get("/nope", headers={"Authorization": "Bearer b"})

        assert (first.status_code, second.status_code) == (404, 404)

    async def test_writes_have_their_own_budget(self) -> None:
        settings = make_settings(
            api_rate_limit="1/minute", api_write_rate_limit="1/minute"
        )
        async with client_for(settings) as client:
            headers = {"Authorization": "Bearer a"}
            await client.get("/nope", headers=headers)
            write = await client.post("/nope", json={}, headers=headers)
            second_write = await client.post("/nope", json={}, headers=headers)

        assert (write.status_code, second_write.status_code) == (404, 429)

    async def test_new_tokens_cannot_dodge_the_ip_budget(self) -> None:
        async with client_for(make_settings(api_ip_rate_limit="2/minute")) as client:
            statuses = [
                (
                    await client.get(
                        "/nope", headers={"Authorization": f"Bearer made-up-{n}"}
                    )
                ).status_code
                for n in range(3)
            ]

        assert statuses == [404, 404, 429]

    async def test_health_is_never_limited(self) -> None:
        async with client_for(make_settings(api_rate_limit="1/minute")) as client:
            statuses = [(await client.get("/health")).status_code for _ in range(3)]

        assert statuses == [200, 200, 200]

    async def test_says_when_to_retry(self) -> None:
        async with client_for(make_settings(api_rate_limit="1/minute")) as client:
            await client.get("/nope")
            response = await client.get("/nope")

        assert response.headers["retry-after"] == "60"


@pytest.mark.db
class TestSharedLimits:
    """Production keeps counters in Postgres, so several processes can run."""

    async def test_two_api_processes_share_one_budget(self, migrated_db: str) -> None:
        settings = make_settings(
            environment="production",
            cors_origins=["https://app.example.com"],
            auth_secret=SecretStr("x" * 40),
            database_url=SecretStr(migrated_db),
            api_ip_rate_limit="2/minute",
        )
        try:
            async with client_for(settings) as first, client_for(settings) as second:
                statuses = [
                    (await first.get("/nope")).status_code,
                    (await second.get("/nope")).status_code,
                    (await first.get("/nope")).status_code,
                ]
        finally:
            await clear_rate_limit_windows(migrated_db)

        assert statuses == [404, 404, 429]


class TestProxies:
    async def test_trusted_proxy_passes_on_the_client_address(self) -> None:
        settings = make_settings(
            trusted_proxies=["127.0.0.1"], api_rate_limit="1/minute"
        )
        transport = ASGITransport(app=create_app(settings), client=("127.0.0.1", 1))
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            first = await client.get(
                "/nope", headers={"X-Forwarded-For": "203.0.113.1"}
            )
            other = await client.get(
                "/nope", headers={"X-Forwarded-For": "203.0.113.2"}
            )

        # Different clients behind one proxy get their own budgets.
        assert (first.status_code, other.status_code) == (404, 404)

    async def test_untrusted_forwarded_header_is_ignored(self) -> None:
        settings = make_settings(api_rate_limit="1/minute")
        transport = ASGITransport(app=create_app(settings), client=("198.51.100.7", 1))
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            await client.get("/nope", headers={"X-Forwarded-For": "203.0.113.1"})
            spoofed = await client.get(
                "/nope", headers={"X-Forwarded-For": "203.0.113.2"}
            )

        assert spoofed.status_code == 429


class TestSecurityLogs:
    async def test_logs_refusals_without_personal_data(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="task_master.security")
        async with client_for(make_settings()) as client:
            await client.post(
                "/auth/mobile/refresh",
                json={},
                headers={"Authorization": "Bearer secret-token"},
            )

        [record] = [r for r in caplog.records if r.name == "task_master.security"]
        assert (record.__dict__["status"], "secret-token" in str(record.__dict__)) == (
            422,
            False,
        )

    async def test_ordinary_responses_are_not_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="task_master.security")
        async with client_for(make_settings()) as client:
            await client.get("/health")

        assert [r for r in caplog.records if r.name == "task_master.security"] == []
