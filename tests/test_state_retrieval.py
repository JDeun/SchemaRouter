from schemarouter.capability_contracts import CapabilityFieldContract, CapabilityPrecondition
from schemarouter.execution_state import ObservedStateField, TypedExecutionState
from schemarouter.models import CapabilityCandidate, CapabilityRetrieval
from schemarouter.state_retrieval import filter_retrieval_by_state


def _candidate(route_id: str, rank: int) -> CapabilityCandidate:
    return CapabilityCandidate(
        rank=rank,
        route_id=route_id,
        tool="tool",
        endpoint=route_id,
        score=10.0 - rank,
        tool_fingerprint="tool-fp",
        endpoint_fingerprint=f"{route_id}-fp",
    )


def _retrieval() -> CapabilityRetrieval:
    return CapabilityRetrieval(
        query="continue the task",
        registry_version=1,
        requested_k=3,
        total_ranked=3,
        candidates=[
            _candidate("needs-id", 1),
            _candidate("stateless", 2),
            _candidate("needs-token", 3),
        ],
    )


def test_state_filter_keeps_satisfied_and_stateless_candidates() -> None:
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(
                    semantic_id="resource_id",
                    json_schema={"type": "string"},
                )
            )
        ]
    )
    requirements = {
        "needs-id": [CapabilityFieldContract(
            semantic_id="resource_id",
            json_schema={"type": "string"},
        )],
        "needs-token": [CapabilityFieldContract(
            semantic_id="continuation_token",
            json_schema={"type": "string"},
        )],
    }

    result = filter_retrieval_by_state(_retrieval(), state, requirements_by_route=requirements)

    assert [item.candidate.route_id for item in result.candidates] == [
        "needs-id",
        "stateless",
    ]
    assert [item.candidate.rank for item in result.candidates] == [1, 2]


def test_incompatible_typed_state_fails_closed() -> None:
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(
                    semantic_id="resource_id",
                    json_schema={"type": "integer"},
                )
            )
        ]
    )

    result = filter_retrieval_by_state(
        _retrieval(),
        state,
        requirements_by_route={
            "needs-id": [CapabilityFieldContract(
                semantic_id="resource_id",
                json_schema={"type": "string"},
            )],
            "stateless": [],
            "needs-token": [],
        },
    )

    assert [item.candidate.route_id for item in result.candidates] == [
        "stateless",
        "needs-token",
    ]


def test_missing_requirement_metadata_does_not_infer_workflow_state() -> None:
    result = filter_retrieval_by_state(_retrieval(), TypedExecutionState())

    assert [item.candidate.route_id for item in result.candidates] == [
        "needs-id",
        "stateless",
        "needs-token",
    ]


def test_state_filter_is_data_only_and_has_no_execution_surface() -> None:
    result = filter_retrieval_by_state(_retrieval(), TypedExecutionState())

    assert not hasattr(result, "execute")
    assert not hasattr(result, "commit")
    assert not hasattr(result, "rollback")
    assert not hasattr(result, "retry")
    assert not hasattr(result, "compensate")


def test_state_filter_applies_explicit_preconditions() -> None:
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(semantic_id="auth.scope"),
                stable_identifier="materials.read",
            )
        ]
    )
    result = filter_retrieval_by_state(
        _retrieval(),
        state,
        preconditions_by_route={
            "needs-id": [CapabilityPrecondition(
                semantic_id="auth.scope",
                operator="contains",
                value="materials.write",
            )]
        },
    )

    assert [item.candidate.route_id for item in result.candidates] == [
        "stateless",
        "needs-token",
    ]


def test_state_aware_retrieval_surface_has_no_execution_authority() -> None:
    result = filter_retrieval_by_state(
        CapabilityRetrieval(
            query="read",
            registry_version=1,
            requested_k=1,
            total_ranked=1,
            candidates=[_candidate("read", 1)],
        ),
        TypedExecutionState(),
    )

    forbidden_verbs = {
        "execute", "invoke", "commit", "rollback", "retry", "compensate",
        "plan", "schedule", "authorize",
    }
    assert forbidden_verbs.isdisjoint(dir(result))
    assert forbidden_verbs.isdisjoint(dir(result.candidates[0]))
