"""Offline unhinted source-task routing evaluation through the real native planner."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

from schemarouter import EndpointSpec, FieldSpec, ParameterSpec, SchemaRouter, ToolSpec


def _offline_registered_source_router() -> tuple[SchemaRouter, list[str]]:
    """Original-shaped routes: real registry/planner, never fake ranking outputs."""
    router = SchemaRouter()
    called: list[str] = []

    def no_network(endpoint: str, arguments: dict) -> dict:
        called.append(endpoint)
        raise AssertionError("retrieval/plan evaluation must not execute providers")

    router.add_bound_tool(
        ToolSpec(
            name="crossref",
            provider="crossref",
            access_mode="http_json",
            endpoints=[
                EndpointSpec(
                    name="get_work",
                    method="GET",
                    path="/works/{doi}",
                    read_only=True,
                    description="Get one Crossref work by DOI.",
                    parameters=[ParameterSpec(name="doi", location="path", required=True)],
                    output_fields=[FieldSpec(name="message", json_schema={"type": "object"})],
                )
            ],
        ),
        no_network,
    )
    router.add_bound_tool(
        ToolSpec(
            name="cod_public",
            provider="cod",
            access_mode="optimade",
            endpoints=[
                EndpointSpec(
                    name="search_structures",
                    method="GET",
                    path="/structures",
                    read_only=True,
                    description="Search crystal structures using an OPTIMADE filter.",
                    parameters=[ParameterSpec(name="filter", location="query")],
                    output_fields=[
                        FieldSpec(name="chemical_formula_descriptive"),
                        FieldSpec(name="nelements"),
                        FieldSpec(name="elements"),
                    ],
                )
            ],
        ),
        no_network,
    )
    router.add_bound_tool(
        ToolSpec(
            name="deepwiki_public",
            provider="deepwiki",
            access_mode="mcp",
            endpoints=[
                EndpointSpec(
                    name="read_wiki_structure",
                    method="GET",
                    read_only=True,
                    description="Read public repository wiki structure.",
                    parameters=[ParameterSpec(name="repoName", required=True)],
                    output_fields=[FieldSpec(name="result", json_schema={"type": "string"})],
                )
            ],
        ),
        no_network,
    )
    return router, called


def test_offline_metric_scoring_cannot_count_zero_score_as_evidence() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import score_selection_report

    rows = [
        {
            "id": "en_crossref",
            "language": "en",
            "expected_route": "crossref.get_work",
            "candidates": [
                {"route_id": "cod_public.search_structures", "score": 5.0},
                {"route_id": "crossref.get_work", "score": 3.0},
            ],
        },
        {
            "id": "ko_cod",
            "language": "ko",
            "expected_route": "cod_public.search_structures",
            "candidates": [{"route_id": "cod_public.search_structures", "score": 0.0}],
        },
        {
            "id": "negative",
            "language": "en",
            "expected_route": None,
            "candidates": [{"route_id": "crossref.get_work", "score": 0.0}],
        },
    ]
    scores = score_selection_report(rows)
    assert scores["labeled_cases"] == 2
    assert scores["positive_top1_hits"] == 0
    assert scores["positive_top5_hits"] == 1
    assert scores["offtopic_cases"] == 1
    assert scores["offtopic_abstentions"] == 1
    assert scores["zero_score_exposed_cases"] == 2


def test_offline_real_registry_retrieval_is_unhinted_and_does_not_execute(monkeypatch) -> None:
    from scripts.research_public_heterogeneous_selection_e1 import (
        SourceQueryCase,
        evaluate_selection,
    )

    router, network_calls = _offline_registered_source_router()
    supplied_requests = []
    real_retrieve = router.retrieve_executable

    def observe(request, *, k: int = 5):
        supplied_requests.append(request)
        return real_retrieve(request, k=k)

    monkeypatch.setattr(router, "retrieve_executable", observe)
    case = SourceQueryCase(
        id="crossref_doi_en",
        language="en",
        query="Find one Crossref work by DOI",
        expected_route="crossref.get_work",
        expected_fields=("message",),
    )
    negative = SourceQueryCase(
        id="negative",
        language="en",
        query="Rotate the deployment credentials",
        expected_route=None,
    )
    report = evaluate_selection(router, cases=(case, negative))
    assert report["evidence_tier"].endswith("NOT_E2")
    assert report["live_source_discovery"] is False
    assert report["evidence_tier"].startswith("E0_")
    assert len(report["rows"]) == 2
    assert len(supplied_requests) == 2
    assert supplied_requests[0].query == case.query
    assert supplied_requests[0].preferred_tools == []
    assert supplied_requests[0].concepts == []
    assert supplied_requests[0].arguments == {}
    assert report["rows"][0]["expected_route"] == case.expected_route
    assert network_calls == []
    asyncio.run(router.aclose())


def test_offline_zero_score_negative_abstains_without_calling_any_tool() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import (
        SourceQueryCase,
        evaluate_selection,
    )

    router, network_calls = _offline_registered_source_router()
    case = SourceQueryCase(
        id="negative_credential_change",
        language="en",
        query="Rotate the deployment credentials immediately",
        expected_route=None,
    )
    positive = SourceQueryCase(
        id="positive",
        language="en",
        query="Find a Crossref work by DOI",
        expected_route="crossref.get_work",
        expected_fields=("message",),
    )
    report = evaluate_selection(router, cases=(positive, case))
    row = report["rows"][1]
    assert row["positive_top1_route"] is None
    assert report["metrics"]["offtopic_abstentions"] == 1
    assert network_calls == []
    asyncio.run(router.aclose())


def test_case_suite_covers_three_native_sources_three_languages_and_negatives() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import CASES

    assert len(CASES) >= 12
    assert {c.language for c in CASES} == {"en", "ko", "ja"}
    assert len({c.id for c in CASES}) == len(CASES)
    assert {c.expected_route for c in CASES if c.expected_route} == {
        "crossref.get_work",
        "cod_public.search_structures",
        "deepwiki_public.read_wiki_structure",
    }
    assert len([c for c in CASES if c.expected_route is None]) >= 3


def test_source_cases_supply_real_lookup_inputs_without_oracle_provider_name() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import CASES

    for case in CASES:
        if case.expected_route == "crossref.get_work":
            assert "10.1038/nature12373" in case.query
            assert "crossref" not in case.query.lower()
        if case.expected_route == "deepwiki_public.read_wiki_structure":
            assert "modelcontextprotocol/servers" in case.query
            assert "deepwiki" not in case.query.lower()


def test_live_contract_provenance_distinguishes_builtin_from_remote_discovery() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import (
        live_source_contract_provenance,
    )

    provenance = live_source_contract_provenance()
    assert set(provenance) == {"crossref", "cod_public", "deepwiki_public"}
    assert provenance["crossref"]["contract_origin"] == "bundled_crossref_provider_profile"
    assert provenance["crossref"]["live_remote_schema_discovered"] is False
    assert provenance["cod_public"]["live_remote_schema_discovered"] is True
    assert provenance["deepwiki_public"]["live_remote_schema_discovered"] is True


@pytest.mark.parametrize(
    "wrong",
    [
        [
            {"id": "duplicate", "language": "en", "expected_route": None, "candidates": []},
            {"id": "duplicate", "language": "ko", "expected_route": None, "candidates": []},
        ],
        [
            {
                "id": "wrong",
                "language": "en",
                "expected_route": "crossref.get_work",
                "candidates": [{"route_id": "crossref.get_work", "score": float("nan")}],
            }
        ],
        [
            {
                "id": "wrong",
                "language": "en",
                "expected_route": "crossref.get_work",
                "candidates": [{"route_id": "crossref.get_work", "score": -1.0}],
            }
        ],
    ],
)
def test_scorer_rejects_duplicate_or_invalid_route_scores(wrong: list[dict]) -> None:
    from scripts.research_public_heterogeneous_selection_e1 import score_selection_report

    with pytest.raises(ValueError, match="case|score|route|duplicate"):
        score_selection_report(wrong)


def test_offtopic_native_planner_proposals_are_not_called_abstentions() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import score_selection_report

    rows = [
        {
            "id": "positive",
            "language": "en",
            "expected_route": "crossref.get_work",
            "candidates": [{"route_id": "crossref.get_work", "score": 2.0}],
            "planned_route": "crossref.get_work",
        },
        {
            "id": "negative",
            "language": "en",
            "expected_route": None,
            "candidates": [{"route_id": "cod_public.search_structures", "score": 0.0}],
            "planned_route": "cod_public.search_structures",
        },
    ]
    scores = score_selection_report(rows)
    assert scores["offtopic_abstentions"] == 1  # evaluator's >0 threshold
    assert scores["offtopic_native_plan_proposals"] == 1  # actual native plan still exists


def test_native_original_source_contracts_fail_closed_if_expected_fields_disappear() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import (
        CASES,
        validate_expected_source_contracts,
    )

    router, _ = _offline_registered_source_router()
    assert validate_expected_source_contracts(router, CASES) == 3
    router.registry.unregister("deepwiki_public")
    with pytest.raises(ValueError, match="source|contract|route|missing"):
        validate_expected_source_contracts(router, CASES)
    asyncio.run(router.aclose())


def test_plan_field_and_required_input_metrics_use_only_correct_native_route() -> None:
    from scripts.research_public_heterogeneous_selection_e1 import score_selection_report

    rows = [
        {
            "id": "correct",
            "language": "en",
            "expected_route": "crossref.get_work",
            "candidates": [{"route_id": "crossref.get_work", "score": 2.0}],
            "planned_route": "crossref.get_work",
            "required_expected_fields": ["message"],
            "planned_fields": ["message"],
            "missing_required_arguments": ["doi"],
        },
        {
            "id": "wrong",
            "language": "ko",
            "expected_route": "deepwiki_public.read_wiki_structure",
            "candidates": [{"route_id": "cod_public.search_structures", "score": 2.0}],
            "planned_route": "cod_public.search_structures",
            "required_expected_fields": ["result"],
            "planned_fields": ["result"],
            "missing_required_arguments": [],
        },
        {
            "id": "negative",
            "language": "ja",
            "expected_route": None,
            "candidates": [],
            "planned_route": None,
        },
    ]
    scores = score_selection_report(rows)
    assert scores["native_plan_exact_route_hits"] == 1
    assert scores["native_plan_expected_field_complete_hits"] == 1
    assert scores["native_plan_required_argument_gaps"] == 1


def test_live_cli_requires_explicit_optin_without_starting_network(monkeypatch) -> None:
    from scripts import research_public_heterogeneous_selection_e1 as selection

    monkeypatch.setattr(sys, "argv", ["research_public_heterogeneous_selection_e1"])

    def network_forbidden(*args, **kwargs):
        raise AssertionError("no opt-in must never start source discovery")

    monkeypatch.setattr(selection.asyncio, "run", network_forbidden)
    with pytest.raises(SystemExit) as error:
        selection.main()
    assert error.value.code == 2


def test_live_failure_redacts_upstream_exception_body(monkeypatch, capsys) -> None:
    from scripts import research_public_heterogeneous_selection_e1 as selection

    monkeypatch.setattr(sys, "argv", ["research_public_heterogeneous_selection_e1", "--live"])

    def failing_discovery(coroutine):
        coroutine.close()
        raise ValueError("sensitive external server response and authorization")

    monkeypatch.setattr(selection.asyncio, "run", failing_discovery)
    with pytest.raises(SystemExit) as error:
        selection.main()
    assert error.value.code == 1
    response = capsys.readouterr().out
    assert json.loads(response) == {"status": "failure", "error_type": "ValueError"}
    assert "sensitive" not in response
