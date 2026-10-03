from __future__ import annotations

from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
    ToolCall,
    VectorCollectionSpec,
    VectorMetadataField,
)


class FakeVectorBackend:
    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        return (
            VectorCollectionSpec(
                name="public_docs",
                dimension=3,
                metric="cosine",
                description="public document embeddings",
                metadata_fields=(
                    VectorMetadataField(
                        name="title",
                        json_schema={"type": "string"},
                    ),
                    VectorMetadataField(
                        name="department",
                        json_schema={"type": "string"},
                        filterable=True,
                    ),
                ),
            ),
            VectorCollectionSpec(
                name="executive_memos",
                dimension=3,
                metric="cosine",
                description="executive memo embeddings",
                metadata_fields=(
                    VectorMetadataField(
                        name="title",
                        json_schema={"type": "string"},
                    ),
                ),
            ),
        )

    def search(
        self,
        *,
        collection: str,
        vector: list[float],
        top_k: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        self.search_calls.append(
            {
                "collection": collection,
                "vector": list(vector),
                "top_k": top_k,
                "include_fields": include_fields,
            }
        )
        if collection == "public_docs":
            return [
                {
                    "id": "doc-1",
                    "score": 0.98,
                    "title": "SchemaRouter",
                    "department": "engineering",
                },
                {
                    "id": "doc-2",
                    "score": 0.91,
                    "title": "Routing notes",
                    "department": "research",
                },
            ][:top_k]
        return [
            {
                "id": "memo-1",
                "score": 0.99,
                "title": "Board forecast",
            }
        ][:top_k]


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    query: str,
    fields: list[str],
    top_k: int | None = None,
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("search")
    arguments: dict[str, object] = {"query": query}
    if top_k is not None:
        arguments["top_k"] = top_k
    return ExecutionPlan(
        query=query,
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=arguments,
                fields=fields,
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


def test_vector_store_introspection_compiles_collection_contracts() -> None:
    backend = FakeVectorBackend()
    router = SchemaRouter()

    keys = router.add_vector_store(
        backend,
        lambda query: [0.1, 0.2, 0.3],
        database_name="vectors",
        remote=False,
    )

    assert keys == (
        "vectors.public_docs",
        "vectors.executive_memos",
    )
    tool = router.registry.get("vectors.public_docs")
    endpoint = tool.endpoint("search")
    assert tool.source_type == "database"
    assert tool.access_mode == "vector"
    assert endpoint.read_only is True
    assert endpoint.destructive is False
    assert endpoint.execution_metadata["dimension"] == 3
    assert endpoint.execution_metadata["metric"] == "cosine"
    assert [field.name for field in endpoint.output_fields] == [
        "id",
        "score",
        "title",
        "department",
    ]
    assert {parameter.name for parameter in endpoint.parameters} == {
        "query",
        "top_k",
    }


@pytest.mark.asyncio
async def test_vector_store_search_embeds_projects_and_bounds_results() -> None:
    backend = FakeVectorBackend()
    router = SchemaRouter()
    router.add_vector_store(
        backend,
        lambda query: [0.1, 0.2, 0.3],
        database_name="vectors",
        default_top_k=1,
        remote=False,
    )

    result = await router.execute(
        _plan(
            router,
            "vectors.public_docs",
            query="schema routing",
            fields=["id", "score", "title"],
        )
    )

    assert result[0].data == [
        {
            "id": "doc-1",
            "score": 0.98,
            "title": "SchemaRouter",
        }
    ]
    assert backend.search_calls == [
        {
            "collection": "public_docs",
            "vector": [0.1, 0.2, 0.3],
            "top_k": 1,
            "include_fields": ("title",),
        }
    ]


@pytest.mark.asyncio
async def test_vector_dimension_mismatch_fails_closed() -> None:
    router = SchemaRouter()
    router.add_vector_store(
        FakeVectorBackend(),
        lambda query: [0.1, 0.2],
        database_name="vectors",
        collections={"public_docs"},
        remote=False,
    )

    with pytest.raises(
        SchemaValidationError,
        match="dimension does not match collection contract",
    ):
        await router.execute(
            _plan(
                router,
                "vectors.public_docs",
                query="schema routing",
                fields=["id", "score"],
            )
        )


@pytest.mark.asyncio
async def test_vector_collections_compose_with_principal_authorization() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="public-vectors",
                effect="allow",
                operation="vectors.public_docs.*",
                roles_any=("employee", "manager", "executive"),
            ),
            AuthorizationRule(
                name="executive-vectors",
                effect="allow",
                operation="vectors.executive_memos.*",
                roles_any=("executive",),
            ),
        )
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_vector_store(
        FakeVectorBackend(),
        lambda query: [0.1, 0.2, 0.3],
        database_name="vectors",
        remote=False,
    )
    employee = PrincipalContext(subject="alice", roles=("employee",))
    executive = PrincipalContext(subject="ceo", roles=("executive",))

    employee_view = router.retrieve_authorized(
        "executive board forecast",
        principal=employee,
        k=5,
    )
    assert all(
        candidate.tool != "vectors.executive_memos"
        for candidate in employee_view.candidates
    )

    plan = _plan(
        router,
        "vectors.executive_memos",
        query="board forecast",
        fields=["id", "title"],
    )
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(plan, config=RunConfig(principal=employee))

    result = await router.execute(
        plan,
        config=RunConfig(principal=executive),
    )
    assert result[0].data == [{"id": "memo-1", "title": "Board forecast"}]


def test_vector_store_can_limit_collections_before_registration() -> None:
    router = SchemaRouter()
    keys = router.add_vector_store(
        FakeVectorBackend(),
        lambda query: [0.1, 0.2, 0.3],
        database_name="vectors",
        collections={"public_docs"},
        remote=False,
    )

    assert keys == ("vectors.public_docs",)
    assert router.registry.keys() == ("vectors.public_docs",)
