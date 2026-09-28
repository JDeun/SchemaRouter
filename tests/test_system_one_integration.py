from __future__ import annotations

from typing import Any

import pytest

from schemarouter import DecisionOption, DecisionRequest, PlanningError, choose_sync
from schemarouter.integrations import SystemOneDecisionBackend


class FakeChoiceAnswer:
    def __init__(self, choice: str, confidence: float) -> None:
        self.choice = choice
        self.confidence = confidence


class FakeUsage:
    input_tokens = 31
    output_tokens = 0


class FakeResponse:
    def __init__(
        self,
        choice: str = "candidate:1",
        confidence: float = 0.93,
        model: str = "kev-4b",
    ) -> None:
        self.choices = {"selection": FakeChoiceAnswer(choice, confidence)}
        self.model = model
        self.usage = FakeUsage()


class FakeCompatibleClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def system_one(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def request() -> DecisionRequest:
    return DecisionRequest(
        query="find the endpoint that can execute this request",
        options=[
            DecisionOption(
                id="candidate:0",
                label="materials.search",
                description="Search registered material records",
                metadata={"secret": "never-forward"},
            ),
            DecisionOption(
                id="candidate:1",
                label="materials.lookup",
                description="Look up one registered material record",
            ),
        ],
        context={"tenant": "example"},
    )


def test_system_one_backend_targets_compatible_provider_without_new_adapter() -> None:
    client = FakeCompatibleClient(FakeResponse())
    backend = SystemOneDecisionBackend(
        client=client,
        model="kev-4b",
        provider_name="kev-local",
        base_url="http://127.0.0.1:8000/v1",
        min_confidence=0.5,
    )

    result = choose_sync(backend, request())

    assert result.selections[0].option_id == "candidate:1"
    assert result.selections[0].score == 0.93
    assert result.metadata["provider"] == "kev-local"
    assert result.metadata["model"] == "kev-4b"
    assert result.metadata["transport"] == "system-one-compatible"
    assert result.metadata["input_tokens"] == 31
    assert result.metadata["output_tokens"] == 0


def test_system_one_backend_keeps_private_option_metadata_local() -> None:
    client = FakeCompatibleClient(FakeResponse(choice="candidate:0"))
    choose_sync(SystemOneDecisionBackend(client=client), request())

    call = client.calls[0]
    assert call["state"] == {
        "query": "find the endpoint that can execute this request",
        "context": {"tenant": "example"},
    }
    assert "secret" not in repr(call["questions"])
    assert "never-forward" not in repr(call["questions"])


def test_system_one_backend_rejects_unknown_provider_choice_before_confidence() -> None:
    client = FakeCompatibleClient(
        FakeResponse(choice="candidate:unregistered", confidence=0.01)
    )

    with pytest.raises(PlanningError, match="unknown option"):
        choose_sync(
            SystemOneDecisionBackend(
                client=client,
                provider_name="future-system-one-model",
                min_confidence=0.99,
            ),
            request(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_name", ""),
        ("model", " "),
        ("base_url", ""),
    ],
)
def test_system_one_backend_rejects_empty_provider_configuration(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValueError):
        SystemOneDecisionBackend(**{field: value})
