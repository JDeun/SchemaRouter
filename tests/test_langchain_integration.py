import sqlite3

import pytest

pytest.importorskip("langchain_core")

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
    TrustedFilterBinding,
    schema_tool,
)
from schemarouter.integrations import (
    to_langchain_tool,
    to_langchain_tools,
    tool_from_langchain,
)


def make_authorized_database_router() -> tuple[SchemaRouter, sqlite3.Connection]:
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

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="company.employees.select",
                roles_any=("employee", "executive"),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="company.employees.select",
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
                operation="company.employees.select",
                roles_any=("executive",),
                visible_fields=("id", "name", "department", "salary"),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_sqlite_database(connection, database_name="company")
    return router, connection


@schema_tool(read_only=True)
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@schema_tool(read_only=False)
def mutate_value(value: int) -> int:
    """Mutate one value."""
    return value


def make_router() -> SchemaRouter:
    router = SchemaRouter()
    router.add_callable(add)
    return router


def test_langchain_tool_preserves_schema_and_sync_execution() -> None:
    router = make_router()
    tool = to_langchain_tool(router, "add", "call")

    assert tool.name == "schemarouter__add__call"
    assert tool.description == "Add two integers."
    assert tool.args_schema["properties"]["a"]["type"] == "integer"
    assert tool.args_schema["properties"]["b"]["type"] == "integer"
    assert tool.invoke({"a": 2, "b": 3}) == 5


@pytest.mark.asyncio
async def test_langchain_tool_supports_async_execution() -> None:
    router = make_router()
    tool = to_langchain_tool(router, "add", "call")

    assert await tool.ainvoke({"a": 4, "b": 5}) == 9


def test_langchain_tool_still_enforces_schemarouter_validation() -> None:
    router = make_router()
    tool = to_langchain_tool(router, "add", "call")

    with pytest.raises(SchemaValidationError):
        tool.invoke({"a": "not-an-int", "b": 3})


def test_langchain_tool_collection_exports_registered_endpoints() -> None:
    router = make_router()
    tools = to_langchain_tools(router)

    assert [tool.name for tool in tools] == ["schemarouter__add__call"]


def test_langchain_tool_cannot_bypass_execution_policy() -> None:
    router = SchemaRouter()
    router.add_callable(mutate_value)
    tool = to_langchain_tool(router, "mutate_value", "call")

    with pytest.raises(PolicyViolationError, match="allow_mutations"):
        tool.invoke({"value": 7})


def test_langchain_tool_can_be_imported_back_into_schemarouter() -> None:
    from langchain_core.tools import StructuredTool

    def search(query: str) -> str:
        """Search one fixture source."""
        return f"found:{query}"

    foreign = StructuredTool.from_function(search)
    imported = tool_from_langchain(
        foreign,
        read_only=True,
        remote=False,
        provider="fixture-search",
    )

    endpoint = imported.endpoint("invoke")
    assert endpoint.parameters[0].name == "query"
    assert endpoint.read_only is True
    assert imported.provider == "fixture-search"

    router = SchemaRouter()
    key = router.add_langchain_tool(
        foreign,
        read_only=True,
        remote=False,
        provider="fixture-search",
    )
    result = router.invoke(
        PlanRequest(
            query="search fixture",
            preferred_tools=[key],
            arguments={"query": "hello"},
        )
    )

    assert result[0].data == "found:hello"

def test_langchain_export_requires_principal_when_authorization_is_enabled() -> None:
    router, connection = make_authorized_database_router()
    events = []
    router.authorization_audit_hook = events.append
    try:
        with pytest.raises(PolicyViolationError, match="principal context is required"):
            to_langchain_tool(router, "company.employees", "select")
        with pytest.raises(PolicyViolationError, match="principal context is required"):
            to_langchain_tools(router)

        assert len(events) == 2
        assert all(event.effect == "deny" for event in events)
        assert all(event.phase == "export" for event in events)
        assert all(event.decision_source == "missing_principal" for event in events)
        assert all(event.run_id for event in events)
    finally:
        connection.close()


def test_langchain_export_projects_data_scope_and_executes_with_principal() -> None:
    router, connection = make_authorized_database_router()
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"department": "sales"},
    )
    try:
        tool = to_langchain_tool(
            router,
            "company.employees",
            "select",
            run_config=RunConfig(principal=principal),
        )
        properties = tool.args_schema["properties"]
        assert "filter__salary" not in properties
        assert "filter__department" not in properties

        result = tool.invoke({"limit": 10})
        assert result == [{"id": 1, "name": "Alice"}]
    finally:
        connection.close()


def test_langchain_collection_filters_denied_endpoints() -> None:
    router, connection = make_authorized_database_router()
    denied = PrincipalContext(subject="guest", roles=("guest",))
    employee = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"department": "sales"},
    )
    try:
        assert to_langchain_tools(
            router,
            run_config=RunConfig(principal=denied),
        ) == []
        assert len(
            to_langchain_tools(
                router,
                run_config=RunConfig(principal=employee),
            )
        ) == 1
    finally:
        connection.close()



def test_langchain_authorization_audit_correlates_export_and_execution() -> None:
    router, connection = make_authorized_database_router()
    events = []
    router.authorization_audit_hook = events.append
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"department": "sales"},
    )
    try:
        tool = to_langchain_tool(
            router,
            "company.employees",
            "select",
            run_config=RunConfig(
                principal=principal,
                principal_audit_id="opaque-langchain-principal",
            ),
        )
        assert len(events) == 1
        assert events[0].phase == "export"
        export_run_id = events[0].run_id
        assert export_run_id
        assert events[0].principal_audit_id == "opaque-langchain-principal"

        result = tool.invoke({"limit": 10})
        assert result == [{"id": 1, "name": "Alice"}]
        assert len(events) == 2
        assert events[1].phase == "execution"
        assert events[1].run_id == export_run_id
        assert events[1].principal_audit_id == "opaque-langchain-principal"
        assert "sales" not in repr(events)
    finally:
        connection.close()
