import sqlite3

import pytest

pytest.importorskip("llama_index.core")

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
    schema_tool,
    TrustedFilterBinding,
)
from schemarouter.integrations.llamaindex import (
    _llamaindex_schema_model,
    to_llamaindex_tool,
    to_llamaindex_tools,
    tool_from_llamaindex,
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


def test_llamaindex_tool_preserves_metadata_and_sync_execution() -> None:
    router = make_router()
    tool = to_llamaindex_tool(router, "add", "call")

    assert tool.metadata.name == "schemarouter__add__call"
    assert tool.metadata.description == "Add two integers."
    parameters = tool.metadata.get_parameters_dict()
    assert parameters["properties"]["a"]["type"] == "integer"
    assert parameters["properties"]["b"]["type"] == "integer"
    assert set(parameters["required"]) == {"a", "b"}
    assert tool(a=2, b=3).raw_output == 5


@pytest.mark.asyncio
async def test_llamaindex_tool_supports_async_execution() -> None:
    router = make_router()
    tool = to_llamaindex_tool(router, "add", "call")

    result = await tool.acall(a=4, b=5)
    assert result.raw_output == 9


def test_llamaindex_tool_still_enforces_schemarouter_validation() -> None:
    router = make_router()
    tool = to_llamaindex_tool(router, "add", "call")

    with pytest.raises(SchemaValidationError):
        tool(a="not-an-int", b=3)


def test_llamaindex_tool_collection_exports_registered_endpoints() -> None:
    tools = to_llamaindex_tools(make_router())
    assert [tool.metadata.name for tool in tools] == ["schemarouter__add__call"]



def test_llamaindex_schema_model_rewrites_openapi_component_refs() -> None:
    schema_model = _llamaindex_schema_model(
        {
            "type": "object",
            "properties": {
                "payload": {"$ref": "#/components/schemas/Payload"},
            },
            "required": ["payload"],
            "additionalProperties": False,
            "components": {
                "schemas": {
                    "Payload": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                    }
                }
            },
        },
        model_name="NestedArgs",
    )

    exported = schema_model.model_json_schema()
    assert exported["properties"]["payload"]["$ref"] == "#/$defs/Payload"
    assert exported["$defs"]["Payload"]["properties"]["value"]["type"] == "string"


def test_llamaindex_tool_cannot_bypass_execution_policy() -> None:
    router = SchemaRouter()
    router.add_callable(mutate_value)
    tool = to_llamaindex_tool(router, "mutate_value", "call")

    with pytest.raises(PolicyViolationError, match="allow_mutations"):
        tool(value=7)


def test_llamaindex_tool_can_be_imported_back_into_schemarouter() -> None:
    from llama_index.core.tools import FunctionTool

    def search(query: str) -> str:
        """Search one fixture source."""
        return f"found:{query}"

    foreign = FunctionTool.from_defaults(fn=search)
    imported = tool_from_llamaindex(
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
    key = router.add_llamaindex_tool(
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

def test_llamaindex_export_requires_principal_when_authorization_is_enabled() -> None:
    router, connection = make_authorized_database_router()
    try:
        with pytest.raises(PolicyViolationError, match="principal context is required"):
            to_llamaindex_tool(router, "company.employees", "select")
        with pytest.raises(PolicyViolationError, match="principal context is required"):
            to_llamaindex_tools(router)
    finally:
        connection.close()


def test_llamaindex_export_projects_data_scope_and_executes_with_principal() -> None:
    router, connection = make_authorized_database_router()
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"department": "sales"},
    )
    try:
        tool = to_llamaindex_tool(
            router,
            "company.employees",
            "select",
            run_config=RunConfig(principal=principal),
        )
        parameters = tool.metadata.get_parameters_dict()["properties"]
        assert "filter__salary" not in parameters
        assert "filter__department" not in parameters

        result = tool(limit=10)
        assert result.raw_output == [{"id": 1, "name": "Alice"}]
    finally:
        connection.close()


def test_llamaindex_collection_filters_denied_endpoints() -> None:
    router, connection = make_authorized_database_router()
    denied = PrincipalContext(subject="guest", roles=("guest",))
    employee = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"department": "sales"},
    )
    try:
        assert to_llamaindex_tools(
            router,
            run_config=RunConfig(principal=denied),
        ) == []
        assert len(
            to_llamaindex_tools(
                router,
                run_config=RunConfig(principal=employee),
            )
        ) == 1
    finally:
        connection.close()

