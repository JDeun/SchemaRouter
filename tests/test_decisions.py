import math

import pytest
from pydantic import ValidationError

from schemarouter import (
    CallableDecisionBackend,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    FirstOptionDecisionBackend,
    PlanningError,
    choose_async,
    choose_sync,
)


def request() -> DecisionRequest:
    return DecisionRequest(
        query="choose an endpoint",
        options=[
            DecisionOption(id="endpoint:0", label="search"),
            DecisionOption(id="endpoint:1", label="get"),
        ],
    )


def test_reference_backend_selects_only_offered_option() -> None:
    result = choose_sync(FirstOptionDecisionBackend(), request())
    assert result.selections == [DecisionSelection(option_id="endpoint:0", score=1.0)]


def test_unknown_option_fails_closed() -> None:
    backend = CallableDecisionBackend(
        lambda _: {"selections": [{"option_id": "endpoint:evil", "score": 1.0}]}
    )
    with pytest.raises(PlanningError, match="unknown option"):
        choose_sync(backend, request())


def test_duplicate_options_and_duplicate_selections_are_rejected() -> None:
    with pytest.raises(ValidationError, match="unique"):
        DecisionRequest(
            query="x",
            options=[DecisionOption(id="x"), DecisionOption(id="x")],
        )

    backend = CallableDecisionBackend(
        lambda _: {
            "selections": [
                {"option_id": "endpoint:0"},
                {"option_id": "endpoint:0"},
            ]
        }
    )
    with pytest.raises(PlanningError, match="duplicate"):
        choose_sync(backend, request())


def test_selection_count_is_bounded() -> None:
    backend = CallableDecisionBackend(
        lambda _: {
            "selections": [
                {"option_id": "endpoint:0"},
                {"option_id": "endpoint:1"},
            ]
        }
    )
    with pytest.raises(PlanningError, match="max_selections"):
        choose_sync(backend, request())


@pytest.mark.parametrize("score", [-0.1, 1.1, math.inf, -math.inf, math.nan])
def test_scores_must_be_bounded_and_finite(score: float) -> None:
    with pytest.raises(ValidationError):
        DecisionSelection(option_id="endpoint:0", score=score)


def test_abstention_cannot_smuggle_a_selection() -> None:
    with pytest.raises(ValidationError, match="abstaining"):
        DecisionResult(
            abstained=True,
            selections=[DecisionSelection(option_id="endpoint:0")],
        )


def test_extra_backend_fields_are_rejected() -> None:
    backend = CallableDecisionBackend(
        lambda _: {
            "selections": [{"option_id": "endpoint:0"}],
            "grant_execution": True,
        }
    )
    with pytest.raises(ValidationError):
        choose_sync(backend, request())


def test_async_backend_works_only_through_async_path() -> None:
    async def decide(_: DecisionRequest) -> dict[str, object]:
        return {"selections": [{"option_id": "endpoint:1", "score": 0.8}]}

    backend = CallableDecisionBackend(decide)
    with pytest.raises(PlanningError, match="asynchronous"):
        choose_sync(backend, request())


@pytest.mark.asyncio
async def test_async_backend_is_validated() -> None:
    async def decide(_: DecisionRequest) -> dict[str, object]:
        return {"selections": [{"option_id": "endpoint:1", "score": 0.8}]}

    result = await choose_async(CallableDecisionBackend(decide), request())
    assert result.selections[0].option_id == "endpoint:1"


@pytest.mark.parametrize(
    "forgery",
    [
        {"query": ["bad"]},
        {"query": ""},
        {"query": "   "},
        {"options": None},
        {"options": ["untrusted"]},
        {"options": [DecisionOption(id="endpoint:0").model_copy(
            update={"id": ["bad"]}
        )]},
        {"options": [DecisionOption(id="endpoint:0"), DecisionOption(id="endpoint:0")]},
        {"max_selections": True},
        {"max_selections": 0},
        {"context": ["bad"]},
    ],
)
def test_sync_choice_rejects_unvalidated_request_before_backend_invocation(
    forgery: dict[str, object],
) -> None:
    calls: list[DecisionRequest] = []
    backend = CallableDecisionBackend(
        lambda value: calls.append(value) or {"selections": []}
    )
    compromised = request().model_copy(update=forgery)
    with pytest.raises(PlanningError, match="decision request"):
        choose_sync(backend, compromised)
    assert calls == []


@pytest.mark.asyncio
async def test_async_choice_rejects_forged_request_before_backend_invocation() -> None:
    calls: list[DecisionRequest] = []

    async def decide(value: DecisionRequest) -> dict:
        calls.append(value)
        return {"selections": []}

    compromised = request().model_copy(
        update={"options": [DecisionOption(id="endpoint:0").model_copy(
            update={"id": ["bad"]}
        )]}
    )
    with pytest.raises(PlanningError, match="decision request"):
        await choose_async(CallableDecisionBackend(decide), compromised)
    assert calls == []


def test_choice_validated_snapshot_does_not_mutate_original_request() -> None:
    original = request()
    captured: list[DecisionRequest] = []
    result = choose_sync(
        CallableDecisionBackend(
            lambda value: captured.append(value)
            or {"selections": [{"option_id": "endpoint:0"}]}
        ),
        original,
    )
    assert result.selections[0].option_id == "endpoint:0"
    assert captured and captured[0] is not original
    assert captured[0].options[0] is not original.options[0]
    assert [option.id for option in original.options] == ["endpoint:0", "endpoint:1"]
