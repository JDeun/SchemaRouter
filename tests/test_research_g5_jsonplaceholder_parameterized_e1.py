"""Offline original-protocol controls for the parameterized live DEMO HTTPS E1."""
from __future__ import annotations

import json

import httpx
import pytest

from schemarouter.errors import PolicyViolationError, SchemaValidationError
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from scripts.research_g5_jsonplaceholder_live_e1 import ACTOR, GROUP
from scripts.research_g5_jsonplaceholder_parameterized_e1 import (
    JSONPlaceholderPostById,
    build_parameterized_router,
    run,
)


def _reply(
    req: httpx.Request, *, bad_post_id: bool = False,
    bad_user_id: bool = False,
) -> httpx.Response:
    assert req.method == "GET"
    assert req.url.scheme == "https"
    assert req.url.host == "jsonplaceholder.typicode.com"
    assert not req.url.query
    if req.url.path in {"/posts/1", "/posts/11"}:
        post = int(req.url.path.split("/")[-1])
        return httpx.Response(200, json={
            "id": post + int(bad_post_id),
            "userId": 1 if post == 1 else 2,
            "body": "FAKE demo field not returned",
        })
    if req.url.path in {"/users/1", "/users/2"}:
        user = int(req.url.path.split("/")[-1])
        return httpx.Response(200, json={
            "id": user + int(bad_user_id),
            "username": "sensitive-demo-value",
            "email": "unused@example.invalid",
        })
    raise AssertionError("unexpected, potentially untrusted external path")


@pytest.mark.asyncio
async def test_two_distinct_parameterized_roots_execute_four_original_calls() -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _reply(req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await run(client)

    assert paths == ["/posts/1", "/users/1", "/posts/11", "/users/2"]
    assert report["source_http_attempts"] == {"post": 2, "user": 2}
    assert report["source_responses_verified"] == {"post": 2, "user": 2}
    assert report["source_input_cases"] == 2
    assert report["approved_source_root_count"] == 1
    assert report["qualified_native_edges"] == 1
    assert report["complete_observed_typed_bindings"] is True
    assert report["provider_is_demo_fabricated_content"] is True
    assert report["model_selected_tools"] is False
    assert report["independent_agent_e2"] is False
    assert report["release_qualified"] is False
    rendered = json.dumps(report)
    assert "sensitive-demo-value" not in rendered
    assert "example.invalid" not in rendered
    assert "FAKE demo field not returned" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_args", (
    None, {}, {"post_id": True}, {"post_id": 1.0},
    {"post_id": "1"}, {"post_id": 1, "admin": 1},
    {"post_id": 0}, {"post_id": 101},
))
async def test_bad_host_source_parameters_fail_before_any_request(
    bad_args: dict | None,
) -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _reply(req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router, graph, _, _ = build_parameterized_router(client)
        candidate = graph.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
        ).candidates[0]
        with pytest.raises((SchemaValidationError, ValueError)):
            await execute_native_graph_one_hop(
                graph, router, query=GROUP.aliases[0], group=GROUP,
                principal=ACTOR, candidate=candidate,
                source_arguments=bad_args,
            )
    assert paths == []


@pytest.mark.asyncio
async def test_unapproved_principal_refuses_source_before_http() -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _reply(req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router, graph, _, _ = build_parameterized_router(client)
        candidate = graph.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
        ).candidates[0]
        with pytest.raises(PolicyViolationError):
            await execute_native_graph_one_hop(
                graph, router, query=GROUP.aliases[0], group=GROUP,
                principal=None, candidate=candidate,
                source_arguments={"post_id": 1},
            )
    assert paths == []


@pytest.mark.asyncio
async def test_mismatched_original_post_identity_blocks_second_call() -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _reply(req, bad_post_id=True)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, SchemaValidationError)):
            await run(client)
    assert paths == ["/posts/1"]


@pytest.mark.asyncio
async def test_mismatched_original_user_identity_cannot_count_success() -> None:
    paths: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        paths.append(req.url.path)
        return _reply(req, bad_user_id=True)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, SchemaValidationError)):
            await run(client)
    assert paths == ["/posts/1", "/users/1"]


@pytest.mark.asyncio
async def test_direct_source_invoker_rejects_unknown_path_and_id_without_network() -> None:
    def forbidden(_req: httpx.Request) -> httpx.Response:
        raise AssertionError("must fail before original HTTP")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        post = JSONPlaceholderPostById(client)
        with pytest.raises(ValueError):
            await post("all", {"post_id": 1})
        with pytest.raises(ValueError):
            await post("by_id", {"post_id": -1})
        with pytest.raises(ValueError):
            await post("by_id", {"post_id": "1"})
        with pytest.raises(ValueError):
            await post("by_id", {"post_id": 1, "url": "evil"})
        assert post.attempts == 0


@pytest.mark.asyncio
async def test_runner_refuses_duplicate_or_out_of_range_study_inputs() -> None:
    def forbidden(_req: httpx.Request) -> httpx.Response:
        raise AssertionError("must fail before original HTTP")

    async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
        with pytest.raises(ValueError):
            await run(client, post_ids=(1, 1))
        with pytest.raises(ValueError):
            await run(client, post_ids=(1, 101))
        with pytest.raises(ValueError):
            await run(client, post_ids=(True, 11))
