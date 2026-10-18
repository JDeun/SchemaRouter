"""E0 paired candidate study reuses original agent and local fixture (NOT E2)."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from scripts.research_paired_native_concept_agent_e0 import (
    EVIDENCE,
    run_paired_concept_agent_e0,
)

PRINCIPAL = PrincipalContext(subject="scoped", roles=("analyst",))
REV = "a" * 40
QUERY = "문의 상태와 우선순위를 보여주세요"
TERM = "내일 날씨에 대해 질문"
CATALOG = NativeConceptCatalog(concepts=(
    NativeDeclaredConcept(
        concept_id="support.status", aliases=("case status", "문의 상태", "問い合わせ状態"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.status", json_schema={"type": "string"},
        ),),
        source_type="support", license="host-reviewed",
    ),
    NativeDeclaredConcept(
        concept_id="support.priority", aliases=("priority", "우선순위", "優先度"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.priority", json_schema={"type": "string"},
        ),),
        source_type="support", license="host-reviewed",
    ),
))


def _router(*, hide: bool = False) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("analyst",),
        ),),
        data_rules=(DataScopeRule(
            operation="zz_complete.read", roles_any=("analyst",),
            hidden_fields=("priority",),
        ),) if hide else (),
    ))
    # Positive lexical distractors precede a complete typed endpoint.
    for i in range(12):
        router.add_tool(ToolSpec(
            name=f"aa_{i:02d}", source_type="support", license="host-reviewed",
            endpoints=[EndpointSpec(
                name="read", description="Read case status and priority",
                read_only=True,
                output_fields=[FieldSpec(
                    name="status", semantic_id="support.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    router.add_tool(ToolSpec(
        name="zz_complete", source_type="support", license="host-reviewed",
        endpoints=[EndpointSpec(
            name="read", description="Read case status and priority",
            read_only=True,
            output_fields=[
                FieldSpec(name="status", semantic_id="support.status",
                          json_schema={"type": "string"}),
                FieldSpec(name="priority", semantic_id="support.priority",
                          json_schema={"type": "string"}),
            ],
        )],
    ))
    return router


def _task(query=QUERY, *, supported=True, language="ko"):
    return {
        "semantic_task_id": language + ("-s" if supported else "-n"),
        "query": query, "language": language, "supported": supported,
        "required_routes": ["zz_complete.read"] if supported else [],
        "executor_fixture": {"steps": [{
            "route_id": "zz_complete.read", "argument_rules": {},
            "observation": {"status": "ok", "priority": "high"},
        }] if supported else []},
    }


class FixedScriptedAgent:
    """Scripted behavior is deliberately NOT actual model decision evidence."""

    def __init__(self, *, no_call=False):
        self.calls = 0
        self.no_call = no_call

    def generate(self, messages, tools):
        del messages, tools
        if self.no_call:
            output = "REQUEST_MORE_TOOLS"
        else:
            output = (
                '<tool_call>{"name":"zz_complete__read","arguments":{}}</tool_call>'
                if self.calls == 0 else "Complete."
            )
        self.calls += 1
        return {
            "text": output, "input_tokens": 10, "tool_tokens": 3,
            "output_tokens": 2, "latency_ms": 0.0,
            "context_overflow": False,
        }


def _run(router, tasks, *, factory=FixedScriptedAgent, catalog=CATALOG):
    return run_paired_concept_agent_e0(
        router, catalog=catalog, principal=PRINCIPAL, tasks=tasks,
        agent_factory=factory, source_revision=REV,
    )


def test_same_query_catalog_principal_two_arms_and_sanitized_report():
    report = _run(_router(), (_task(),))
    assert report["evidence_tier"] == EVIDENCE
    assert report["independent_e2_qualified"] is False
    assert report["publication_gate_passed"] is False
    assert report["strict_k"] == 5
    assert report["paired_tasks"] == 1
    assert report["arms"] == ["lexical_k5", "declared_concepts_k5"]
    assert report["metrics"]["declared_concepts_k5"]["scripted_fixture_pass"] == 1
    assert report["metrics"]["declared_concepts_k5"]["supported_pass"] == 1
    assert report["metrics"]["declared_concepts_k5"]["mean_visible_candidate_count"] == 1
    for arm in report["arms"]:
        assert report["metrics"][arm]["cases"] == 1
        assert report["metrics"][arm]["mean_input_tokens"] >= 0
        assert report["metrics"][arm]["mean_tool_schema_tokens"] >= 0
    serialized = json.dumps(report, ensure_ascii=False)
    for canary in ("zz_complete", "문의 상태", "expected", "required_routes",
                   "arguments", "case status", "priority"):
        assert canary not in serialized
    assert "No independent publisher cohort" in " ".join(report["limitations"])


@pytest.mark.parametrize("query,language", (
    (QUERY, "ko"),
    ("Please check case status and priority", "en"),
    ("問い合わせ状態と優先度を教えて", "ja"),
))
def test_language_strata_are_reported_only_as_dev_without_promoting_model(query, language):
    report = _run(_router(), (_task(query, language=language),))
    assert report["languages"][language]["declared_concepts_k5"]["passed"] == 1
    assert sum(report["languages"][code]["declared_concepts_k5"]["tasks"]
               for code in ("en", "ko", "ja")) == 1
    assert report["evidence_tier"] == EVIDENCE


def test_unsupported_ood_remains_scripted_no_call_not_calibrated_unsupported():
    report = _run(
        _router(), (_task(TERM, supported=False),),
        factory=lambda: FixedScriptedAgent(no_call=True),
    )
    for arm in report["arms"]:
        assert report["metrics"][arm]["unsupported_tasks"] == 1
        assert report["metrics"][arm]["unsupported_no_call_pass"] == 1
    assert report["independent_e2_qualified"] is False


def test_hidden_field_cannot_become_concept_candidate_or_success():
    report = _run(_router(hide=True), (_task(),))
    assert report["metrics"]["declared_concepts_k5"]["mean_visible_candidate_count"] == 0
    assert report["metrics"]["declared_concepts_k5"]["supported_pass"] == 0


def test_duplicate_identity_invalid_source_or_too_many_cases_abort():
    router = _router()
    task = _task()
    with pytest.raises(ValueError, match="invalid paired E0 case identity"):
        _run(router, (task, task))
    with pytest.raises(ValueError, match="invalid bounded paired E0 case count"):
        _run(router, tuple(_task(language=f"t{i}") for i in range(25)))
    with pytest.raises(ValueError, match="invalid trusted paired experiment"):
        run_paired_concept_agent_e0(
            router, catalog=CATALOG, principal=PRINCIPAL,
            tasks=(task,), agent_factory=FixedScriptedAgent, source_revision="not-sha",
        )


def test_source_policy_mutation_in_agent_factory_never_passes_scoped_comparison():
    router = _router()
    def mutate_before_agent():
        router.add_tool(ToolSpec(name="attack", endpoints=[
            EndpointSpec(name="read", read_only=True),
        ]))
        return FixedScriptedAgent()
    with pytest.raises(PolicyViolationError):
        _run(router, (_task(),), factory=mutate_before_agent)


def test_trusted_catalog_change_is_not_reinterpreted_between_paired_arms():
    original = CATALOG.model_copy(deep=True)
    agents = 0
    def mutate_after_first_selection():
        nonlocal agents
        agents += 1
        if agents == 2:
            object.__setattr__(
                original.concepts[1], "aliases",
                ("different concept", "우선순위", "優先度"),
            )
        return FixedScriptedAgent()
    with pytest.raises(PolicyViolationError, match="catalog mutated"):
        _run(_router(), (_task(),), factory=mutate_after_first_selection, catalog=original)
