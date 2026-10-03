from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.execution_state import ObservedStateField, TypedExecutionState
from schemarouter.models import CapabilityCandidate, CapabilityRetrieval
from schemarouter.state_retrieval import filter_retrieval_by_state


def _candidate(route_id: str, rank: int, tool: str) -> CapabilityCandidate:
    return CapabilityCandidate(
        rank=rank,
        route_id=route_id,
        tool=tool,
        endpoint=route_id,
        score=10.0 - rank,
        tool_fingerprint=f"{tool}-fp",
        endpoint_fingerprint=f"{route_id}-fp",
    )


def _retrieval(candidates: list[CapabilityCandidate]) -> CapabilityRetrieval:
    return CapabilityRetrieval(
        query="continue with observed state",
        registry_version=1,
        requested_k=len(candidates),
        total_ranked=len(candidates),
        candidates=candidates,
    )


def test_scientific_rest_optimade_python_alternatives_share_typed_state() -> None:
    candidates = [
        _candidate("mp-rest-summary", 1, "materials-rest"),
        _candidate("mp-optimade-structures", 2, "materials-optimade"),
        _candidate("mp-python-summary", 3, "materials-python"),
    ]
    required = CapabilityFieldContract(
        semantic_id="resource.material_id",
        json_schema={"type": "string"},
    )
    state = TypedExecutionState(
        observed_fields=[ObservedStateField(contract=required, stable_identifier="mp-149")]
    )

    result = filter_retrieval_by_state(
        _retrieval(candidates),
        state,
        requirements_by_route={candidate.route_id: [required] for candidate in candidates},
    )

    assert [item.candidate.route_id for item in result.candidates] == [
        "mp-rest-summary",
        "mp-optimade-structures",
        "mp-python-summary",
    ]


def test_mcp_host_allowlist_remains_authoritative_before_state_filter() -> None:
    candidates = [
        _candidate("mcp-visible-read", 1, "mcp-server"),
    ]
    state = TypedExecutionState(
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(
                    semantic_id="resource.material_id",
                    json_schema={"type": "string"},
                )
            )
        ]
    )

    # The hidden route is deliberately absent from the host-authorized retrieval.
    result = filter_retrieval_by_state(_retrieval(candidates), state)

    assert [item.candidate.route_id for item in result.candidates] == ["mcp-visible-read"]
    assert all(item.candidate.route_id != "mcp-hidden-write" for item in result.candidates)


def test_multistep_observable_state_never_uses_future_route_or_rank_oracle() -> None:
    state = TypedExecutionState(
        completed_route_ids=("lookup-material",),
        observed_fields=[
            ObservedStateField(
                contract=CapabilityFieldContract(
                    semantic_id="resource.material_id",
                    json_schema={"type": "string"},
                ),
                stable_identifier="mp-149",
            )
        ],
        task_incomplete=True,
    )
    candidates = [
        _candidate("fetch-elasticity", 1, "materials"),
        _candidate("search-unrelated", 2, "search"),
    ]

    result = filter_retrieval_by_state(
        _retrieval(candidates),
        state,
        requirements_by_route={
            "fetch-elasticity": [
                CapabilityFieldContract(
                    semantic_id="resource.material_id",
                    json_schema={"type": "string"},
                )
            ],
            "search-unrelated": [
                CapabilityFieldContract(
                    semantic_id="future.answer",
                    json_schema={"type": "string"},
                )
            ],
        },
    )

    assert [item.candidate.route_id for item in result.candidates] == ["fetch-elasticity"]
