"""No-network original-contract controls; the real HTTPS job is separate."""

from __future__ import annotations

import json

import httpx
import pytest

from schemarouter.errors import PolicyViolationError, SchemaValidationError
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from scripts.research_g5_jsonplaceholder_live_e1 import (
    ACTOR,
    GROUP,
    MAX_JSON_BYTES,
    JSONPlaceholderBoundInvoker,
    _original_json,
    build_graph_router,
    run,
)


def _handler(
    request: httpx.Request,
    *,
    source_override: dict | None = None,
    target_override: dict | None = None,
    status: int = 200,
) -> httpx.Response:
    assert request.method == "GET"
    assert request.url.scheme == "https"
    assert request.url.host == "jsonplaceholder.typicode.com"
    assert not request.url.query
    if request.url.path == "/posts/1":
        source = {
            "userId": 1, "id": 1, "title": "dummy title", "body": "demo",
        }
        return httpx.Response(status, json=source_override or source)
    if request.url.path == "/users/1":
        user = {
            "id": 1, "username": "source-demo", "email": "unused@example.invalid",
        }
        return httpx.Response(status, json=target_override or user)
    raise AssertionError("a dynamic/untrusted request path escaped the fixed host")


@pytest.mark.asyncio
async def test_two_real_bound_http_transport_calls_with_schema_routed_dataflow() -> None:
    requested: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requested.append(req.url.path)
        return _handler(req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run(client)
    assert requested == ["/posts/1", "/users/1"]
    assert report["source_responses_verified"] == {"post": 1, "user": 1}
    assert report["g5_original_conjunctive_candidate_count"] == 1
    assert report["complete_field_bindings_observed"]
    assert report["provider_is_demo_fabricated_content"]
    assert report["model_selected_tools"] is False
    assert report["independent_provider_identity"] is False
    assert report["independent_agent_e2"] is False
    assert report["release_qualified"] is False
    assert "source-demo" not in json.dumps(report)
    assert "example.invalid" not in json.dumps(report)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_source", [
    {"id": 1, "userId": 0},
    {"id": 1, "userId": None},
    {"id": 1, "userId": "1"},
    {"id": 1, "userId": [1]},
    {"id": 2, "userId": 1},
])
async def test_bad_first_source_observation_never_invokes_second(
    bad_source: dict,
) -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _handler(req, source_override=bad_source)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, SchemaValidationError)):
            await run(client)
    assert paths == ["/posts/1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_user", [
    {"id": 2, "username": "not-our-author"},
    {"id": 1, "username": ""},
    {"id": 1, "username": 42},
])
async def test_wrong_second_provider_identity_is_rejected(bad_user: dict) -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _handler(req, target_override=bad_user)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, SchemaValidationError)):
            await run(client)
    assert paths == ["/posts/1", "/users/1"]


def test_duplicate_key_nonfinite_and_oversize_source_payload_rejected() -> None:
    url = "https://jsonplaceholder.typicode.com/posts/1"
    duplicate = httpx.Response(
        200, request=httpx.Request("GET", url),
        content=b'{"id":1,"userId":1,"userId":2}',
        headers={"content-type": "application/json"},
    )
    with pytest.raises(ValueError, match="invalid source JSON content"):
        _original_json(duplicate)
    nonfinite = httpx.Response(
        200, request=httpx.Request("GET", url),
        content=b'{"id":1,"userId":NaN}',
        headers={"content-type": "application/json"},
    )
    with pytest.raises(ValueError, match="invalid"):
        _original_json(nonfinite)
    large = httpx.Response(
        200, request=httpx.Request("GET", url),
        content=b"x" * (MAX_JSON_BYTES + 1),
        headers={"content-type": "application/json"},
    )
    with pytest.raises(ValueError, match="size bound"):
        _original_json(large)


@pytest.mark.asyncio
async def test_untrusted_graph_alias_and_hidden_principal_deny_before_transport() -> None:
    attempted: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        attempted.append(req)
        return _handler(req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router, graph, post, user = build_graph_router(client)
        with pytest.raises(ValueError, match="approved"):
            graph.lookup(router, "invented route", group=GROUP, principal=ACTOR)
        edge = graph.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
        ).candidates[0]
        with pytest.raises(PolicyViolationError):
            await execute_native_graph_one_hop(
                graph, router, query=GROUP.aliases[0],
                group=GROUP, principal=None, candidate=edge,
            )
        assert post.attempts == user.attempts == 0
    assert attempted == []


@pytest.mark.asyncio
async def test_invalid_or_unapproved_direct_invoker_path_never_requests_http() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be reached")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = JSONPlaceholderBoundInvoker(client, resource="user")
        with pytest.raises(ValueError, match="out of bounds"):
            await invoker("by_user", {"user_id": -1})
        with pytest.raises(ValueError, match="invalid fixed"):
            await invoker("unknown", {"user_id": 1})
        with pytest.raises(ValueError, match="out of bounds"):
            await invoker("by_user", {"user_id": "1"})
        assert invoker.attempts == 0


@pytest.mark.asyncio
async def test_host_approved_original_post_id_crosses_two_real_bound_https_calls() -> None:
    """Original GET /posts/11 -> observed userId=2 -> GET /users/2."""
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        assert req.url.scheme == "https"
        assert req.url.host == "jsonplaceholder.typicode.com"
        assert not req.url.query
        if req.url.path == "/posts/11":
            return httpx.Response(200, json={
                "id": 11, "userId": 2, "body": "untrusted extra metadata",
            })
        if req.url.path == "/users/2":
            return httpx.Response(200, json={
                "id": 2, "username": "private-demo-observation",
                "email": "never-persist@example.invalid",
            })
        raise AssertionError("unapproved/guessed provider path")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run(client, host_post_id=11)
    assert paths == ["/posts/11", "/users/2"]
    assert report["study"] == "G5_HOST_PARAMETERIZED_ORIGINAL_DEMO_HTTPS_E1_NOT_E2"
    assert report["host_parameterized_source_root"] is True
    assert report["host_source_arguments_explicitly_provided"] is True
    assert report["g5_original_conjunctive_candidate_count"] == 1
    assert report["source_responses_verified"] == {"post": 1, "user": 1}
    assert report["independent_agent_e2"] is False
    assert report["release_qualified"] is False
    assert "private-demo-observation" not in json.dumps(report)
    assert "never-persist@example.invalid" not in json.dumps(report)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_id", [0, -1, 101, True, 11.0, "11"])
async def test_bad_host_post_id_refuses_before_any_source_request(invalid_id) -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        raise AssertionError("invalid host input reached network")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="host-selected post identifier"):
            await run(client, host_post_id=invalid_id)
    assert seen == []


@pytest.mark.asyncio
async def test_host_requested_post_id_mismatch_refuses_second_call() -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        assert req.url.path == "/posts/11"
        return httpx.Response(200, json={"id": 1, "userId": 2})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, SchemaValidationError)):
            await run(client, host_post_id=11)
    assert paths == ["/posts/11"]


@pytest.mark.asyncio
async def test_host_root_is_not_eligible_without_build_time_approval() -> None:
    from schemarouter.native_graph_index import NativeSchemaGraphIndex
    from schemarouter.native_semantic_index import NativeSchemaPostingIndex

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: (_ for _ in ()).throw(AssertionError("network called"))
        ),
    ) as client:
        router, approved, post, user = build_graph_router(
            client, parameterized=True,
        )
        found = approved.lookup(router, GROUP.aliases[0], group=GROUP, principal=ACTOR)
        assert found.status == "complete"
        assert found.candidates[0].source_root_parameters == ("post_id",)
        unapproved = NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry)
        )
        assert unapproved.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
        ).status == "no_proven_hit"
        assert post.attempts == user.attempts == 0
