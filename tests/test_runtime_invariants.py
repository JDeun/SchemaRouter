from __future__ import annotations

import ast
import inspect

import pytest

import schemarouter.runtime as runtime_module
from schemarouter import ExecutionInvariantError, InvocationUnavailableError
from schemarouter.runtime import _require_execution_event_exception


def test_runtime_module_contains_no_production_assert_statements() -> None:
    tree = ast.parse(inspect.getsource(runtime_module))
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
    ]


def test_parallel_event_exception_guard_accepts_expected_exception() -> None:
    error = RuntimeError("boom")

    assert (
        _require_execution_event_exception(
            error,
            event_kind="error",
        )
        is error
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "error",
        1,
        object(),
    ],
)
def test_parallel_event_exception_guard_rejects_invalid_payload(payload: object) -> None:
    with pytest.raises(
        ExecutionInvariantError,
        match="parallel execution event payload violated the internal contract",
    ):
        _require_execution_event_exception(
            payload,
            event_kind="error",
        )


def test_parallel_unavailable_guard_requires_specific_exception_type() -> None:
    with pytest.raises(
        ExecutionInvariantError,
        match="InvocationUnavailableError",
    ):
        _require_execution_event_exception(
            RuntimeError("wrong error kind"),
            event_kind="unavailable",
            expected_type=InvocationUnavailableError,
        )


def test_parallel_unavailable_guard_accepts_unavailable_error() -> None:
    error = InvocationUnavailableError("temporarily unavailable")

    assert (
        _require_execution_event_exception(
            error,
            event_kind="unavailable",
            expected_type=InvocationUnavailableError,
        )
        is error
    )
