"""Synthetic no-network assertions for one DEMO original-HTTPS G5 fork (E0)."""
from __future__ import annotations

import json

import httpx
import pytest

from schemarouter.errors import SchemaValidationError
from scripts.research_g5_jsonplaceholder_fork_e1 import run


def demo_transport(
    *, mismatched_email_id: bool = False,
) -> httpx.MockTransport:
    seen_user_requests = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal seen_user_requests
        if (request.method != "GET" or request.url.scheme != "https"
                or request.url.host != "jsonplaceholder.typicode.com"
                or request.url.query):
            raise AssertionError("unexpected method, host or query in provider request")
        if request.url.path == "/posts/1":
            return httpx.Response(
                200, headers={"content-type": "application/json"},
                content=json.dumps({"id": 1, "userId": 1}).encode(),
            )
        if request.url.path == "/users/1":
            seen_user_requests += 1
            return httpx.Response(
                200, headers={"content-type": "application/json"},
                content=json.dumps({
                    "id": 2 if mismatched_email_id and seen_user_requests == 2 else 1,
                    "username": "public-demo-user",
                    "email": "demo@example.test",
                }).encode(),
            )
        raise AssertionError("unregistered provider resource")

    return httpx.MockTransport(respond)


@pytest.mark.asyncio
async def test_actual_registered_source_paths_simulated_no_network():
    async with httpx.AsyncClient(transport=demo_transport()) as client:
        result = await run(client)
    assert result["study"].endswith("HTTPS_E1_NOT_E2")
    assert result["source_http_attempts"] == {"post": 2, "user": 1, "email": 1}
    assert result["source_responses_verified"] == result["source_http_attempts"]
    assert result["qualified_native_forks"] == 1
    assert result["host_attested_en_ko_ja_aliases"] == 3
    assert result["fork_is_nonexecuting"] is True
    assert result["atomic_row_snapshot_proven"] is False
    assert result["independent_task_gold"] is False
    assert result["independent_agent_e2"] is False
    assert result["release_qualified"] is False
    serialized = json.dumps(result)
    assert "demo@example.test" not in serialized
    assert "public-demo-user" not in serialized


@pytest.mark.asyncio
async def test_provider_identity_drift_fails_without_source_content_leak():
    async with httpx.AsyncClient(
        transport=demo_transport(mismatched_email_id=True),
    ) as client:
        with pytest.raises((ValueError, SchemaValidationError)):
            await run(client)
