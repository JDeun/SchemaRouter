"""SQLAlchemy registered read-only native execution through public SchemaRouter.execute."""
from __future__ import annotations

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, event  # noqa: E402

from schemarouter import (  # noqa: E402
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


def _plan(router: SchemaRouter, tool_key: str, arguments: dict) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("select")
    return ExecutionPlan(
        query="read order",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool_key,
                endpoint="select",
                arguments=arguments,
                fields=["id", "customer"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


@pytest.mark.asyncio
async def test_sqlalchemy_registered_public_execute_denies_before_driver_and_blocks_sql() -> None:
    """Rejected plans do not reach the real SQLAlchemy database engine."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO orders (id, customer) VALUES (1, 'Acme')"
            )

        auth = AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    effect="allow",
                    operation="warehouse.orders.select",
                    roles_any=("reader",),
                ),
            ),
            default_effect="deny",
        )
        router = SchemaRouter(authorization_policy=auth)
        keys = router.add_sqlalchemy_database(
            engine, database_name="warehouse", remote=False
        )
        assert keys == ("warehouse.orders",)
        endpoint = router.registry.get(keys[0]).endpoint("select")
        assert endpoint.read_only is True
        assert endpoint.destructive is False

        driver_calls: list[str] = []

        def track_execute(conn, cursor, statement, parameters, context, executemany):
            driver_calls.append(statement)

        event.listen(engine, "before_cursor_execute", track_execute)
        reader = RunConfig(
            principal=PrincipalContext(subject="reader", roles=("reader",))
        )
        guest = RunConfig(
            principal=PrincipalContext(subject="guest", roles=("guest",))
        )
        plan = _plan(router, keys[0], {"id": 1, "limit": 5})

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(plan, config=guest)
        assert driver_calls == []

        with pytest.raises(PlanValidationError, match="undeclared arguments"):
            await router.execute(
                _plan(router, keys[0], {"sql": "DELETE FROM orders"}),
                config=reader,
            )
        assert driver_calls == []

        result = await router.execute(plan, config=reader)
        assert result[0].data == [{"id": 1, "customer": "Acme"}]
        assert len(driver_calls) == 1
        assert driver_calls[0].lstrip().upper().startswith("SELECT")

        # The public runtime must deny a stale receipt after deregistration.
        router.remove_tool(keys[0])
        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(plan, config=reader)
        assert len(driver_calls) == 1
    finally:
        engine.dispose()
