from __future__ import annotations

import pytest

from schemarouter import (
    DecisionEvidence,
    DecisionOption,
    DecisionRequest,
    EvidenceProjector,
    EvidenceRequirement,
    PlanningError,
)


def request(*, max_selections: int = 1) -> DecisionRequest:
    return DecisionRequest(
        query="route this request",
        options=[
            DecisionOption(id="tool.a", label="tool.a"),
            DecisionOption(id="tool.b", label="tool.b"),
        ],
        max_selections=max_selections,
    )


def test_projector_requires_all_score_kinds_without_averaging() -> None:
    projector = EvidenceProjector(
        [
            EvidenceRequirement(
                kind="tool_domain",
                score_kind="cosine_similarity",
                min_score=0.60,
            ),
            EvidenceRequirement(
                kind="operation_fit",
                score_kind="pairwise_probability",
                min_score=0.70,
            ),
        ]
    )
    evidence = [
        DecisionEvidence(
            kind="tool_domain",
            state="match",
            source="embedding",
            option_id="tool.a",
            score=0.90,
            score_kind="cosine_similarity",
        ),
        DecisionEvidence(
            kind="operation_fit",
            state="match",
            source="reranker",
            option_id="tool.a",
            score=0.65,
            score_kind="pairwise_probability",
        ),
        DecisionEvidence(
            kind="tool_domain",
            state="match",
            source="embedding",
            option_id="tool.b",
            score=0.61,
            score_kind="cosine_similarity",
        ),
        DecisionEvidence(
            kind="operation_fit",
            state="match",
            source="reranker",
            option_id="tool.b",
            score=0.85,
            score_kind="pairwise_probability",
        ),
    ]

    result = projector.project(request(), evidence)

    assert result.abstained is False
    assert [item.option_id for item in result.selections] == ["tool.b"]
    assert result.metadata["per_option"]["tool.a"]["state"] == "reject"
    assert result.metadata["per_option"]["tool.b"]["state"] == "accept"


def test_missing_required_evidence_remains_unknown_not_zero() -> None:
    projector = EvidenceProjector(
        [
            EvidenceRequirement(
                kind="operation_fit",
                score_kind="pairwise_probability",
                min_score=0.50,
            )
        ]
    )

    result = projector.project(
        request(),
        [
            DecisionEvidence(
                kind="operation_fit",
                state="match",
                source="reranker",
                option_id="tool.a",
                score=0.75,
                score_kind="different_score_kind",
            )
        ],
    )

    assert result.abstained is True
    assert result.metadata["reason"] == "evidence_unknown"
    assert result.metadata["per_option"]["tool.a"]["state"] == "unknown"
    assert (
        result.metadata["per_option"]["tool.a"]["requirements"][0]["reason"]
        == "missing_evidence"
    )


def test_unknown_policy_can_fail_closed_to_reject() -> None:
    projector = EvidenceProjector(
        [
            EvidenceRequirement(
                kind="negative_capability",
                source="boundary-check",
                on_unknown="reject",
            )
        ]
    )
    evidence = [
        DecisionEvidence(
            kind="negative_capability",
            state="unknown",
            source="boundary-check",
            option_id="tool.a",
        ),
        DecisionEvidence(
            kind="negative_capability",
            state="unknown",
            source="boundary-check",
            option_id="tool.b",
        ),
    ]

    result = projector.project(request(), evidence)

    assert result.abstained is True
    assert result.metadata["reason"] == "evidence_rejected"
    assert result.metadata["per_option"]["tool.a"]["state"] == "reject"


def test_multiple_accepted_options_abstain_when_request_allows_one() -> None:
    projector = EvidenceProjector(
        [EvidenceRequirement(kind="schema_path")]
    )
    evidence = [
        DecisionEvidence(
            kind="schema_path",
            state="match",
            source="graph",
            option_id="tool.a",
        ),
        DecisionEvidence(
            kind="schema_path",
            state="match",
            source="graph",
            option_id="tool.b",
        ),
    ]

    result = projector.project(request(), evidence)

    assert result.abstained is True
    assert result.metadata["reason"] == "ambiguous_evidence_projection"
    assert result.metadata["accepted_option_ids"] == ["tool.a", "tool.b"]


def test_multiple_accepted_options_can_fill_bounded_multi_selection() -> None:
    projector = EvidenceProjector(
        [EvidenceRequirement(kind="schema_path")]
    )
    evidence = [
        DecisionEvidence(
            kind="schema_path",
            state="match",
            source="graph",
            option_id="tool.a",
        ),
        DecisionEvidence(
            kind="schema_path",
            state="match",
            source="graph",
            option_id="tool.b",
        ),
    ]

    result = projector.project(request(max_selections=2), evidence)

    assert result.abstained is False
    assert [item.option_id for item in result.selections] == ["tool.a", "tool.b"]


def test_duplicate_matching_observations_are_rejected_instead_of_aggregated() -> None:
    projector = EvidenceProjector(
        [
            EvidenceRequirement(
                kind="operation_fit",
                score_kind="pairwise_probability",
                min_score=0.50,
            )
        ]
    )
    evidence = [
        DecisionEvidence(
            kind="operation_fit",
            state="match",
            source="reranker-a",
            option_id="tool.a",
            score=0.8,
            score_kind="pairwise_probability",
        ),
        DecisionEvidence(
            kind="operation_fit",
            state="match",
            source="reranker-b",
            option_id="tool.a",
            score=0.9,
            score_kind="pairwise_probability",
        ),
    ]

    with pytest.raises(PlanningError, match="multiple observations"):
        projector.project(request(), evidence)


def test_projection_rejects_evidence_for_unoffered_option() -> None:
    projector = EvidenceProjector(
        [EvidenceRequirement(kind="schema_path")]
    )

    with pytest.raises(PlanningError, match="unknown option IDs"):
        projector.project(
            request(),
            [
                DecisionEvidence(
                    kind="schema_path",
                    state="match",
                    source="graph",
                    option_id="tool.outside",
                )
            ],
        )


def test_numeric_requirement_requires_declared_score_kind() -> None:
    with pytest.raises(ValueError, match="requires score_kind"):
        EvidenceRequirement(
            kind="operation_fit",
            min_score=0.5,
        )


def test_duplicate_requirement_selectors_are_rejected() -> None:
    requirement = EvidenceRequirement(kind="schema_path", source="graph")
    with pytest.raises(ValueError, match="duplicate"):
        EvidenceProjector([requirement, requirement])
