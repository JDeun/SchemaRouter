"""Synthetic no-network assertions for one DEMO original-HTTPS G5 fork (E0)."""
from __future__ import annotations

import json

import httpx
import pytest

from schemarouter.errors import SchemaValidationError
from scripts.research_g5_jsonplaceholder_fork_e1 import (
    ACTOR,
    FORK_ALIASES,
    FORK_GROUP,
    build_fork_router,
    run,
)


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


@pytest.mark.asyncio
async def test_original_source_id_changes_between_separate_reads_fail_closed():
    """Two individually valid HTTP paths must not simulate an atomic row join.

    The post root is observed twice through the host-registered executor.
    It may point to a different user on the second observation. Even though
    both consumers independently return valid projected scalar fields, the
    final E1 result MUST fail closed, never merge different source identities.
    """
    observed_paths: list[str] = []
    post_observations = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal post_observations
        assert request.method == "GET"
        assert request.url.scheme == "https"
        assert request.url.host == "jsonplaceholder.typicode.com"
        assert not request.url.query
        observed_paths.append(request.url.path)
        if request.url.path == "/posts/1":
            post_observations += 1
            assert post_observations <= 2
            return httpx.Response(
                200, headers={"content-type": "application/json"},
                json={
                    "id": 1,
                    "userId": 1 if post_observations == 1 else 2,
                },
            )
        if request.url.path in {"/users/1", "/users/2"}:
            user_id = int(request.url.path.rsplit("/", 1)[1])
            return httpx.Response(
                200, headers={"content-type": "application/json"},
                json={
                    "id": user_id,
                    "username": "simulated-username",
                    "email": "simulated@example.test",
                },
            )
        raise AssertionError("unregistered original provider URL")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
    ) as client:
        with pytest.raises(
            ValueError,
            match="original provider request/binding/identity mismatch",
        ):
            await run(client)
    assert observed_paths == [
        "/posts/1", "/users/1", "/posts/1", "/users/2",
    ]
    assert post_observations == 2


@pytest.mark.asyncio
async def test_revoked_original_email_consumer_never_reaches_provider():
    """Same pinned graph cannot disclose a fork after current health revoke."""
    recorded: list[httpx.Request] = []

    def deny_network(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        raise AssertionError("a non-authorized fork performed HTTPS")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(deny_network),
    ) as client:
        router, graph, post, user, email = build_fork_router(client)
        router.planner.availability_predicate = (
            lambda tool, _ep: tool.key != "demo_user_email"
        )
        for alias in FORK_ALIASES:
            forbidden = graph.lookup_shared_root_forks(
                router, alias, group=FORK_GROUP, principal=ACTOR,
            )
            assert forbidden.status == "no_proven_hit"
            assert forbidden.qualified_fork_count == 0
            assert forbidden.candidates == ()
            assert forbidden.executable_authority is False
        assert (post.attempts, user.attempts, email.attempts) == (0, 0, 0)
    assert recorded == []
