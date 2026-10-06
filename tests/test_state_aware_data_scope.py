from __future__ import annotations

import sqlite3

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.authorization import _principal_execution_context
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.execution_state import ObservedStateField, TypedExecutionState
from schemarouter.models import CapabilityCandidate


def _scoped_router() -> tuple[SchemaRouter, sqlite3.Connection, PrincipalContext]:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            salary REAL NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO employees(id, name, salary) VALUES (1, 'Alice', 100.0)"
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
                visible_fields=("id", "name"),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_sqlite_database(connection, database_name="company")
    principal = PrincipalContext(subject="alice", roles=("employee",))
    return router, connection, principal


def _candidate_surface(candidate: CapabilityCandidate) -> tuple[object, ...]:
    output_fields = tuple(field.name for field in candidate.output_fields)
    parameters = tuple(parameter.name for parameter in candidate.parameters)
    return (
        output_fields,
        parameters,
        tuple(candidate.matched_fields),
        candidate.input_schema,
        candidate.output_schema,
    )


@pytest.mark.asyncio
async def test_state_aware_retrieval_matches_normal_data_scope_sync_and_async() -> None:
    router, connection, principal = _scoped_router()
    try:
        normal = router.retrieve_authorized(
            "employee name salary",
            principal=principal,
            k=5,
        )
        assert normal.candidates
        expected = _candidate_surface(normal.candidates[0])
        assert "salary" not in repr(expected)

        with _principal_execution_context(principal):
            sync_initial = router.retrieve_state_aware(
                "employee name salary",
                execution_state=TypedExecutionState(),
                k=5,
            )
            sync_backfill = router.reretrieve_state_aware(
                "employee name salary",
                execution_state=TypedExecutionState(),
                k=5,
            )
            async_initial = await router.aretrieve_state_aware(
                "employee name salary",
                execution_state=TypedExecutionState(),
                k=5,
            )
            async_backfill = await router.areretrieve_state_aware(
                "employee name salary",
                execution_state=TypedExecutionState(),
                k=5,
            )

        for result in (
            sync_initial,
            sync_backfill,
            async_initial,
            async_backfill,
        ):
            assert result.candidates
            assert _candidate_surface(result.candidates[0].candidate) == expected
            assert "salary" not in repr(result.candidates[0].candidate)
    finally:
        connection.close()


def test_state_backfill_cannot_revive_fully_hidden_endpoint() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE public_docs (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE payroll (
            id INTEGER PRIMARY KEY,
            salary REAL NOT NULL
        )
        """
    )
    connection.commit()

    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="company.*.select",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="company.payroll.select",
                roles_any=("employee",),
                visible_fields=(),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_sqlite_database(connection, database_name="company")
    principal = PrincipalContext(subject="alice", roles=("employee",))
    state = TypedExecutionState(
        observed_fields=(
            ObservedStateField(
                contract=CapabilityFieldContract(
                    semantic_id="salary",
                    json_schema={"type": "number"},
                )
            ),
        )
    )
    requirements = {
        "company.payroll.select": [
            CapabilityFieldContract(
                semantic_id="salary",
                json_schema={"type": "number"},
            )
        ]
    }

    try:
        with _principal_execution_context(principal):
            initial = router.retrieve_state_aware(
                "salary payroll",
                execution_state=state,
                k=5,
                state_requirements=requirements,
            )
            backfilled = router.reretrieve_state_aware(
                "salary payroll",
                execution_state=state,
                k=5,
                state_requirements=requirements,
            )

        initial_routes = {item.candidate.route_id for item in initial.candidates}
        backfill_routes = {item.candidate.route_id for item in backfilled.candidates}
        excluded_routes = {item.candidate.route_id for item in backfilled.excluded}

        assert "company.payroll.select" not in initial_routes
        assert "company.payroll.select" not in backfill_routes
        assert "company.payroll.select" not in excluded_routes
    finally:
        connection.close()
