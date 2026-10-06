from __future__ import annotations

import sqlite3

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
)

from schemarouter.errors import RegistrationError
from schemarouter.registry import InMemoryRegistry


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE board_financials (
            id INTEGER PRIMARY KEY,
            quarter TEXT NOT NULL,
            forecast REAL NOT NULL
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
    connection.executemany(
        "INSERT INTO board_financials(id, quarter, forecast) VALUES (?, ?, ?)",
        [
            (1, "Q1", 500.0),
            (2, "Q2", 650.0),
        ],
    )
    connection.execute(
        """
        CREATE VIEW employee_directory AS
        SELECT id, name, department FROM employees
        """
    )
    connection.commit()
    return connection


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    fields: list[str],
    arguments: dict[str, object] | None = None,
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("select")
    return ExecutionPlan(
        query=f"read {tool_key}",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=arguments or {},
                fields=fields,
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


def test_sqlite_introspection_registers_typed_tables_and_views() -> None:
    connection = _connection()
    router = SchemaRouter()

    keys = router.add_sqlite_database(
        connection,
        database_name="company",
    )

    assert set(keys) == {
        "company.board_financials",
        "company.employee_directory",
        "company.employees",
    }

    employees = router.registry.get("company.employees")
    endpoint = employees.endpoint("select")
    assert employees.source_type == "database"
    assert employees.provider == "company"
    assert employees.access_mode == "sqlite"
    assert employees.remote is False
    assert endpoint.read_only is True
    assert endpoint.destructive is False
    assert [field.name for field in endpoint.output_fields] == [
        "id",
        "name",
        "department",
        "salary",
    ]
    assert endpoint.output_fields[0].identifier is True
    assert {parameter.name for parameter in endpoint.parameters} == {
        "id",
        "limit",
        "offset",
    }

    connection.close()


@pytest.mark.asyncio
async def test_sqlite_execution_is_projected_parameterized_and_bounded() -> None:
    connection = _connection()
    router = SchemaRouter()
    router.add_sqlite_database(connection, database_name="company")

    result = await router.execute(
        _plan(
            router,
            "company.employees",
            fields=["id", "name", "department"],
            arguments={"id": 2, "limit": 10},
        )
    )

    assert result[0].data == [
        {
            "id": 2,
            "name": "Bob",
            "department": "engineering",
        }
    ]

    with pytest.raises(PlanValidationError, match="undeclared arguments"):
        await router.execute(
            _plan(
                router,
                "company.employees",
                fields=["id", "name"],
                arguments={"where": "1=1; DROP TABLE employees"},
            )
        )

    assert connection.execute("SELECT COUNT(*) FROM employees").fetchone() == (2,)
    connection.close()


@pytest.mark.asyncio
async def test_sqlite_execution_honors_configured_default_limit() -> None:
    connection = _connection()
    router = SchemaRouter()
    router.add_sqlite_database(
        connection,
        database_name="company",
        tables={"employees"},
        max_default_rows=1,
    )

    result = await router.execute(
        _plan(
            router,
            "company.employees",
            fields=["id", "name"],
        )
    )

    assert len(result[0].data) == 1
    connection.close()


def test_sqlite_registration_can_limit_visible_tables_before_model_exposure() -> None:
    connection = _connection()
    router = SchemaRouter()

    keys = router.add_sqlite_database(
        connection,
        database_name="company",
        tables={"employee_directory"},
    )

    assert keys == ("company.employee_directory",)
    assert router.registry.keys() == ("company.employee_directory",)
    connection.close()


@pytest.mark.asyncio
async def test_database_tools_compose_with_employee_and_executive_authorization() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="employee-directory",
                effect="allow",
                operation="company.employee_directory.*",
                roles_any=("employee", "manager", "executive"),
            ),
            AuthorizationRule(
                name="employee-table-managers",
                effect="allow",
                operation="company.employees.*",
                roles_any=("manager", "executive"),
            ),
            AuthorizationRule(
                name="board-only-executive",
                effect="allow",
                operation="company.board_financials.*",
                roles_any=("executive",),
            ),
        )
    )
    connection = _connection()
    router = SchemaRouter(authorization_policy=policy)
    router.add_sqlite_database(connection, database_name="company")

    employee = PrincipalContext(subject="alice", roles=("employee",))
    manager = PrincipalContext(subject="manager", roles=("manager",))
    executive = PrincipalContext(subject="ceo", roles=("executive",))

    employee_retrieval = router.retrieve_authorized(
        "board forecast finance",
        principal=employee,
        k=5,
    )
    assert all(
        candidate.tool != "company.board_financials"
        for candidate in employee_retrieval.candidates
    )

    manager_retrieval = router.retrieve_authorized(
        "employee salary",
        principal=manager,
        k=5,
    )
    assert any(
        candidate.tool == "company.employees"
        for candidate in manager_retrieval.candidates
    )

    executive_plan = _plan(
        router,
        "company.board_financials",
        fields=["quarter", "forecast"],
        arguments={"id": 1},
    )

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            executive_plan,
            config=RunConfig(principal=employee),
        )

    result = await router.execute(
        executive_plan,
        config=RunConfig(principal=executive),
    )
    assert result[0].data == [{"quarter": "Q1", "forecast": 500.0}]

    connection.close()


def test_sqlite_database_connection_never_enters_model_visible_metadata() -> None:
    connection = _connection()
    router = SchemaRouter()
    router.add_sqlite_database(connection, database_name="company")

    tool = router.registry.get("company.employees")
    serialized = tool.model_dump(mode="json")

    assert ":memory:" not in repr(serialized)
    assert "sqlite3.Connection" not in repr(serialized)
    assert "connection" not in serialized["metadata"]
    assert "connection" not in serialized["execution_metadata"]

    connection.close()


def test_sqlite_registration_rolls_back_all_contracts_on_middle_bind_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _connection()
    router = SchemaRouter()
    real_bind = router.executor.bind
    bind_calls = 0

    def fail_middle_bind(*args, **kwargs):
        nonlocal bind_calls
        bind_calls += 1
        if bind_calls == 2:
            raise RuntimeError("injected middle SQLite bind failure")
        return real_bind(*args, **kwargs)

    monkeypatch.setattr(router.executor, "bind", fail_middle_bind)

    with pytest.raises(RuntimeError, match="middle SQLite bind failure"):
        router.add_sqlite_database(
            connection,
            database_name="company",
        )

    assert bind_calls == 2
    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()
    assert connection.execute("SELECT 1").fetchone() == (1,)
    connection.close()


def test_sqlite_registration_rejects_concurrent_key_insertion_atomically() -> None:
    class RacingRegistry(InMemoryRegistry):
        raced = False

        def update_many_if_version(
            self,
            tools,
            *,
            expected_version: int,
            replace: bool = False,
        ) -> tuple[str, ...]:
            staged = tuple(tools)
            if not self.raced:
                self.raced = True
                # Simulate another writer publishing a colliding key after
                # SQLite introspection but before this batch can commit.
                super().register(staged[0])
            return super().update_many_if_version(
                staged,
                expected_version=expected_version,
                replace=replace,
            )

    connection = _connection()
    registry = RacingRegistry()
    router = SchemaRouter(registry=registry)

    with pytest.raises(RegistrationError, match="registry changed concurrently"):
        router.add_sqlite_database(
            connection,
            database_name="company",
        )

    assert len(registry.keys()) == 1
    concurrent_key = registry.keys()[0]
    assert concurrent_key.startswith("company.")
    assert router.executor.bound_keys() == ()
    assert connection.execute("SELECT 1").fetchone() == (1,)
    connection.close()
