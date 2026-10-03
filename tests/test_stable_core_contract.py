from __future__ import annotations

import inspect

from schemarouter import (
    CapabilityCandidate,
    ConfiguredSchemaRouter,
    SchemaRouter,
)


def _assert_retrieval_signature(owner: type, name: str) -> None:
    signature = inspect.signature(getattr(owner, name))
    parameters = list(signature.parameters.values())

    assert [parameter.name for parameter in parameters] == ["self", "request", "k"]
    assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters[1].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters[2].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[2].default == 5


def test_stable_retrieval_facade_signatures_are_aligned() -> None:
    for owner in (SchemaRouter, ConfiguredSchemaRouter):
        for name in (
            "retrieve",
            "aretrieve",
            "retrieve_executable",
            "aretrieve_executable",
        ):
            _assert_retrieval_signature(owner, name)


def test_capability_candidate_keeps_full_schema_contract() -> None:
    fields = CapabilityCandidate.model_fields

    assert "parameters" in fields
    assert "input_schema" in fields
    assert "output_fields" in fields
    assert "output_schema" in fields
    assert "read_only" in fields
    assert "destructive" in fields
    assert "tool_fingerprint" in fields
    assert "endpoint_fingerprint" in fields


def test_retrieval_facade_remains_separate_from_execution_verbs() -> None:
    retrieval = {
        "retrieve",
        "aretrieve",
        "retrieve_executable",
        "aretrieve_executable",
    }
    execution = {
        "execute",
        "invoke",
        "ainvoke",
        "batch",
        "abatch",
        "stream",
        "astream",
    }

    assert retrieval.isdisjoint(execution)
    assert retrieval <= set(dir(SchemaRouter))
    assert execution <= set(dir(SchemaRouter))
