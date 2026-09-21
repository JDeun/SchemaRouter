import math
import sys
from types import ModuleType
from typing import Any

import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    PlanningError,
    choose_async,
    choose_sync,
)
from schemarouter.integrations import JevDecisionBackend


class FakeChoiceAnswer:
    def __init__(self, choice: str, confidence: float) -> None:
        self.choice = choice
        self.confidence = confidence


class FakeUsage:
    input_tokens = 12
    output_tokens = 3


class FakeResponse:
    def __init__(self, choice: str, confidence: float) -> None:
        self.choices = {"selection": FakeChoiceAnswer(choice, confidence)}
        self.model = "jev-test"
        self.usage = FakeUsage()


class FakeSyncClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def system_one(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class FakeAsyncClient(FakeSyncClient):
    async def system_one(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def request() -> DecisionRequest:
    return DecisionRequest(
        query="choose the best endpoint",
        options=[
            DecisionOption(
                id="candidate:0",
                label="materials.search",
                description="Search material properties",
                metadata={"private_note": "do-not-send"},
            ),
            DecisionOption(
                id="candidate:1",
                label="secondary.lookup",
                description="Lookup a cached property",
            ),
        ],
        context={"tenant": "example"},
    )


def test_jev_selects_only_from_bounded_options() -> None:
    client = FakeSyncClient(FakeResponse("candidate:1", 0.91))
    result = choose_sync(JevDecisionBackend(client=client), request())

    assert result.selections[0].option_id == "candidate:1"
    assert result.selections[0].score == 0.91
    assert result.metadata["provider"] == "typesafe-system-one"
    assert result.metadata["input_tokens"] == 12
    assert result.metadata["output_tokens"] == 3


def test_jev_payload_does_not_forward_option_metadata() -> None:
    client = FakeSyncClient(FakeResponse("candidate:0", 0.8))
    choose_sync(JevDecisionBackend(client=client), request())

    call = client.calls[0]
    assert call["state"] == {
        "query": "choose the best endpoint",
        "context": {"tenant": "example"},
    }
    assert "private_note" not in repr(call["questions"])
    assert "do-not-send" not in repr(call["questions"])


def test_jev_can_omit_request_context() -> None:
    client = FakeSyncClient(FakeResponse("candidate:0", 0.8))
    choose_sync(
        JevDecisionBackend(client=client, include_context=False),
        request(),
    )

    assert client.calls[0]["state"] == {"query": "choose the best endpoint"}


def test_jev_low_confidence_abstains() -> None:
    client = FakeSyncClient(FakeResponse("candidate:0", 0.49))
    result = choose_sync(
        JevDecisionBackend(client=client, min_confidence=0.5),
        request(),
    )

    assert result.abstained is True
    assert result.selections == []
    assert result.metadata["reason"] == "below_min_confidence"


def test_jev_unknown_choice_fails_closed() -> None:
    client = FakeSyncClient(FakeResponse("candidate:evil", 0.99))

    with pytest.raises(PlanningError, match="unknown option"):
        choose_sync(JevDecisionBackend(client=client), request())


def test_jev_unknown_choice_cannot_hide_behind_low_confidence() -> None:
    client = FakeSyncClient(FakeResponse("candidate:evil", 0.01))

    with pytest.raises(PlanningError, match="unknown option"):
        choose_sync(
            JevDecisionBackend(client=client, min_confidence=0.5),
            request(),
        )


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -0.1, 1.1])
def test_jev_rejects_invalid_confidence(confidence: float) -> None:
    client = FakeSyncClient(FakeResponse("candidate:0", confidence))

    with pytest.raises(PlanningError, match="confidence"):
        choose_sync(JevDecisionBackend(client=client), request())


def test_jev_rejects_malformed_response() -> None:
    client = FakeSyncClient(object())

    with pytest.raises(PlanningError, match="invalid choice response"):
        choose_sync(JevDecisionBackend(client=client), request())


@pytest.mark.asyncio
async def test_jev_async_backend_uses_async_client() -> None:
    client = FakeAsyncClient(FakeResponse("candidate:1", 0.77))
    result = await choose_async(
        JevDecisionBackend(client=client, async_mode=True),
        request(),
    )

    assert result.selections[0].option_id == "candidate:1"
    assert result.selections[0].score == 0.77


def test_sync_mode_rejects_async_client() -> None:
    client = FakeAsyncClient(FakeResponse("candidate:0", 0.8))

    with pytest.raises(PlanningError, match="asynchronous TypeSafe client"):
        choose_sync(JevDecisionBackend(client=client), request())


def test_credentials_are_client_configuration_not_model_state(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:
    captured: dict[str, Any] = {}

    class SDKClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client_kwargs"] = kwargs

        def __enter__(self) -> "SDKClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def system_one(self, **kwargs: Any) -> FakeResponse:
            captured["call"] = kwargs
            return FakeResponse("candidate:0", 0.9)

    module = ModuleType("typesafe_sdk")
    module.TypeSafeClient = SDKClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "typesafe_sdk", module)

    choose_sync(
        JevDecisionBackend(api_key="secret-key", model="jev-test"),
        request(),
    )

    assert captured["client_kwargs"]["api_key"] == "secret-key"
    assert "secret-key" not in repr(captured["call"]["state"])
    assert "secret-key" not in repr(captured["call"]["questions"])


@pytest.mark.parametrize("threshold", [-0.01, 1.01, math.nan, math.inf])
def test_min_confidence_must_be_bounded(threshold: float) -> None:
    with pytest.raises(ValueError, match="min_confidence"):
        JevDecisionBackend(min_confidence=threshold)
