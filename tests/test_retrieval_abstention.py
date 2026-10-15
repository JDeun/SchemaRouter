"""Prospective synthetic tests only; never tune on external DEV/OOD rows."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from schemarouter import (
    CapabilityRetrieval,
    EndpointSpec,
    FieldSpec,
    RetrievalAbstentionPolicy,
    SchemaRouter,
    ToolSpec,
    apply_retrieval_abstention,
)


def build_router() -> SchemaRouter:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="paper",
            description="Published paper retrieval",
            endpoints=[
                EndpointSpec(
                    name="search", description="Search papers", read_only=True
                ),
                EndpointSpec(name="get", description="Read paper", read_only=True),
            ],
        )
    )
    return router


def test_explicit_min_score_does_not_mutate_default_retrieval() -> None:
    router = build_router()
    retrieval = router.retrieve("search published papers", k=2)
    original_routes = [x.route_id for x in retrieval.candidates]
    top = retrieval.candidates[0].score

    rejected = apply_retrieval_abstention(
        retrieval, policy=RetrievalAbstentionPolicy(min_score=top + 1.0)
    )
    assert rejected.abstained
    assert rejected.reason == "below_min_score"
    assert rejected.candidates == []
    assert rejected.observed_top_score == top
    assert rejected.total_ranked == retrieval.total_ranked
    assert rejected.requested_k == retrieval.requested_k
    assert [x.route_id for x in retrieval.candidates] == original_routes

    accepted = apply_retrieval_abstention(
        retrieval, policy=RetrievalAbstentionPolicy(min_score=top - 1.0)
    )
    assert not accepted.abstained
    assert accepted.reason == "selected"
    assert [x.route_id for x in accepted.candidates] == original_routes
    again = router.retrieve("search published papers", k=2)
    assert [x.route_id for x in again.candidates] == original_routes


def test_margin_rejects_missing_runner_up_and_narrow_margin() -> None:
    router = build_router()
    one = router.retrieve("search papers", k=1)
    result = apply_retrieval_abstention(
        one, policy=RetrievalAbstentionPolicy(min_margin=0.1)
    )
    assert result.reason == "insufficient_margin_evidence"
    assert result.abstained

    two = router.retrieve("search papers", k=2)
    delta = two.candidates[0].score - two.candidates[1].score
    assert delta >= 0.0
    ambiguous = apply_retrieval_abstention(
        two, policy=RetrievalAbstentionPolicy(min_margin=delta + 1)
    )
    assert ambiguous.reason == "below_min_margin"
    assert ambiguous.abstained
    selected = apply_retrieval_abstention(
        two, policy=RetrievalAbstentionPolicy(min_margin=0)
    )
    assert selected.reason == "selected"
    assert selected.observed_margin == pytest.approx(delta)


def test_empty_catalog_abstains_without_exception() -> None:
    retrieval = CapabilityRetrieval(
        query="nonexistent capability", registry_version=0,
        requested_k=3, total_ranked=0, candidates=[],
    )
    result = apply_retrieval_abstention(
        retrieval, policy=RetrievalAbstentionPolicy(min_score=0)
    )
    assert result.abstained
    assert result.reason == "empty_catalog"
    assert result.candidates == []
    assert result.observed_top_score is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_candidate_score_fails_closed(value: float) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    poisoned = retrieval.model_copy(
        update={"candidates": [
            retrieval.candidates[0].model_copy(update={"score": value}),
            retrieval.candidates[1],
        ]}
    )
    result = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-10000)
    )
    assert result.reason == "untrusted_ranking"
    assert result.candidates == []


def test_untrusted_rank_order_and_duplicates_fail_closed() -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    for candidates in (
        [retrieval.candidates[1], retrieval.candidates[0]],
        [retrieval.candidates[0], retrieval.candidates[0]],
    ):
        poisoned = retrieval.model_copy(update={"candidates": candidates})
        decision = apply_retrieval_abstention(
            poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
        )
        assert decision.reason == "untrusted_ranking"


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"min_score": float("nan")},
        {"min_score": math.inf},
        {"min_score": -math.inf},
        {"min_margin": float("nan")},
        {"min_margin": float("inf")},
        {"min_margin": -0.01},
        {"min_score": True},
        {"min_margin": "1.0"},
    ],
)
def test_unconfigured_or_unsafe_thresholds_rejected(kwargs: dict) -> None:
    with pytest.raises((ValidationError, ValueError)):
        RetrievalAbstentionPolicy(**kwargs)


def test_not_authorization_and_no_new_candidates() -> None:
    router = build_router()
    retrieval = router.retrieve("search papers", k=1)
    accepted = apply_retrieval_abstention(
        retrieval, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert {x.route_id for x in accepted.candidates} <= {
        x.route_id for x in retrieval.candidates
    }
    assert accepted.registry_version == retrieval.registry_version


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("route_id", "paper.different"),
        ("tool", "impostor"),
        ("endpoint", "different"),
        ("tool_fingerprint", ""),
        ("endpoint_fingerprint", ""),
        ("tool_fingerprint", None),
    ],
)
def test_corrupted_provenance_fails_closed(field: str, value: object) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    forged = retrieval.candidates[0].model_copy(update={field: value})
    poisoned = retrieval.model_copy(
        update={"candidates": [forged, retrieval.candidates[1]]}
    )
    result = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert result.abstained
    assert result.reason == "untrusted_ranking"
    assert result.candidates == []
    assert retrieval.candidates[0].route_id.startswith("paper.")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_ranked", 1),
        ("requested_k", 1),
        ("registry_version", -1),
    ],
)
def test_inconsistent_retrieval_envelope_fails_closed(
    field: str, value: int
) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    poisoned = retrieval.model_copy(update={field: value})
    result = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert result.abstained
    assert result.reason == "untrusted_ranking"
    assert result.candidates == []


def test_finite_scores_with_overflowing_margin_fail_closed() -> None:
    """A nonfinite computed margin is not evidence of separation."""
    retrieval = build_router().retrieve("search papers", k=2)
    forged = retrieval.model_copy(update={
        "candidates": [
            retrieval.candidates[0].model_copy(update={"score": 1e308}),
            retrieval.candidates[1].model_copy(update={"score": -1e308}),
        ],
    })
    decision = apply_retrieval_abstention(
        forged,
        policy=RetrievalAbstentionPolicy(min_score=0, min_margin=1),
    )
    assert decision.abstained
    assert decision.reason == "untrusted_ranking"
    assert decision.candidates == []
    assert decision.observed_margin is None
    assert retrieval.candidates[0].score != 1e308


@pytest.mark.parametrize(("field", "value"), [
    ("registry_version", True),
    ("registry_version", False),
    ("requested_k", True),
    ("total_ranked", True),
    ("executable_only", 1),
])
def test_boolean_or_forged_retrieval_metadata_fail_closed(
    field: str, value: object,
) -> None:
    retrieval = build_router().retrieve("search papers", k=1)
    poisoned = retrieval.model_copy(update={field: value})
    decision = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert decision.abstained
    assert decision.reason == "untrusted_ranking"
    assert decision.candidates == []
    # Forged Pydantic envelopes must not be silently re-authorized by
    # bool/int coercion when constructing the fail-closed response.
    assert type(decision.registry_version) is int
    assert type(decision.requested_k) is int
    assert type(decision.total_ranked) is int
    assert type(decision.executable_only) is bool
    if field == "executable_only":
        assert decision.executable_only is False
    assert getattr(poisoned, field) == value


def test_boolean_rank_does_not_pass_numeric_rank_identity() -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    poisoned = retrieval.model_copy(update={
        "candidates": [
            retrieval.candidates[0].model_copy(update={"rank": True}),
            retrieval.candidates[1],
        ],
    })
    decision = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert decision.abstained
    assert decision.reason == "untrusted_ranking"
    assert decision.candidates == []


def test_ordinary_finite_rankings_unchanged_after_overflow_guard() -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    decision = apply_retrieval_abstention(
        retrieval,
        policy=RetrievalAbstentionPolicy(min_score=-1e8, min_margin=0),
    )
    assert not decision.abstained
    assert decision.reason == "selected"
    assert decision.observed_margin is not None
    assert math.isfinite(decision.observed_margin)
    assert [c.route_id for c in decision.candidates] == [
        c.route_id for c in retrieval.candidates
    ]


@pytest.mark.parametrize(
    "poison",
    [
        {"min_score": float("nan")},
        {"min_score": float("inf")},
        {"min_score": True},
        {"min_score": "0.3"},
        {"min_margin": -1.0},
        {"min_score": None, "min_margin": None},
    ],
)
def test_public_abstention_revalidates_forged_policy(poison: dict) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    original = [x.route_id for x in retrieval.candidates]
    forged = RetrievalAbstentionPolicy(min_score=-1e8).model_copy(update=poison)
    with pytest.raises((ValidationError, ValueError)):
        apply_retrieval_abstention(retrieval, policy=forged)
    assert [x.route_id for x in retrieval.candidates] == original


def test_validated_public_policy_retains_ranked_selection_behavior() -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    decision = apply_retrieval_abstention(
        retrieval, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert decision.disposition == "selected"
    assert [x.route_id for x in decision.candidates] == [
        x.route_id for x in retrieval.candidates
    ]


@pytest.mark.parametrize(
    "forged",
    [
        None,
        "not-a-list",
        [None],
        [{"score": 1000.0, "route_id": "fake.tool"}],
        [123],
    ],
)
def test_malformed_candidate_containers_fail_closed_without_attribute_errors(
    forged: object,
) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    original = [candidate.route_id for candidate in retrieval.candidates]
    poisoned = retrieval.model_copy(update={"candidates": forged})
    decision = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert decision.abstained
    assert decision.reason == "untrusted_ranking"
    assert decision.candidates == []
    assert [candidate.route_id for candidate in retrieval.candidates] == original


@pytest.mark.parametrize("field", ["route_id", "tool", "endpoint"])
def test_unhashable_candidate_identity_fails_closed(field: str) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    forged = retrieval.candidates[0].model_copy(update={field: ["fake"]})
    poisoned = retrieval.model_copy(
        update={"candidates": [forged, retrieval.candidates[1]]}
    )
    decision = apply_retrieval_abstention(
        poisoned, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert decision.abstained
    assert decision.reason == "untrusted_ranking"
    assert decision.candidates == []


@pytest.mark.parametrize(
    "corrupt_fields",
    [
        None,
        "counterfeit_fields",
        [None],
        [{"name": "secrets"}],
        [FieldSpec(name="published").model_copy(update={"name": ["bad"]})],
    ],
)
def test_forged_candidate_field_contracts_are_untrusted_ranking(
    corrupt_fields: object,
) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    original = [candidate.route_id for candidate in retrieval.candidates]
    candidate = retrieval.candidates[0].model_copy(
        update={"output_fields": corrupt_fields}
    )
    poisoned = retrieval.model_copy(
        update={"candidates": [candidate, *retrieval.candidates[1:]]}
    )
    result = apply_retrieval_abstention(
        poisoned,
        policy=RetrievalAbstentionPolicy(min_score=-1e8),
    )
    assert result.abstained
    assert result.reason == "untrusted_ranking"
    assert result.candidates == []
    assert [candidate.route_id for candidate in retrieval.candidates] == original


@pytest.mark.parametrize(
    "forgery",
    [
        {"input_schema": ["injected"]},
        {"parameters": {"required": "secret"}},
        {"score_components": [None]},
        {"matched_fields": "string-not-list"},
        {"selection_source": "unreviewed_external"},
        {"read_only": "yes"},
        {"destructive": "no"},
        {"output_fields": [
            FieldSpec(name="count").model_copy(
                update={"json_schema": ["bad-schema"]}
            )
        ]},
    ],
)
def test_nested_candidate_forgery_cannot_be_reauthorized(
    forgery: dict[str, object],
) -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    original = [candidate.route_id for candidate in retrieval.candidates]
    forged = retrieval.candidates[0].model_copy(update=forgery)
    compromised = retrieval.model_copy(update={
        "candidates": [forged, *retrieval.candidates[1:]]
    })
    result = apply_retrieval_abstention(
        compromised, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert result.abstained
    assert result.reason == "untrusted_ranking"
    assert result.candidates == []
    assert [candidate.route_id for candidate in retrieval.candidates] == original


def test_valid_nested_candidate_metadata_remains_selectable() -> None:
    retrieval = build_router().retrieve("search papers", k=2)
    selected = apply_retrieval_abstention(
        retrieval, policy=RetrievalAbstentionPolicy(min_score=-1e8)
    )
    assert not selected.abstained
    assert [x.route_id for x in selected.candidates] == [
        x.route_id for x in retrieval.candidates
    ]
