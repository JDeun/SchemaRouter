from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    GraphRelationshipTypeSpec,
    GraphSourceSpec,
    PolicyViolationError,
    PrincipalContext,
    RecordFieldSpec,
    RecordSourceSpec,
    RunConfig,
    SchemaRouter,
    ToolCall,
    ToolSpec,
    TrustedFilterBinding,
    VectorCollectionSpec,
    VectorMetadataField,
)
from schemarouter.adapters.graph_store import GraphSourceInvoker
from schemarouter.adapters.graphql import GraphQLRemoteInvoker
from schemarouter.adapters.http_json import HTTPJSONRemoteInvoker
from schemarouter.adapters.mcp import MCPBoundInvoker, MCPRemoteInvoker
from schemarouter.adapters.odata import ODataRemoteInvoker
from schemarouter.adapters.openapi import OpenAPIRemoteInvoker
from schemarouter.adapters.openrpc import OpenRPCRemoteInvoker
from schemarouter.adapters.optimade import OPTIMADERemoteInvoker
from schemarouter.adapters.record_store import RecordSourceInvoker
from schemarouter.adapters.sqlalchemy_database import SQLAlchemyTableInvoker
from schemarouter.adapters.sqlite_database import SQLiteTableInvoker
from schemarouter.adapters.vector_store import VectorCollectionInvoker
from schemarouter.authorization import _current_data_scope


def _call(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    *,
    fields: list[str],
    arguments: dict[str, object],
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(endpoint_name)
    return ExecutionPlan(
        query=f"call {tool_key}.{endpoint_name}",
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


def _employee_policy(operation: str) -> AuthorizationPolicy:
    return AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="employee-capability",
                effect="allow",
                operation=operation,
                roles_any=("employee", "manager", "executive"),
            ),
        ),
        data_rules=(
            DataScopeRule(
                name="employee-scope",
                operation=operation,
                roles_any=("employee",),
                visible_fields=("id", "name"),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="department",
                        principal_value="attribute:department",
                    ),
                ),
            ),
            DataScopeRule(
                name="manager-scope",
                operation=operation,
                roles_any=("manager",),
                visible_fields=("id", "name", "department", "salary"),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="department",
                        principal_value="attribute:department",
                    ),
                ),
            ),
            DataScopeRule(
                name="executive-scope",
                operation=operation,
                roles_any=("executive",),
                visible_fields=("id", "name", "department", "salary"),
            ),
        ),
    )


def test_data_scope_rule_rejects_overlapping_visible_and_hidden_fields() -> None:
    with pytest.raises(ValueError, match="visible_fields and hidden_fields must not overlap"):
        DataScopeRule(
            operation="company.employees.select",
            visible_fields=("id", "name"),
            hidden_fields=("name",),
        )


def test_data_scope_rejects_unknown_hidden_field_after_schema_drift() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    connection.commit()

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="company.employees.select",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="company.employees.select",
                roles_any=("employee",),
                hidden_fields=("legacy_salary",),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_sqlite_database(connection, database_name="company")
    principal = PrincipalContext(subject="alice", roles=("employee",))

    try:
        with pytest.raises(PolicyViolationError, match="authorization denied"):
            router.retrieve_authorized(
                "employees",
                principal=principal,
                k=5,
            )
    finally:
        connection.close()


@pytest.mark.asyncio
async def test_sql_scope_hides_fields_before_retrieval_and_enforces_row_predicate() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL NOT NULL
        )
        """
    )
    connection.executemany(
        "INSERT INTO employees(id, name, department, salary) VALUES (?, ?, ?, ?)",
        [
            (1, "Alice", "sales", 100.0),
            (2, "Bob", "engineering", 120.0),
        ],
    )
    connection.commit()

    policy = _employee_policy("company.employees.select")
    router = SchemaRouter(authorization_policy=policy)
    router.add_sqlite_database(connection, database_name="company")

    employee = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"department": "sales"},
    )
    manager = PrincipalContext(
        subject="manager",
        roles=("manager",),
        attributes={"department": "engineering"},
    )

    employee_view = router.retrieve_authorized(
        "employee salary payroll",
        principal=employee,
        k=5,
    )
    assert employee_view.candidates
    employee_candidate = employee_view.candidates[0]
    assert [field.name for field in employee_candidate.output_fields] == ["id", "name"]
    assert "salary" not in employee_candidate.matched_fields
    assert "salary" not in repr(employee_candidate.output_schema)

    manager_view = router.retrieve_authorized(
        "employee salary payroll",
        principal=manager,
        k=5,
    )
    assert any(
        field.name == "salary"
        for field in manager_view.candidates[0].output_fields
    )

    safe_plan = _call(
        router,
        "company.employees",
        "select",
        fields=["id", "name"],
        arguments={"limit": 10},
    )
    result = await router.execute(
        safe_plan,
        config=RunConfig(principal=employee),
    )
    assert result[0].data == [{"id": 1, "name": "Alice"}]

    forbidden_plan = _call(
        router,
        "company.employees",
        "select",
        fields=["id", "salary"],
        arguments={"limit": 10},
    )
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            forbidden_plan,
            config=RunConfig(principal=employee),
        )

    connection.close()


class _VectorBackend:
    supports_trusted_filters = True

    def __init__(self) -> None:
        self.filters: dict[str, Any] | None = None

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        return (
            VectorCollectionSpec(
                name="docs",
                dimension=2,
                metric="cosine",
                metadata_fields=(
                    VectorMetadataField(
                        name="title",
                        json_schema={"type": "string"},
                    ),
                    VectorMetadataField(
                        name="tenant",
                        json_schema={"type": "string"},
                        filterable=True,
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
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.filters = filters
        assert collection == "docs"
        return [
            {
                "id": "doc-1",
                "score": 0.99,
                "title": "Tenant A",
                "tenant": "tenant-a",
            }
        ]


@pytest.mark.asyncio
async def test_vector_scope_hides_tenant_field_and_injects_trusted_filter() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="vectors.docs.search",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="vectors.docs.search",
                roles_any=("employee",),
                visible_fields=("id", "score", "title"),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
            ),
        ),
    )
    backend = _VectorBackend()
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_vector_store(
        backend,
        lambda query: [0.1, 0.2],
        database_name="vectors",
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )

    view = await router.aretrieve_authorized(
        "tenant docs",
        principal=principal,
        k=5,
    )
    assert [field.name for field in view.candidates[0].output_fields] == [
        "id",
        "score",
        "title",
    ]

    result = await router.execute(
        _call(
            router,
            "vectors.docs",
            "search",
            fields=["id", "title"],
            arguments={"query": "routing", "top_k": 5},
        ),
        config=RunConfig(principal=principal),
    )
    assert result[0].data == [{"id": "doc-1", "title": "Tenant A"}]
    assert backend.filters == {"tenant": "tenant-a"}


class _UndeclaredScopedVectorBackend(_VectorBackend):
    supports_trusted_filters = False

    def __init__(self) -> None:
        super().__init__()
        self.search_called = False

    def search(
        self,
        *,
        collection: str,
        vector: list[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.search_called = True
        return super().search(
            collection=collection,
            vector=vector,
            top_k=top_k,
            include_fields=include_fields,
            filters=filters,
        )


@pytest.mark.asyncio
async def test_vector_scope_requires_explicit_filter_capability_before_query() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="vectors.docs.search",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="vectors.docs.search",
                roles_any=("employee",),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
            ),
        ),
    )
    backend = _UndeclaredScopedVectorBackend()
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_vector_store(
        backend,
        lambda query: [0.1, 0.2],
        database_name="vectors",
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            _call(
                router,
                "vectors.docs",
                "search",
                fields=["id", "title"],
                arguments={"query": "routing", "top_k": 5},
            ),
            config=RunConfig(principal=principal),
        )

    assert backend.search_called is False


class _RecordBackend:
    def __init__(self) -> None:
        self.filters: dict[str, Any] = {}

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        return (
            RecordSourceSpec(
                name="documents",
                model="document",
                supports_text_search=True,
                fields=(
                    RecordFieldSpec(
                        name="id",
                        json_schema={"type": "string"},
                        identifier=True,
                    ),
                    RecordFieldSpec(
                        name="title",
                        json_schema={"type": "string"},
                    ),
                    RecordFieldSpec(
                        name="tenant",
                        json_schema={"type": "string"},
                        filterable=True,
                    ),
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
        self.filters = dict(filters)
        return [{"id": "doc-1", "title": "Scoped", "tenant": "tenant-a"}]


@pytest.mark.asyncio
async def test_record_scope_injects_tenant_filter_without_model_parameter() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="nosql.documents.query",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="nosql.documents.query",
                roles_any=("employee",),
                visible_fields=("id", "title"),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
            ),
        ),
    )
    backend = _RecordBackend()
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_record_store(
        backend,
        database_name="nosql",
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )

    view = router.retrieve_authorized(
        "documents",
        principal=principal,
        k=5,
    )
    candidate = view.candidates[0]
    assert [field.name for field in candidate.output_fields] == ["id", "title"]
    assert "filter__tenant" not in {parameter.name for parameter in candidate.parameters}

    result = await router.execute(
        _call(
            router,
            "nosql.documents",
            "query",
            fields=["id", "title"],
            arguments={"query": "scope", "limit": 5},
        ),
        config=RunConfig(principal=principal),
    )
    assert result[0].data == [{"id": "doc-1", "title": "Scoped"}]
    assert backend.filters == {"tenant": "tenant-a"}


class _GraphBackend:
    def __init__(self) -> None:
        self.relationships: tuple[str, ...] = ()
        self.max_hops = 0

    def list_graphs(self) -> tuple[GraphSourceSpec, ...]:
        return (
            GraphSourceSpec(
                name="org",
                relationship_types=(
                    GraphRelationshipTypeSpec(name="MEMBER_OF"),
                    GraphRelationshipTypeSpec(name="MANAGES"),
                ),
            ),
        )

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        self.relationships = relationship_types
        self.max_hops = max_hops
        return [
            {
                "source_id": start_id,
                "target_id": "team-1",
                "relationship": "MEMBER_OF",
                "depth": 1,
                "source_type": "Person",
                "target_type": "Team",
            }
        ]


@pytest.mark.asyncio
async def test_graph_scope_restricts_relationship_schema_and_default_traversal() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="knowledge.org.traverse",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="knowledge.org.traverse",
                roles_any=("employee",),
                visible_fields=("source_id", "target_id", "relationship"),
                allowed_relationships=("MEMBER_OF",),
                max_hops=1,
            ),
        ),
    )
    backend = _GraphBackend()
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_graph_store(
        backend,
        database_name="knowledge",
        default_max_hops=3,
        remote=False,
    )
    principal = PrincipalContext(subject="alice", roles=("employee",))

    view = router.retrieve_authorized(
        "organization relationship",
        principal=principal,
        k=5,
    )
    candidate = view.candidates[0]
    parameters = {parameter.name: parameter for parameter in candidate.parameters}
    assert parameters["relationship_types"].json_schema["items"]["enum"] == [
        "MEMBER_OF"
    ]
    assert parameters["max_hops"].json_schema["maximum"] == 1
    assert [field.name for field in candidate.output_fields] == [
        "source_id",
        "target_id",
        "relationship",
    ]

    result = await router.execute(
        _call(
            router,
            "knowledge.org",
            "traverse",
            fields=["source_id", "target_id", "relationship"],
            arguments={"start_id": "person-1"},
        ),
        config=RunConfig(principal=principal),
    )
    assert result[0].data[0]["relationship"] == "MEMBER_OF"
    assert backend.relationships == ("MEMBER_OF",)
    assert backend.max_hops == 1

    forbidden = _call(
        router,
        "knowledge.org",
        "traverse",
        fields=["source_id", "relationship"],
        arguments={
            "start_id": "person-1",
            "relationship_types": ["MANAGES"],
            "max_hops": 2,
        },
    )
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            forbidden,
            config=RunConfig(principal=principal),
        )


@pytest.mark.parametrize(
    "invoker_type",
    [
        OpenAPIRemoteInvoker,
        HTTPJSONRemoteInvoker,
        GraphQLRemoteInvoker,
        OpenRPCRemoteInvoker,
        ODataRemoteInvoker,
        OPTIMADERemoteInvoker,
        MCPBoundInvoker,
        MCPRemoteInvoker,
    ],
)
def test_non_database_transports_do_not_claim_trusted_filter_enforcement(
    invoker_type: type,
) -> None:
    assert getattr(invoker_type, "supports_trusted_filters", False) is False


@pytest.mark.parametrize(
    "invoker_type",
    [
        SQLiteTableInvoker,
        SQLAlchemyTableInvoker,
        VectorCollectionInvoker,
        GraphSourceInvoker,
        RecordSourceInvoker,
    ],
)
def test_scoped_storage_invokers_declare_trusted_filter_enforcement(
    invoker_type: type,
) -> None:
    assert getattr(invoker_type, "supports_trusted_filters", False) is True


class _UnscopedCustomInvoker:
    def __init__(self) -> None:
        self.called = False

    async def __call__(
        self,
        endpoint: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        del endpoint, arguments
        self.called = True
        return {"id": "row-1"}


class _ScopedCustomInvoker:
    supports_trusted_filters = True

    def __init__(self) -> None:
        self.called = False
        self.filters: dict[str, Any] | None = None

    async def __call__(
        self,
        endpoint: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        del endpoint
        self.called = True
        scope = _current_data_scope()
        assert scope is not None
        self.filters = scope.filter_dict()
        assert "tenant" not in arguments
        return {"id": "row-1"}


def _custom_scoped_router(invoker: Any) -> tuple[SchemaRouter, ExecutionPlan, PrincipalContext]:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="custom.read.get",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="custom.read.get",
                roles_any=("employee",),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    tool = ToolSpec(
        name="custom.read",
        endpoints=[
            EndpointSpec(
                name="get",
                read_only=True,
                output_fields=[FieldSpec(name="id", identifier=True)],
            )
        ],
    )
    router.registry.register(tool)
    router.executor.bind(
        tool.key,
        invoker,
        expected_fingerprint=tool.fingerprint,
    )
    plan = _call(
        router,
        tool.key,
        "get",
        fields=["id"],
        arguments={},
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )
    return router, plan, principal


@pytest.mark.asyncio
async def test_trusted_filter_scope_rejects_unscoped_custom_invoker_before_io() -> None:
    invoker = _UnscopedCustomInvoker()
    router, plan, principal = _custom_scoped_router(invoker)

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(plan, config=RunConfig(principal=principal))

    assert invoker.called is False


@pytest.mark.asyncio
async def test_scoped_custom_invoker_receives_hidden_principal_filter() -> None:
    invoker = _ScopedCustomInvoker()
    router, plan, principal = _custom_scoped_router(invoker)

    result = await router.execute(plan, config=RunConfig(principal=principal))

    assert result[0].data == {"id": "row-1"}
    assert invoker.called is True
    assert invoker.filters == {"tenant": "tenant-a"}
