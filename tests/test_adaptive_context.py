from __future__ import annotations

import pytest

from schemarouter.adaptive_context import (
    SessionSchemaExposure,
    SuccessfulCapabilityHistory,
    apply_success_prior,
    filter_unexposed_schemas,
)
from schemarouter.models import CapabilityCandidate, CapabilityRetrieval


def test_success_history_records_only_explicit_successes_and_round_trips() -> None:
    history = SuccessfulCapabilityHistory()
    history.record_success("materials", "search")
    history.record_success("materials", "search")
    history.record_success("papers", "lookup")

    assert history.count("materials", "search") == 2
    assert history.count("papers", "lookup") == 1
    assert SuccessfulCapabilityHistory.loads(history.dumps()).snapshot() == history.snapshot()


def test_success_history_reset_is_deterministic() -> None:
    history = SuccessfulCapabilityHistory()
    history.record_success("materials", "search")
    history.reset()
    assert history.snapshot() == {}


def test_session_exposure_suppresses_duplicates_until_compaction() -> None:
    state = SessionSchemaExposure()

    first = state.decision("materials", "search")
    assert first.inject is True
    assert first.reason == "not_exposed"

    state.mark_exposed("materials", "search")
    duplicate = state.decision("materials", "search")
    assert duplicate.inject is False
    assert duplicate.reason == "already_exposed"

    state.compacted()
    assert state.compaction_epoch == 1
    reinject = state.decision("materials", "search")
    assert reinject.inject is True
    assert reinject.reason == "not_exposed"


def test_session_exposure_round_trip_preserves_epoch_and_routes() -> None:
    state = SessionSchemaExposure()
    state.mark_many_exposed([("materials", "search"), ("papers", "lookup")])
    state.compacted()
    state.mark_exposed("materials", "search")

    restored = SessionSchemaExposure.loads(state.dumps())
    assert restored.snapshot() == state.snapshot()


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '{"bad": 1}',
        '{"compaction_epoch": -1, "exposed_routes": []}',
        '{"compaction_epoch": 0, "exposed_routes": ["invalid"]}',
    ],
)
def test_session_exposure_rejects_invalid_serialized_state(payload: str) -> None:
    with pytest.raises(ValueError):
        SessionSchemaExposure.loads(payload)



def _candidate(rank: int, route: str, score: float) -> CapabilityCandidate:
    tool, endpoint = route.split(".", 1)
    return CapabilityCandidate(
        rank=rank,
        route_id=route,
        tool=tool,
        endpoint=endpoint,
        score=score,
        tool_fingerprint=f"{tool}-fp",
        endpoint_fingerprint=f"{endpoint}-fp",
    )


def _retrieval() -> CapabilityRetrieval:
    return CapabilityRetrieval(
        query="find material",
        registry_version=1,
        requested_k=2,
        total_ranked=2,
        candidates=[
            _candidate(1, "alpha.search", 10.0),
            _candidate(2, "beta.search", 9.5),
        ],
    )


def test_success_prior_is_opt_in_and_can_rerank_visible_candidates() -> None:
    retrieval = _retrieval()
    history = SuccessfulCapabilityHistory()
    history.record_success("beta", "search")

    assert apply_success_prior(retrieval, history).candidates == retrieval.candidates
    ranked = apply_success_prior(retrieval, history, weight=1.0)
    assert [candidate.route_id for candidate in ranked.candidates] == [
        "beta.search",
        "alpha.search",
    ]


def test_schema_exposure_filter_does_not_mutate_session_state() -> None:
    retrieval = _retrieval()
    exposure = SessionSchemaExposure()
    exposure.mark_exposed("alpha", "search")

    filtered = filter_unexposed_schemas(retrieval, exposure)
    assert [candidate.route_id for candidate in filtered.candidates] == ["beta.search"]
    assert exposure.decision("beta", "search").inject is True

    exposure.compacted()
    restored = filter_unexposed_schemas(retrieval, exposure)
    assert [candidate.route_id for candidate in restored.candidates] == [
        "alpha.search",
        "beta.search",
    ]
