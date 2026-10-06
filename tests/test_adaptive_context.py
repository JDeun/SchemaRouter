from __future__ import annotations

import json

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

    assert history.count("materials", "search") == 1
    assert history.count("papers", "lookup") == 1
    assert SuccessfulCapabilityHistory.loads(history.dumps()).snapshot() == history.snapshot()


def test_adaptive_checkpoints_emit_v1_envelopes_and_read_legacy_state() -> None:
    history = SuccessfulCapabilityHistory()
    history.record_success("materials", "search")
    history_payload = json.loads(history.dumps())
    assert history_payload == {
        "schema_version": 1,
        "counts": {"materials.search": 1},
    }
    assert SuccessfulCapabilityHistory.loads(
        '{"materials.search":7}'
    ).snapshot() == {"materials.search": 1}

    exposure = SessionSchemaExposure()
    exposure.mark_exposed("materials", "search")
    exposure_payload = json.loads(exposure.dumps())
    assert exposure_payload == {
        "schema_version": 1,
        "compaction_epoch": 0,
        "exposed_routes": ["materials.search"],
    }
    assert SessionSchemaExposure.loads(
        '{"compaction_epoch":0,"exposed_routes":["materials.search"]}'
    ).snapshot() == exposure.snapshot()


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":2,"counts":{}}',
        '{"schema_version":1,"counts":{},"extra":true}',
    ],
)
def test_success_history_rejects_malformed_checkpoint_versions(payload: str) -> None:
    with pytest.raises(ValueError):
        SuccessfulCapabilityHistory.loads(payload)


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":2,"compaction_epoch":0,"exposed_routes":[]}',
        '{"schema_version":1,"compaction_epoch":0,"exposed_routes":[],"extra":true}',
    ],
)
def test_session_exposure_rejects_malformed_checkpoint_versions(payload: str) -> None:
    with pytest.raises(ValueError):
        SessionSchemaExposure.loads(payload)


def test_adaptive_checkpoint_restore_rejects_oversized_payload_before_decode() -> None:
    payload = " " * (1024 * 1024 + 1)

    with pytest.raises(ValueError, match="restore limits"):
        SuccessfulCapabilityHistory.loads(payload)
    with pytest.raises(ValueError, match="restore limits"):
        SessionSchemaExposure.loads(payload)


def test_success_history_restore_rejects_oversized_route_key_and_count() -> None:
    long_route = "tool." + ("x" * 508)
    with pytest.raises(ValueError, match="route id exceeds"):
        SuccessfulCapabilityHistory.loads(
            json.dumps({"schema_version": 1, "counts": {long_route: 1}})
        )

    with pytest.raises(ValueError, match="history count exceeds"):
        SuccessfulCapabilityHistory.loads(
            '{"schema_version":1,"counts":{"tool.run":2147483648}}'
        )


def test_session_exposure_restore_rejects_oversized_route_key_and_epoch() -> None:
    long_route = "tool." + ("x" * 508)
    with pytest.raises(ValueError, match="route id exceeds"):
        SessionSchemaExposure.loads(
            json.dumps(
                {
                    "schema_version": 1,
                    "compaction_epoch": 0,
                    "exposed_routes": [long_route],
                }
            )
        )

    with pytest.raises(ValueError, match="compaction_epoch exceeds"):
        SessionSchemaExposure.loads(
            '{"schema_version":1,"compaction_epoch":2147483648,"exposed_routes":[]}'
        )


def test_adaptive_checkpoint_restore_rejects_route_cardinality_over_budget() -> None:
    history_routes = {
        f"tool.route_{index}": 1
        for index in range(10_001)
    }
    with pytest.raises(ValueError, match="restore limits"):
        SuccessfulCapabilityHistory.loads(
            json.dumps(
                {
                    "schema_version": 1,
                    "counts": history_routes,
                },
                separators=(",", ":"),
            )
        )

    exposure_routes = [
        f"tool.route_{index}"
        for index in range(10_001)
    ]
    with pytest.raises(ValueError, match="restore limits"):
        SessionSchemaExposure.loads(
            json.dumps(
                {
                    "schema_version": 1,
                    "compaction_epoch": 0,
                    "exposed_routes": exposure_routes,
                },
                separators=(",", ":"),
            )
        )


def test_session_exposure_runtime_compaction_respects_checkpoint_epoch_range() -> None:
    state = SessionSchemaExposure(compaction_epoch=2_147_483_647)
    with pytest.raises(ValueError, match="compaction_epoch exceeds"):
        state.compacted()


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



def test_history_fingerprint_prevents_schema_drift_prior_reuse() -> None:
    history = SuccessfulCapabilityHistory()
    history.record_success(
        "weather",
        "current",
        endpoint_fingerprint="endpoint-v1",
    )
    assert (
        history.count(
            "weather",
            "current",
            endpoint_fingerprint="endpoint-v1",
        )
        == 1
    )
    assert (
        history.count(
            "weather",
            "current",
            endpoint_fingerprint="endpoint-v2",
        )
        == 0
    )


def test_exposure_fingerprint_reinjects_changed_schema() -> None:
    exposure = SessionSchemaExposure()
    exposure.mark_exposed(
        "weather",
        "current",
        endpoint_fingerprint="endpoint-v1",
    )
    assert not exposure.decision(
        "weather",
        "current",
        endpoint_fingerprint="endpoint-v1",
    ).inject
    assert exposure.decision(
        "weather",
        "current",
        endpoint_fingerprint="endpoint-v2",
    ).inject


def test_state_digests_are_deterministic_and_change_with_state() -> None:
    history = SuccessfulCapabilityHistory()
    exposure = SessionSchemaExposure()
    history_empty = history.digest()
    exposure_empty = exposure.digest()

    history.record_success("weather", "current")
    exposure.mark_exposed("weather", "current")

    assert history.digest() != history_empty
    assert exposure.digest() != exposure_empty
    assert SuccessfulCapabilityHistory.loads(history.dumps()).digest() == history.digest()
    assert SessionSchemaExposure.loads(exposure.dumps()).digest() == exposure.digest()


@pytest.mark.parametrize("persisted_count", [1, 10, 1_000, 1_000_000_000])
def test_success_prior_is_bounded_for_large_history_counts(
    persisted_count: int,
) -> None:
    # _candidate("tool_b.run") uses endpoint_fingerprint="run-fp". Load a
    # matching legacy/checkpoint count so this test exercises the prior rather
    # than silently missing because of fingerprint drift.
    history = SuccessfulCapabilityHistory.loads(
        f'{{"tool_b.run@run-fp":{persisted_count}}}'
    )
    retrieval = CapabilityRetrieval(
        query="bounded prior",
        registry_version=1,
        requested_k=2,
        total_ranked=2,
        candidates=[
            _candidate(1, "tool_a.run", 0.75),
            _candidate(2, "tool_b.run", 0.0),
        ],
    )

    # Persisted counts are normalized to the bounded success signal.
    assert history.count(
        "tool_b",
        "run",
        endpoint_fingerprint="run-fp",
    ) == 1

    # With weight=1 the bounded +1 prior must be present; if matching history
    # were ignored, tool_b would remain second.
    reranked = apply_success_prior(retrieval, history, weight=1.0)
    assert [candidate.route_id for candidate in reranked.candidates] == [
        "tool_b.run",
        "tool_a.run",
    ]

    # At weight=0.5 the maximum allowed bonus is +0.5, which is insufficient
    # to pass tool_a's 0.75 base score. Any count-amplified/unbounded prior
    # would eventually violate this assertion for the larger cases above.
    bounded = apply_success_prior(retrieval, history, weight=0.5)
    assert [candidate.route_id for candidate in bounded.candidates] == [
        "tool_a.run",
        "tool_b.run",
    ]



def test_success_history_retains_only_latest_fingerprint_per_route() -> None:
    history = SuccessfulCapabilityHistory()
    for generation in range(100):
        history.record_success(
            "weather",
            "current",
            endpoint_fingerprint=f"fp-{generation:03d}",
        )

    snapshot = history.snapshot()
    assert snapshot == {"weather.current@fp-099": 1}
    assert history.count("weather", "current", endpoint_fingerprint="fp-099") == 1
    assert history.count("weather", "current", endpoint_fingerprint="fp-098") == 0


def test_schema_exposure_retains_only_latest_fingerprint_per_route() -> None:
    exposure = SessionSchemaExposure()
    for generation in range(100):
        exposure.mark_exposed(
            "weather",
            "current",
            endpoint_fingerprint=f"fp-{generation:03d}",
        )

    assert exposure.snapshot()["exposed_routes"] == ["weather.current@fp-099"]
    assert not exposure.decision(
        "weather", "current", endpoint_fingerprint="fp-099"
    ).inject
    assert exposure.decision(
        "weather", "current", endpoint_fingerprint="fp-098"
    ).inject


def test_legacy_multi_fingerprint_checkpoints_compact_deterministically() -> None:
    history_payload = (
        '{"weather.current@fp-003":7,"weather.current@fp-001":3,'
        '"weather.current@fp-002":5,"legacy.route":4}'
    )
    history = SuccessfulCapabilityHistory.loads(history_payload)
    assert history.snapshot() == {
        "legacy.route": 1,
        "weather.current@fp-003": 1,
    }
    assert SuccessfulCapabilityHistory.loads(history.dumps()).digest() == history.digest()

    exposure = SessionSchemaExposure.loads(
        '{"compaction_epoch":2,"exposed_routes":['
        '"weather.current@fp-002","weather.current@fp-001","weather.current@fp-003",'
        '"legacy.route"]}'
    )
    assert exposure.snapshot() == {
        "compaction_epoch": 2,
        "exposed_routes": ["legacy.route", "weather.current@fp-003"],
    }
    assert SessionSchemaExposure.loads(exposure.dumps()).digest() == exposure.digest()


def test_adaptive_route_forget_removes_legacy_and_fingerprinted_state() -> None:
    history = SuccessfulCapabilityHistory()
    exposure = SessionSchemaExposure()
    history.record_success("weather", "current")
    history.record_success("weather", "current", endpoint_fingerprint="fp-current")
    exposure.mark_exposed("weather", "current")
    exposure.mark_exposed("weather", "current", endpoint_fingerprint="fp-current")

    history.forget("weather", "current")
    exposure.forget("weather", "current")

    assert history.snapshot() == {}
    assert exposure.snapshot()["exposed_routes"] == []
