"""Original JSONPlaceholder HTTPS -> G5 typed binding -> second HTTPS E1.

A public *fake* REST provider exercises real remote transport; content is
demo seed data, not independent actual business truth or agent-selected E2.
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
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

PROVIDER = "https://jsonplaceholder.typicode.com"
SOURCE_PATH = "/posts/1"  # Fixed source-issued demo record, not an agent URL.
USER_PATH_TEMPLATE = "/users/{id}"
MAX_JSON_BYTES = 65536
MAX_USER_ID = 10000
MAX_POST_ID = 100  # Original public JSONPlaceholder seeded post catalog.
ACTOR = PrincipalContext(subject="research-host", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("post author username", "게시글 작성자 계정", "投稿者ユーザー名"),
    required_fields=(CapabilityFieldContract(
        semantic_id="demo.username",
        json_schema={"type": "string"},
    ),),
    source_type="demo_rest",
    license="public_demo_not_business_data",
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for name, value in pairs:
        if name in obj:
            raise ValueError("duplicate source JSON key")
        obj[name] = value
    return obj


def _nonfinite(_: str) -> None:
    raise ValueError("source JSON contains nonfinite number")


def _original_json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    if response.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise ValueError("original provider did not return JSON content-type")
    if len(response.content) > MAX_JSON_BYTES:
        raise ValueError("original provider JSON body exceeds size bound")
    try:
        body = json.loads(
            response.content, object_pairs_hook=_unique_object,
            parse_constant=_nonfinite,
        )
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ValueError("invalid source JSON content") from exc
    if type(body) is not dict:
        raise ValueError("original provider root must be JSON object")
    return body


class JSONPlaceholderBoundInvoker:
    """Fixed-host read-only transport under explicitly registered invokers."""

    def __init__(self, client: httpx.AsyncClient, *, resource: str) -> None:
        if resource not in {"post", "user"}:
            raise ValueError("unapproved provider resource")
        self._client = client
        self._resource = resource
        self.attempts = 0
        self.validated = 0

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
        expected_post_id = 1  # Non-post invokers never inspect this value.
        if self._resource == "post":
            if endpoint == "one" and not arguments:
                expected_post_id = 1
                path = SOURCE_PATH
            elif endpoint == "by_post" and set(arguments) == {"post_id"}:
                expected_post_id = arguments["post_id"]
                if type(expected_post_id) is not int or not 1 <= expected_post_id <= MAX_POST_ID:
                    raise ValueError("untrusted host post identifier out of bounds")
                path = f"/posts/{expected_post_id}"
            else:
                raise ValueError("invalid pinned root operation")
        else:
            if endpoint != "by_user" or set(arguments) != {"user_id"}:
                raise ValueError("invalid fixed user lookup")
            user_id = arguments["user_id"]
            if type(user_id) is not int or not 1 <= user_id <= MAX_USER_ID:
                raise ValueError("untrusted second-hop identifier out of bounds")
            path = USER_PATH_TEMPLATE.format(id=user_id)
        # The caller only supplies a bounded *integer*, never the host or URL.
        self.attempts += 1
        response = await self._client.get(PROVIDER + path)
        payload = _original_json(response)
        if self._resource == "post":
            user_id = payload.get("userId")
            if (
                type(user_id) is not int
                or not 1 <= user_id <= MAX_USER_ID
                or type(payload.get("id")) is not int
                or payload["id"] != expected_post_id
            ):
                raise ValueError("source post owner field untrusted")
            result = {"userId": user_id}
        else:
            identifier = payload.get("id")
            username = payload.get("username")
            if (
                type(identifier) is not int
                or identifier != arguments["user_id"]
                or type(username) is not str
                or not 1 <= len(username) <= 200
            ):
                raise ValueError("second-hop user identity or username inconsistent")
            result = {"username": username}
        self.validated += 1
        return result


def build_graph_router(
    client: httpx.AsyncClient, *, parameterized: bool = False,
) -> tuple[
    SchemaRouter, NativeSchemaGraphIndex,
    JSONPlaceholderBoundInvoker, JSONPlaceholderBoundInvoker,
]:
    """Host-owned native registration, no public provider metadata authority."""
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    )
    router = SchemaRouter(authorization_policy=policy)
    source_input = ({
        "parameters": [ParameterSpec(
            name="post_id", required=True, json_schema={"type": "integer"},
        )],
        "input_schema": {
            "type": "object",
            "properties": {"post_id": {"type": "integer"}},
            "required": ["post_id"],
        },
    } if parameterized else {})
    source = ToolSpec(
        name="demo_posts",
        provider="jsonplaceholder",
        access_mode="host-pinned-public-https",
        source_type="demo_rest",
        license="public_demo_not_business_data",
        remote=True,
        endpoints=[EndpointSpec(
            name="by_post" if parameterized else "one", read_only=True,
            **source_input,
            output_fields=[FieldSpec(
                name="userId",
                semantic_id="demo.user_id",
                identifier=True,
                json_schema={"type": "integer"},
            )],
            output_schema={
                "type": "object",
                "properties": {"userId": {"type": "integer"}},
                "required": ["userId"],
            },
        )],
    )
    consumer = ToolSpec(
        name="demo_users",
        provider="jsonplaceholder",
        access_mode="host-pinned-public-https",
        source_type="demo_rest",
        license="public_demo_not_business_data",
        remote=True,
        endpoints=[EndpointSpec(
            name="by_user", read_only=True,
            parameters=[ParameterSpec(
                name="user_id", required=True,
                semantic_id="demo.user_id",
                json_schema={"type": "integer"},
            )],
            input_schema={
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
            },
            output_fields=[FieldSpec(
                name="username",
                semantic_id="demo.username",
                json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"username": {"type": "string"}},
                "required": ["username"],
            },
        )],
    )
    post = JSONPlaceholderBoundInvoker(client, resource="post")
    user = JSONPlaceholderBoundInvoker(client, resource="user")
    router.add_bound_tool(source, post)
    router.add_bound_tool(consumer, user)
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=(
            frozenset({"demo_posts.by_post"}) if parameterized else frozenset()
        ),
    )
    return router, graph, post, user


async def run(
    client: httpx.AsyncClient, *, host_post_id: int | None = None,
) -> dict[str, Any]:
    # The host selects and authorizes the original source ID. The graph never
    # infers one from query wording; untrusted values cannot become URL paths.
    if host_post_id is not None and (
        type(host_post_id) is not int or not 1 <= host_post_id <= MAX_POST_ID
    ):
        raise ValueError("invalid bounded host-selected post identifier")
    parameterized = host_post_id is not None
    router, graph, post, user = build_graph_router(
        client, parameterized=parameterized,
    )
    start = time.perf_counter()
    query = GROUP.aliases[0]  # Host-chosen alias; no unseen-language intent.
    found = graph.lookup(router, query, group=GROUP, principal=ACTOR)
    if found.status != "complete" or len(found.candidates) != 1:
        raise ValueError("pinned real-provider graph failed the original G5 gate")
    edge = found.candidates[0]
    if edge.parameter_bindings != (("user_id", "userId"),):
        raise ValueError("provider-to-consumer native typed graph mapping drift")
    if edge.source_root_parameters != (("post_id",) if parameterized else ()):
        raise ValueError("source root parameters do not match approved contract")
    pair = await execute_native_graph_one_hop(
        graph, router, query=query, group=GROUP,
        principal=ACTOR, candidate=edge,
        source_arguments=({"post_id": host_post_id} if parameterized else None),
    )
    source_data, target_data = pair.producer.data, pair.consumer.data
    if (
        type(source_data) is not dict
        or type(target_data) is not dict
        or set(source_data) != {"userId"}
        or set(target_data) != {"username"}
    ):
        raise ValueError("source field projection or consumer result changed")
    if post.attempts != post.validated or user.attempts != user.validated:
        raise ValueError("nonverified source attempts cannot be counted complete")
    if post.validated != 1 or user.validated != 1:
        raise ValueError("expected exactly two observed real provider responses")
    return {
        "study": (
            "G5_HOST_PARAMETERIZED_ORIGINAL_DEMO_HTTPS_E1_NOT_E2"
            if parameterized else "G5_ORIGINAL_DEMO_HTTPS_TWO_BOUND_CALLS_E1_NOT_E2"
        ),
        "source_provider": "jsonplaceholder.typicode.com",
        "provider_is_demo_fabricated_content": True,
        "source_paths": [
            (f"/posts/{host_post_id}" if parameterized else SOURCE_PATH),
            USER_PATH_TEMPLATE,
        ],
        "host_parameterized_source_root": parameterized,
        "host_source_arguments_explicitly_provided": parameterized,
        "actual_https_requested": True,
        "source_http_attempts": {"post": post.attempts, "user": user.attempts},
        "source_responses_verified": {"post": post.validated, "user": user.validated},
        "g5_original_conjunctive_candidate_count": found.qualified_path_count,
        "complete_field_bindings_observed": True,
        "host_selected_original_post_and_tool_sequence": True,
        "model_selected_tools": False,
        "independent_provider_identity": False,
        "independent_agent_e2": False,
        "product_default_changed": False,
        "release_qualified": False,
        "wall_seconds": round(time.perf_counter() - start, 3),
        # Never persist username, userId, provider response body or URL query.
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--post-id", type=int, default=None,
        help="Explicit host-approved public post ID 1..100; default pins /posts/1",
    )
    options = parser.parse_args()
    async def _live() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await run(client, host_post_id=options.post_id)

    report = asyncio.run(_live())
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(
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
