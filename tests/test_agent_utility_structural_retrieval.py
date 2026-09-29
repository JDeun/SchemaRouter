from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "evaluate_agent_utility_v5_structural_retrieval.py"
)

spec = importlib.util.spec_from_file_location("structural_retrieval", SCRIPT)
assert spec is not None and spec.loader is not None
structural = importlib.util.module_from_spec(spec)
spec.loader.exec_module(structural)


def test_conservative_identifier_singularization() -> None:
    assert structural._singularize_identifier("jobs") == "job"
    assert structural._singularize_identifier("studies") == "study"
    assert structural._singularize_identifier("glass") == "glass"
    assert (
        structural._singularize_identifier("aux_job_076")
        == "aux_job_076"
    )


def test_full_tool_identifier_match_does_not_match_aux_component() -> None:
    canonical = SimpleNamespace(name="jobs", key="jobs")
    auxiliary = SimpleNamespace(
        name="aux_job_076",
        key="aux_job_076",
    )
    query_tokens = {"modify", "job", "cancellation"}

    assert structural._tool_identifier_match(
        query_tokens,
        canonical,
    )
    assert not structural._tool_identifier_match(
        query_tokens,
        auxiliary,
    )


def test_operation_family_recovers_common_nominalizations() -> None:
    assert structural._same_operation_family(
        "cancellation",
        "cancel",
    )
    assert structural._same_operation_family(
        "retrieval",
        "retrieve",
    )
    assert structural._same_operation_family(
        "creation",
        "create",
    )
    assert structural._same_operation_family(
        "archiving",
        "archive",
    )


def test_operation_family_rejects_unrelated_operations() -> None:
    assert not structural._same_operation_family(
        "search",
        "send",
    )
    assert not structural._same_operation_family(
        "status",
        "start",
    )
    assert not structural._same_operation_family(
        "read",
        "restart",
    )


def test_operation_aliases_participate_in_family_matching() -> None:
    endpoint = SimpleNamespace(
        name="get",
        operation_aliases=["read record"],
    )

    assert structural._operation_family_match(
        {"please", "read", "sample"},
        endpoint,
    )
