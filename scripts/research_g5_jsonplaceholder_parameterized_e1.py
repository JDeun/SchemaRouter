"""Live public DEMO HTTPS E1 for #1596 host-approved parameterized G5 roots.

The host, not a model, supplies bounded original post IDs and a trusted
candidate/alias. Two real provider calls per case travel through the original
SchemaRouter executor. Source content is JSONPlaceholder FAKE test data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_g5_jsonplaceholder_live_e1 import (
    ACTOR,
    GROUP,
    MAX_USER_ID,
    PROVIDER,
    JSONPlaceholderBoundInvoker,
    _original_json,
)

POST_IDS = (1, 11)  # Host-chosen public DEMO source inputs; never inferred by G5.
MAX_POST_ID = 100
SOURCE_ROUTE = "demo_posts.by_id"


class JSONPlaceholderPostById:
    """Allow only a bounded original GET /posts/{post_id}, never arbitrary URLs."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.attempts = 0
        self.validated = 0

    async def __call__(
        self, endpoint: str, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if endpoint != "by_id" or type(arguments) is not dict or set(arguments) != {"post_id"}:
            raise ValueError("unapproved original source invocation")
        post_id = arguments["post_id"]
        if type(post_id) is not int or not 1 <= post_id <= MAX_POST_ID:
            raise ValueError("out-of-range original source identifier")
        self.attempts += 1
        payload = _original_json(await self._client.get(PROVIDER + f"/posts/{post_id}"))
        user_id = payload.get("userId")
        if (
            type(payload.get("id")) is not int
            or payload["id"] != post_id
            or type(user_id) is not int
            or not 1 <= user_id <= MAX_USER_ID
        ):
            raise ValueError("original post identity / source binding inconsistent")
        self.validated += 1
        # The registered tool exposes ONLY the field required by the next edge.
        return {"userId": user_id}


def build_parameterized_router(
    client: httpx.AsyncClient,
) -> tuple[
    SchemaRouter, NativeSchemaGraphIndex,
    JSONPlaceholderPostById, JSONPlaceholderBoundInvoker,
]:
    """Original two ToolSpecs, host-authorized root and shared canonical G5."""
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    )
    router = SchemaRouter(authorization_policy=policy)
    source = ToolSpec(
        name="demo_posts", provider="jsonplaceholder",
        access_mode="host-pinned-public-https", source_type="demo_rest",
        license="public_demo_not_business_data", remote=True,
        endpoints=[EndpointSpec(
            name="by_id", read_only=True,
            parameters=[ParameterSpec(
                name="post_id", required=True,
                json_schema={"type": "integer"},
            )],
            input_schema={
                "type": "object",
                "properties": {"post_id": {"type": "integer"}},
                "required": ["post_id"],
            },
            output_fields=[FieldSpec(
                name="userId", semantic_id="demo.user_id",
                identifier=True, json_schema={"type": "integer"},
            )],
            output_schema={
                "type": "object",
                "properties": {"userId": {"type": "integer"}},
                "required": ["userId"],
            },
        )],
    )
    consumer = ToolSpec(
        name="demo_users", provider="jsonplaceholder",
        access_mode="host-pinned-public-https", source_type="demo_rest",
        license="public_demo_not_business_data", remote=True,
        endpoints=[EndpointSpec(
            name="by_user", read_only=True,
            parameters=[ParameterSpec(
                name="user_id", required=True,
                semantic_id="demo.user_id", json_schema={"type": "integer"},
            )],
            input_schema={
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
            },
            output_fields=[FieldSpec(
                name="username", semantic_id="demo.username",
                json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"username": {"type": "string"}},
                "required": ["username"],
            },
        )],
    )
    post = JSONPlaceholderPostById(client)
    user = JSONPlaceholderBoundInvoker(client, resource="user")
    router.add_bound_tool(source, post)
    router.add_bound_tool(consumer, user)
    posting = NativeSchemaPostingIndex.build(router.registry)
    # Explicit proof that the previously published default remains no-fit.
    default = NativeSchemaGraphIndex.build(posting)
    if (
        default.lookup(router, GROUP.aliases[0], group=GROUP, principal=ACTOR).status
        != "no_proven_hit"
    ):
        raise ValueError("default G5 unexpectedly admitted a parameterized source")
    graph = NativeSchemaGraphIndex.build(
        posting, approved_host_roots=frozenset({SOURCE_ROUTE}),
    )
    return router, graph, post, user


async def run(
    client: httpx.AsyncClient, *, post_ids: tuple[int, ...] = POST_IDS,
) -> dict[str, Any]:
    if (
        type(post_ids) is not tuple or len(post_ids) != 2
        or len(set(post_ids)) != 2
        or any(type(x) is not int or not 1 <= x <= MAX_POST_ID for x in post_ids)
    ):
        raise ValueError("two distinct bounded host-chosen original post IDs required")
    router, graph, post, user = build_parameterized_router(client)
    start = time.perf_counter()
    query = GROUP.aliases[0]  # Existing host-defined English alias only.
    found = graph.lookup(router, query, group=GROUP, principal=ACTOR)
    if found.status != "complete" or len(found.candidates) != 1:
        raise ValueError("approved original parameterized G5 edge not uniquely qualified")
    candidate = found.candidates[0]
    if (
        candidate.producer_route_id != SOURCE_ROUTE
        or candidate.source_root_parameters != ("post_id",)
        or candidate.parameter_bindings != (("user_id", "userId"),)
    ):
        raise ValueError("original source-bound G5 contract drift")
    for post_id in post_ids:
        result = await execute_native_graph_one_hop(
            graph, router, query=query, group=GROUP, principal=ACTOR,
            candidate=candidate, source_arguments={"post_id": post_id},
        )
        if (
            type(result.producer.data) is not dict
            or set(result.producer.data) != {"userId"}
            or type(result.consumer.data) is not dict
            or set(result.consumer.data) != {"username"}
            or not result.producer_via_registered_executor
            or not result.consumer_via_registered_executor
            or result.independent_agent_e2
            or result.independent_provider_identity_verified
        ):
            raise ValueError("source projection or original execution contract drift")
    if post.attempts != len(post_ids) or user.attempts != len(post_ids):
        raise ValueError("missing original HTTP request")
    if post.validated != post.attempts or user.validated != user.attempts:
        raise ValueError("unvalidated provider HTTP response")
    return {
        "study": "G5_ORIGINAL_DEMO_PARAMETERIZED_HTTPS_E1_NOT_E2",
        "source_provider": "jsonplaceholder.typicode.com",
        "provider_is_demo_fabricated_content": True,
        "approved_source_root_count": len(graph.approved_host_roots),
        "source_input_cases": len(post_ids),
        "source_http_attempts": {"post": post.attempts, "user": user.attempts},
        "source_responses_verified": {"post": post.validated, "user": user.validated},
        "qualified_native_edges": len(found.candidates),
        "complete_observed_typed_bindings": True,
        "host_selected_original_routes_and_arguments": True,
        "model_selected_tools": False,
        "independent_provider_identity": False,
        "independent_agent_e2": False,
        "product_default_changed": False,
        "release_qualified": False,
        "wall_seconds": round(time.perf_counter() - start, 3),
        # Do not persist response values, actual IDs, usernames or raw URLs.
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    async def _live() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await run(client)

    report = asyncio.run(_live())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "source_responses_verified": report["source_responses_verified"],
        "wall_seconds": report["wall_seconds"],
    }, allow_nan=False))


if __name__ == "__main__":
    main()
