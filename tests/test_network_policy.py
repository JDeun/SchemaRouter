from __future__ import annotations

import pytest
import httpx

from schemarouter.ingestion import _fetch_with_safe_redirects
from schemarouter.network_policy import NetworkPolicy, NetworkPolicyError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/schema",
        "http://10.0.0.1/schema",
        "http://169.254.169.254/latest/meta-data",
        "http://192.168.1.10/schema",
        "http://224.0.0.1/schema",
        "http://[::1]/schema",
        "http://[fe80::1]/schema",
    ],
)
async def test_public_network_policy_rejects_non_global_literal_destinations(
    url: str,
) -> None:
    policy = NetworkPolicy.public_only()

    with pytest.raises(NetworkPolicyError):
        await policy.authorize(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/schema",
        "http://service.localhost/schema",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data.ec2.internal/latest/meta-data/",
    ],
)
async def test_public_network_policy_rejects_local_and_metadata_hostnames(
    url: str,
) -> None:
    policy = NetworkPolicy.public_only()

    with pytest.raises(NetworkPolicyError):
        await policy.authorize(url)


@pytest.mark.asyncio
async def test_public_network_policy_checks_resolved_addresses() -> None:
    async def private_resolver(host: str, port: int) -> tuple[str, ...]:
        assert host == "api.example.test"
        assert port == 443
        return ("10.10.0.8",)

    policy = NetworkPolicy.public_only(resolver=private_resolver)

    with pytest.raises(NetworkPolicyError):
        await policy.authorize("https://api.example.test/openapi.json")


@pytest.mark.asyncio
async def test_public_network_policy_accepts_global_resolution() -> None:
    async def public_resolver(host: str, port: int) -> tuple[str, ...]:
        assert host == "api.example.test"
        assert port == 443
        return ("93.184.216.34",)

    policy = NetworkPolicy.public_only(resolver=public_resolver)

    await policy.authorize("https://api.example.test/openapi.json")


@pytest.mark.asyncio
async def test_public_network_policy_allowlist_preserves_explicit_internal_access() -> None:
    calls = 0

    async def resolver(host: str, port: int) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        return ("127.0.0.1",)

    policy = NetworkPolicy.public_only(
        allowed_hosts={"internal.example.test"},
        resolver=resolver,
    )

    await policy.authorize("https://internal.example.test/schema")
    assert calls == 0


@pytest.mark.asyncio
async def test_trusted_internal_policy_preserves_existing_private_network_use() -> None:
    policy = NetworkPolicy.trusted_internal()

    await policy.authorize("http://127.0.0.1:8080/schema")
    await policy.authorize("http://[::1]:8080/schema")


@pytest.mark.asyncio
async def test_public_network_policy_rechecks_dns_on_each_authorization() -> None:
    answers = iter((("93.184.216.34",), ("127.0.0.1",)))

    async def changing_resolver(host: str, port: int) -> tuple[str, ...]:
        assert host == "api.example.test"
        assert port == 443
        return next(answers)

    policy = NetworkPolicy.public_only(resolver=changing_resolver)

    await policy.authorize("https://api.example.test/schema")
    with pytest.raises(NetworkPolicyError):
        await policy.authorize("https://api.example.test/schema")


@pytest.mark.asyncio
async def test_redirect_path_reauthorizes_before_second_request() -> None:
    resolver_answers = iter((("93.184.216.34",), ("127.0.0.1",)))
    request_count = 0

    async def changing_resolver(host: str, port: int) -> tuple[str, ...]:
        assert host == "api.example.test"
        assert port == 443
        return next(resolver_answers)

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            302,
            headers={"Location": "/schema-v2"},
            request=request,
        )

    policy = NetworkPolicy.public_only(resolver=changing_resolver)
    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(NetworkPolicyError):
            await _fetch_with_safe_redirects(
                client,
                "https://api.example.test/schema",
                headers=None,
                network_policy=policy,
            )

    assert request_count == 1


@pytest.mark.asyncio
async def test_public_network_policy_rejects_ambiguous_or_credentialed_hosts() -> None:
    policy = NetworkPolicy.public_only()

    with pytest.raises(NetworkPolicyError):
        await policy.authorize("http://user:pass@example.com/schema")
    with pytest.raises(NetworkPolicyError):
        await policy.authorize("http://[fe80::1%25eth0]/schema")


def test_network_policy_validates_port_allowlist() -> None:
    policy = NetworkPolicy.trusted_internal(allowed_ports={443})

    policy.validate_url("https://example.com/schema")
    with pytest.raises(NetworkPolicyError):
        policy.validate_url("http://example.com:8080/schema")
