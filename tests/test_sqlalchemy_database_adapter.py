from __future__ import annotations

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine  # noqa: E402

from schemarouter import (  # noqa: E402
    ExecutionPlan,
    PlanValidationError,
    SchemaRouter,
    ToolCall,
)
from schemarouter.errors import RegistrationError  # noqa: E402


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer TEXT NOT NULL,
                region TEXT NOT NULL,
                total REAL NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO orders(id, customer, region, total)
            VALUES
                (1, 'Acme', 'apac', 120.5),
                (2, 'Globex', 'emea', 200.0)
            """
        )
    return engine


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


def test_sqlalchemy_engine_introspection_compiles_relational_contract() -> None:
    engine = _engine()
    router = SchemaRouter()

    keys = router.add_sqlalchemy_database(
        engine,
        database_name="warehouse",
        remote=False,
    )

    assert keys == ("warehouse.orders",)
    tool = router.registry.get("warehouse.orders")
    endpoint = tool.endpoint("select")
    assert tool.source_type == "database"
    assert tool.provider == "warehouse"
    assert tool.access_mode == "sqlalchemy"
    assert tool.remote is False
    assert endpoint.read_only is True
    assert endpoint.destructive is False
    assert [field.name for field in endpoint.output_fields] == [
        "id",
        "customer",
        "region",
        "total",
    ]
    assert endpoint.output_fields[0].identifier is True
    assert {parameter.name for parameter in endpoint.parameters} == {
        "id",
        "limit",
        "offset",
    }

    engine.dispose()


@pytest.mark.asyncio
async def test_sqlalchemy_execution_uses_core_projection_and_parameter_binding() -> None:
    engine = _engine()
    router = SchemaRouter()
    router.add_sqlalchemy_database(
        engine,
        database_name="warehouse",
        remote=False,
    )

    result = await router.execute(
        _plan(
            router,
            "warehouse.orders",
            fields=["id", "customer", "total"],
            arguments={"id": 1, "limit": 5},
        )
    )
    assert result[0].data == [
        {
            "id": 1,
            "customer": "Acme",
            "total": 120.5,
        }
    ]

    with pytest.raises(PlanValidationError, match="undeclared arguments"):
        await router.execute(
            _plan(
                router,
                "warehouse.orders",
                fields=["id"],
                arguments={"sql": "DROP TABLE orders"},
            )
        )

    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM orders").scalar_one() == 2

    engine.dispose()


def test_sqlalchemy_engine_object_and_url_are_not_model_visible() -> None:
    engine = _engine()
    router = SchemaRouter()
    router.add_sqlalchemy_database(
        engine,
        database_name="warehouse",
        remote=False,
    )

    tool = router.registry.get("warehouse.orders")
    serialized = tool.model_dump(mode="json")
    rendered = repr(serialized)

    assert "sqlite+pysqlite:///:memory:" not in rendered
    assert "Engine(" not in rendered
    assert "engine" not in serialized["metadata"]
    assert "engine" not in serialized["execution_metadata"]

    engine.dispose()

@pytest.mark.asyncio
async def test_native_sqlalchemy_schema_refresh_reintrospects_current_contract() -> None:
    engine = _engine()
    router = SchemaRouter()
    try:
        router.add_sqlalchemy_database(
            engine,
            database_name="warehouse",
            remote=False,
        )

        result = await router.arefresh_native_schema("warehouse.orders")

        tool = router.registry.get("warehouse.orders")
        assert result.action == "unchanged"
        assert router.executor.is_binding_ready_for_contract(tool.key, tool.fingerprint)
    finally:
        engine.dispose()



def test_sqlalchemy_discovery_rejects_oversized_relation_catalog_atomically() -> None:
    engine = _engine()
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
            )

        router = SchemaRouter()
        with pytest.raises(RegistrationError, match="max_discovery_relations=1"):
            router.add_sqlalchemy_database(
                engine,
                database_name="warehouse",
                max_discovery_relations=1,
                remote=False,
            )

        assert router.registry.keys() == ()
    finally:
        engine.dispose()


def test_sqlalchemy_discovery_rejects_wide_relation_atomically() -> None:
    engine = _engine()
    try:
        router = SchemaRouter()
        with pytest.raises(RegistrationError, match="exposes 4 columns"):
            router.add_sqlalchemy_database(
                engine,
                database_name="warehouse",
                max_columns_per_relation=3,
                remote=False,
            )

        assert router.registry.keys() == ()
    finally:
        engine.dispose()
