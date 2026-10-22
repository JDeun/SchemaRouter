"""Host-controlled live public DEMO E1 for one source-root, two typed leaves.

G5 shared-root fork evidence is NONEXECUTING. A host separately runs both
original, already registered one-hop operations. Do not call this an atomic
row join, independent E2, multilingual model interpretation, or agent plan.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from schemarouter import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_execution import execute_native_graph_one_hop
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_g5_jsonplaceholder_live_e1 import (
    ACTOR,
    MAX_USER_ID,
    PROVIDER,
    USER_PATH_TEMPLATE,
    _original_json,
    build_graph_router,
)

FORK_ALIASES = (
    "post author username and email",
    "게시글 작성자의 계정과 이메일",
    "投稿者のユーザー名とメール",
)
SOURCE_TYPE = "demo_rest"
LICENSE = "public_demo_not_business_data"
FORK_GROUP = NativeDeclaredFieldGroup(
    aliases=FORK_ALIASES,
    required_fields=(
        CapabilityFieldContract(
            semantic_id="demo.username", json_schema={"type": "string"},
        ),
        CapabilityFieldContract(
            semantic_id="demo.email", json_schema={"type": "string"},
        ),
    ),
    source_type=SOURCE_TYPE,
    license=LICENSE,
)
ROOT_ROUTE = "demo_posts.one"
USER_ROUTE = "demo_users.by_user"
EMAIL_ROUTE = "demo_user_email.by_user"


class OriginalDemoEmailInvoker:
    """Bound original user resource; returns only licensed, validated email."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.attempts = 0
        self.validated = 0

    async def __call__(
        self, endpoint: str, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if endpoint != "by_user" or type(arguments) is not dict or set(arguments) != {"user_id"}:
            raise ValueError("unregistered email source invocation")
        user_id = arguments["user_id"]
        if type(user_id) is not int or not 1 <= user_id <= MAX_USER_ID:
            raise ValueError("invalid provider user identifier")
        self.attempts += 1
        payload = _original_json(await self._client.get(
            PROVIDER + USER_PATH_TEMPLATE.format(id=user_id)
        ))
        email = payload.get("email")
        if (
            type(payload.get("id")) is not int
            or payload["id"] != user_id
            or type(email) is not str
            or not 1 <= len(email) <= 200
        ):
            raise ValueError("source email identity/field validation failed")
        self.validated += 1
        return {"email": email}


def build_fork_router(
    client: httpx.AsyncClient,
) -> tuple[Any, NativeSchemaGraphIndex, Any, Any, OriginalDemoEmailInvoker]:
    """Reuse the existing original pinned post/user pair; add one read-only leaf."""
    router, _old_graph, post, user = build_graph_router(client)
    extra = ToolSpec(
        name="demo_user_email", provider="jsonplaceholder",
        access_mode="host-pinned-public-https", source_type=SOURCE_TYPE,
        license=LICENSE, remote=True,
        endpoints=[EndpointSpec(
            name="by_user", read_only=True,
            parameters=[ParameterSpec(
                name="user_id", required=True, semantic_id="demo.user_id",
                json_schema={"type": "integer"},
            )],
            input_schema={
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
            },
            output_fields=[FieldSpec(
                name="email", semantic_id="demo.email",
                json_schema={"type": "string"},
            )],
            output_schema={
                "type": "object",
                "properties": {"email": {"type": "string"}},
                "required": ["email"],
            },
        )],
    )
    email = OriginalDemoEmailInvoker(client)
    router.add_bound_tool(extra, email)
    graph = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    return router, graph, post, user, email


async def run(client: httpx.AsyncClient) -> dict[str, Any]:
    router, graph, post, user, email = build_fork_router(client)
    # The aliases are explicit host-owned declarations, not inferred language understanding.
    for alias in FORK_ALIASES:
        result = graph.lookup_shared_root_forks(
            router, alias, group=FORK_GROUP, principal=ACTOR,
        )
        identities = tuple(
            (item.root_route_id, *item.branch_route_ids)
            for item in result.candidates
        )
        if (
            result.status != "complete"
            or result.qualified_fork_count != 1
            or identities != ((ROOT_ROUTE, USER_ROUTE, EMAIL_ROUTE),)
            or result.executable_authority
            or result.independent_quality_evidence
        ):
            raise ValueError("original fork source contract/authority drift")

    # The fork evidence cannot itself invoke tools. Only the separately
    # authorized, registered host-controlled original one-hop executor can.
    results: list[Any] = []
    for required in FORK_GROUP.required_fields:
        single = NativeDeclaredFieldGroup(
            aliases=FORK_ALIASES, required_fields=(required,),
            source_type=SOURCE_TYPE, license=LICENSE,
        )
        one = graph.lookup(
            router, FORK_ALIASES[0], group=single, principal=ACTOR,
        )
        if one.status != "complete" or len(one.candidates) != 1:
            raise ValueError("source-verified single-leaf path unavailable")
        observed = await execute_native_graph_one_hop(
            graph, router, query=FORK_ALIASES[0],
            group=single, principal=ACTOR, candidate=one.candidates[0],
        )
        if (
            not observed.producer_via_registered_executor
            or not observed.consumer_via_registered_executor
            or observed.independent_agent_e2
        ):
            raise ValueError("original bound host execution receipt not proven")
        results.append(observed)

    first, second = results
    if (
        type(first.producer.data) is not dict
        or set(first.producer.data) != {"userId"}
        or first.producer.data != second.producer.data
        or type(first.consumer.data) is not dict
        or set(first.consumer.data) != {"username"}
        or type(second.consumer.data) is not dict
        or set(second.consumer.data) != {"email"}
        or (post.attempts, user.attempts, email.attempts) != (2, 1, 1)
        or post.attempts != post.validated
        or user.attempts != user.validated
        or email.attempts != email.validated
    ):
        raise ValueError("original provider request/binding/identity mismatch")

    return {
        "study": "G5_ORIGINAL_DEMO_SHARED_ROOT_TWO_LEAVES_HTTPS_E1_NOT_E2",
        "source_provider": "jsonplaceholder.typicode.com",
        "provider_is_demo_fabricated_content": True,
        "source_http_attempts": {
            "post": post.attempts, "user": user.attempts, "email": email.attempts,
        },
        "source_responses_verified": {
            "post": post.validated, "user": user.validated, "email": email.validated,
        },
        "host_attested_en_ko_ja_aliases": len(FORK_ALIASES),
        "qualified_native_forks": 1,
        "host_selected_operations_and_arguments": True,
        "fork_is_nonexecuting": True,
        "separate_original_one_hop_invocations_observed": True,
        "atomic_row_snapshot_proven": False,
        "model_selected_tools": False,
        "independent_task_gold": False,
        "independent_agent_e2": False,
        "product_default_changed": False,
        "release_qualified": False,
        # Never persist raw user IDs, response bodies, account names, emails or URLs.
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    output = parser.parse_args().out

    async def _live() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await run(client)

    report = asyncio.run(_live())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "source_responses_verified": report["source_responses_verified"],
        "independent_agent_e2": False,
    }))


if __name__ == "__main__":
    main()
