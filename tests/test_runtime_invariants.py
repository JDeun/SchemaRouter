from __future__ import annotations

import ast
import inspect

import pytest

import schemarouter.runtime as runtime_module
from schemarouter import ExecutionInvariantError, InvocationUnavailableError
from schemarouter.runtime import (
    _require_execution_event_exception,
    _require_unavailable_event_payload,
)


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


@pytest.mark.parametrize(
    "payload",
    [
        None,
        (),
        (InvocationUnavailableError("temporarily unavailable"), None),
        (InvocationUnavailableError("temporarily unavailable"), None, 0, "extra"),
    ],
)
def test_unavailable_event_guard_rejects_invalid_tuple_shape(payload: object) -> None:
    with pytest.raises(
        ExecutionInvariantError,
        match="expected a 3-item tuple",
    ):
        _require_unavailable_event_payload(payload)


def test_unavailable_event_guard_rejects_invalid_next_call() -> None:
    with pytest.raises(
        ExecutionInvariantError,
        match="expected ToolCall or None",
    ):
        _require_unavailable_event_payload(
            (InvocationUnavailableError("temporarily unavailable"), object(), 0)
        )


@pytest.mark.parametrize("candidate_index", [True, -1, "0"])
def test_unavailable_event_guard_rejects_invalid_candidate_index(
    candidate_index: object,
) -> None:
    with pytest.raises(
        ExecutionInvariantError,
        match="non-negative integer candidate index",
    ):
        _require_unavailable_event_payload(
            (InvocationUnavailableError("temporarily unavailable"), None, candidate_index)
        )


def test_unavailable_event_guard_accepts_terminal_unavailable_payload() -> None:
    error = InvocationUnavailableError("temporarily unavailable")

    assert _require_unavailable_event_payload((error, None, 0)) == (error, None, 0)
