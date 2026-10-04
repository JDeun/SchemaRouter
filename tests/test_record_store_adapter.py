from __future__ import annotations

from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RecordFieldSpec,
    RecordSourceSpec,
    RunConfig,
    SchemaRouter,
    ToolCall,
)


class FakeRecordBackend:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        return (
            RecordSourceSpec(
                name="documents",
                model="document",
                supports_text_search=True,
                fields=(
                    RecordFieldSpec(name="id", json_schema={"type": "string"}, identifier=True),
                    RecordFieldSpec(name="title", json_schema={"type": "string"}),
                    RecordFieldSpec(
                        name="department",
                        json_schema={"type": "string"},
                        filterable=True,
                    ),
                    RecordFieldSpec(name="body", json_schema={"type": "string"}),
                ),
            ),
            RecordSourceSpec(
                name="search_logs",
                model="search",
                supports_text_search=True,
                fields=(
                    RecordFieldSpec(name="id", json_schema={"type": "string"}, identifier=True),
                    RecordFieldSpec(name="message", json_schema={"type": "string"}),
                    RecordFieldSpec(
                        name="service",
                        json_schema={"type": "string"},
                        filterable=True,
                    ),
                ),
            ),
            RecordSourceSpec(
                name="cache",
                model="key_value",
                fields=(
                    RecordFieldSpec(name="key", json_schema={"type": "string"}, identifier=True),
                    RecordFieldSpec(name="value", json_schema={}),
                    RecordFieldSpec(
                        name="tenant",
                        json_schema={"type": "string"},
                        filterable=True,
                    ),
                ),
            ),
            RecordSourceSpec(
                name="metrics",
                model="time_series",
                time_field="timestamp",
                fields=(
                    RecordFieldSpec(name="timestamp", json_schema={"type": "string"}),
                    RecordFieldSpec(
                        name="service",
                        json_schema={"type": "string"},
                        filterable=True,
                    ),
                    RecordFieldSpec(name="value", json_schema={"type": "number"}),
                ),
            ),
            RecordSourceSpec(
                name="executive_docs",
                model="document",
                supports_text_search=True,
                fields=(
                    RecordFieldSpec(name="id", json_schema={"type": "string"}, identifier=True),
                    RecordFieldSpec(name="title", json_schema={"type": "string"}),
                ),
            ),
        )

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "source": source,
                "text_query": text_query,
                "filters": dict(filters),
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
                "include_fields": include_fields,
            }
        )
        rows: dict[str, list[dict[str, Any]]] = {
            "documents": [
                {
                    "id": "doc-1",
                    "title": "Router design",
                    "department": "engineering",
                    "body": "typed capability retrieval",
                }
            ],
            "search_logs": [
                {"id": "log-1", "message": "healthy", "service": "router"}
            ],
            "cache": [
                {"key": "tenant:1", "value": {"ok": True}, "tenant": "tenant-1"}
            ],
            "metrics": [
                {
                    "timestamp": "2026-10-03T00:00:00Z",
                    "service": "router",
                    "value": 42.0,
                }
            ],
            "executive_docs": [
                {"id": "exec-1", "title": "Board forecast"}
            ],
        }
        return rows[source][:limit]


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    fields: list[str],
    arguments: dict[str, object],
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("query")
    return ExecutionPlan(
        query=f"query {tool_key}",
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


def test_record_store_introspection_covers_all_four_models() -> None:
    router = SchemaRouter()
    keys = router.add_record_store(
        FakeRecordBackend(),
        database_name="nosql",
        remote=False,
    )

    assert set(keys) == {
        "nosql.documents",
        "nosql.search_logs",
        "nosql.cache",
        "nosql.metrics",
        "nosql.executive_docs",
    }
    models = {
        key: router.registry.get(key).endpoint("query").metadata["record_model"]
        for key in (
            "nosql.documents",
            "nosql.search_logs",
            "nosql.cache",
            "nosql.metrics",
        )
    }
    assert models == {
        "nosql.documents": "document",
        "nosql.search_logs": "search",
        "nosql.cache": "key_value",
        "nosql.metrics": "time_series",
    }

    document_parameters = {
        value.name for value in router.registry.get("nosql.documents").endpoint("query").parameters
    }
    assert {"query", "filter__id", "filter__department", "limit"} <= document_parameters

    metric_parameters = {
        value.name for value in router.registry.get("nosql.metrics").endpoint("query").parameters
    }
    assert {"filter__service", "start_time", "end_time", "limit"} <= metric_parameters
    assert "query" not in metric_parameters


@pytest.mark.asyncio
async def test_document_query_is_bounded_filtered_and_projected() -> None:
    backend = FakeRecordBackend()
    router = SchemaRouter()
    await router.aadd_record_store(
        backend,
        database_name="nosql",
        sources={"documents"},
        default_limit=5,
        remote=False,
    )

    result = await router.execute(
        _plan(
            router,
            "nosql.documents",
            fields=["id", "title"],
            arguments={
                "query": "routing",
                "filter__department": "engineering",
            },
        )
    )

    assert result[0].data == [{"id": "doc-1", "title": "Router design"}]
    assert backend.calls == [
        {
            "source": "documents",
            "text_query": "routing",
            "filters": {"department": "engineering"},
            "start_time": None,
            "end_time": None,
            "limit": 5,
            "include_fields": ("id", "title"),
        }
    ]


@pytest.mark.asyncio
async def test_key_value_store_rejects_raw_query_dsl() -> None:
    router = SchemaRouter()
    await router.aadd_record_store(
        FakeRecordBackend(),
        database_name="nosql",
        sources={"cache"},
        remote=False,
    )

    with pytest.raises(PlanValidationError, match="undeclared arguments"):
        await router.execute(
            _plan(
                router,
                "nosql.cache",
                fields=["key", "value"],
                arguments={"raw_query": "{'$where': '...'}"},
            )
        )


@pytest.mark.asyncio
async def test_time_series_query_passes_only_declared_time_bounds() -> None:
    backend = FakeRecordBackend()
    router = SchemaRouter()
    await router.aadd_record_store(
        backend,
        database_name="nosql",
        sources={"metrics"},
        remote=False,
    )

    result = await router.execute(
        _plan(
            router,
            "nosql.metrics",
            fields=["timestamp", "value"],
            arguments={
                "filter__service": "router",
                "start_time": "2026-10-03T00:00:00Z",
                "end_time": "2026-10-04T00:00:00Z",
                "limit": 10,
            },
        )
    )

    assert result[0].data == [
        {"timestamp": "2026-10-03T00:00:00Z", "value": 42.0}
    ]
    assert backend.calls[0]["start_time"] == "2026-10-03T00:00:00Z"
    assert backend.calls[0]["end_time"] == "2026-10-04T00:00:00Z"


@pytest.mark.asyncio
async def test_record_sources_compose_with_principal_authorization() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="general-nosql",
                effect="allow",
                operation="nosql.documents.*",
                roles_any=("employee", "manager", "executive"),
            ),
            AuthorizationRule(
                name="executive-nosql",
                effect="allow",
                operation="nosql.executive_docs.*",
                roles_any=("executive",),
            ),
        )
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_record_store(
        FakeRecordBackend(),
        database_name="nosql",
        sources={"documents", "executive_docs"},
        remote=False,
    )
    employee = PrincipalContext(subject="alice", roles=("employee",))
    executive = PrincipalContext(subject="ceo", roles=("executive",))

    visible = router.retrieve_authorized(
        "board forecast",
        principal=employee,
        k=5,
    )
    assert all(
        candidate.tool != "nosql.executive_docs"
        for candidate in visible.candidates
    )

    plan = _plan(
        router,
        "nosql.executive_docs",
        fields=["id", "title"],
        arguments={"query": "forecast"},
    )
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(plan, config=RunConfig(principal=employee))

    result = await router.execute(plan, config=RunConfig(principal=executive))
    assert result[0].data == [{"id": "exec-1", "title": "Board forecast"}]


def test_record_store_can_limit_sources_before_registration() -> None:
    router = SchemaRouter()
    keys = router.add_record_store(
        FakeRecordBackend(),
        database_name="nosql",
        sources={"cache"},
        remote=False,
    )

    assert keys == ("nosql.cache",)
    assert router.registry.keys() == ("nosql.cache",)


@pytest.mark.asyncio
async def test_native_record_schema_refresh_applies_compatible_drift_and_rebinds() -> None:
    class MutableBackend(FakeRecordBackend):
        def __init__(self) -> None:
            super().__init__()
            self.add_summary = False

        def list_sources(self) -> tuple[RecordSourceSpec, ...]:
            sources = list(super().list_sources())
            if not self.add_summary:
                return tuple(sources)
            current = sources[0]
            sources[0] = current.model_copy(
                deep=True,
                update={
                    "fields": (
                        *current.fields,
                        current.fields[-1].model_copy(
                            deep=True,
                            update={"aliases": ("summary",)},
                        ),
                    )
                },
            )
            return tuple(sources)

    backend = MutableBackend()
    router = SchemaRouter()
    await router.aadd_record_store(
        backend,
        database_name="nosql",
        sources={"documents"},
    )
    before = router.registry.get("nosql.documents")
    backend.add_summary = True

    result = await router.arefresh_native_schema("nosql.documents")

    after = router.registry.get("nosql.documents")
    assert result.action == "applied"
    assert result.report.compatibility == "compatible"
    assert after.fingerprint != before.fingerprint
    assert "summary" in {
        field.name for field in after.endpoint("query").output_fields
    }
    assert router.executor.is_binding_ready_for_contract(
        "nosql.documents",
        after.fingerprint,
    )


@pytest.mark.asyncio
async def test_native_record_schema_refresh_quarantines_breaking_drift() -> None:
    class MutableBackend(FakeRecordBackend):
        def __init__(self) -> None:
            super().__init__()
            self.break_schema = False

        def list_sources(self) -> tuple[RecordSourceSpec, ...]:
            sources = list(super().list_sources())
            if not self.break_schema:
                return tuple(sources)
            current = sources[0]
            sources[0] = current.model_copy(
                deep=True,
                update={
                    "fields": tuple(
                        field for field in current.fields if field.name != "title"
                    )
                },
            )
            return tuple(sources)

    backend = MutableBackend()
    router = SchemaRouter()
    await router.aadd_record_store(
        backend,
        database_name="nosql",
        sources={"documents"},
    )
    before = router.registry.get("nosql.documents")
    backend.break_schema = True

    result = await router.arefresh_native_schema("nosql.documents")

    assert result.action == "pending_review"
    assert result.report.compatibility == "breaking"
    assert router.registry.get("nosql.documents").fingerprint == before.fingerprint
    assert "nosql.documents" in router._native_schema_pending
