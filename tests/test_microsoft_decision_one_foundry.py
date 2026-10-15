"""No-provider, no-credential HTTP mock tests for Microsoft Decision-1 (#1324)."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    PlanningError,
    choose_sync,
)
from schemarouter.integrations import MicrosoftDecisionOneFoundryBackend

ENDPOINT = "https://example.services.ai.azure.com"
DEPLOYMENT = "my-microsoft-decision-1-deployment"


def decision_request() -> DecisionRequest:
    return DecisionRequest(
        query="Cancel this customer order",
        options=[
            DecisionOption(
                id="orders_lookup", label="orders.lookup",
                description="Read order details only; cannot cancel an order",
                metadata={"secret": "do-not-forward"},
            ),
            DecisionOption(
                id="none_of_above", label="No registered capability",
                description="No route can perform the requested operation",
            ),
        ],
        context={"tenant_secret": "do-not-forward"},
    )


def valid_payload(choice: str = "none_of_above") -> dict[str, Any]:
    return {
        "model": "microsoft-decision-1",
        "answers": {
            "selection": {
                "type": "choice", "choice": choice,
                "probabilities": {
                    "orders_lookup": 0.85 if choice == "orders_lookup" else 0.15,
                    "none_of_above": 0.15 if choice == "orders_lookup" else 0.85,
                },
            },
        },
        "usage": {"input_tokens": 23, "output_tokens": 0},
    }


def backend_with_payload(
    payload: Any,
    *,
    status: int = 200,
    raw_content: bytes | None = None,
    include_context: bool = False,
):
    requests: list[httpx.Request] = []

    def mock_transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if raw_content is not None:
            return httpx.Response(status, content=raw_content)
        # Simulate even deliberately non-RFC provider payloads (NaN), which
        # standard httpx.Response(json=...) refuses to serialize.
        return httpx.Response(
            status, content=json.dumps(payload, allow_nan=True).encode("utf-8"),
        )

    client = httpx.Client(transport=httpx.MockTransport(mock_transport))
    backend = MicrosoftDecisionOneFoundryBackend(
        resource_endpoint=ENDPOINT,
        deployment=DEPLOYMENT,
        api_key="fake-unit-test-only",
        client=client,
        include_context=include_context,
    )
    return backend, client, requests


def test_foundry_native_choice_payload_auth_and_no_fit_never_executes_tool():
    backend, client, requests = backend_with_payload(valid_payload())
    try:
        result = choose_sync(backend, decision_request())
        assert result.abstained
        assert result.selections == []
        assert result.metadata["reason"] == "selected_none_of_above"
        assert result.metadata["model"] == "microsoft-decision-1"
        assert result.metadata["input_tokens"] == 23
        assert result.metadata["confidence_verified"] is True
        assert len(requests) == 1
        wire = requests[0]
        assert str(wire.url) == ENDPOINT + "/providers/microsoft/v1/systemone"
        assert wire.method == "POST"
        assert wire.headers["api-key"] == "fake-unit-test-only"
        assert "authorization" not in wire.headers
        body = json.loads(wire.content)
        assert body["model"] == DEPLOYMENT
        assert body["questions"]["selection"]["type"] == "choice"
        assert body["questions"]["selection"]["criteria"]["none_of_above"]
        assert set(body["questions"]["selection"]["criteria"]) == {
            "orders_lookup", "none_of_above",
        }
        assert "do-not-forward" not in repr(body)
    finally:
        client.close()


def test_foundry_does_not_invent_confidence_missing_official_probability_shape():
    payload = valid_payload("orders_lookup")
    payload["answers"]["selection"].pop("probabilities")
    backend, client, _ = backend_with_payload(payload)
    try:
        result = choose_sync(backend, decision_request())
        assert not result.abstained
        assert result.selections[0].option_id == "orders_lookup"
        assert result.selections[0].score is None
        assert result.metadata["confidence_verified"] is False
    finally:
        client.close()


def test_foundry_uses_declared_probability_only_not_untrusted_raw_choice():
    backend, client, _ = backend_with_payload(valid_payload("orders_lookup"))
    try:
        result = choose_sync(backend, decision_request())
        assert result.selections[0].score == 0.85
    finally:
        client.close()


@pytest.mark.parametrize(("mutate", "error"), [
    (lambda p: p["answers"]["selection"].update(choice=True), "unauthorized option"),
    (lambda p: p["answers"]["selection"].update(choice=1), "unauthorized option"),
    (
        lambda p: p["answers"]["selection"].update(choice="unknown_action"),
        "unauthorized option",
    ),
    (
        lambda p: p["answers"]["selection"].update(type="noul"),
        "invalid choice answer",
    ),
    (lambda p: p.update(answers=None), "no answers object"),
    (
        lambda p: p["answers"]["selection"].update(probabilities=True),
        "invalid option probabilities",
    ),
    (
        lambda p: p["answers"]["selection"]["probabilities"].update(
            orders_lookup=True,
        ),
        "invalid option probabilities",
    ),
    (
        lambda p: p["answers"]["selection"]["probabilities"].update(
            orders_lookup=-0.1,
        ),
        "invalid option probabilities",
    ),
    (
        lambda p: p["answers"]["selection"]["probabilities"].update(
            orders_lookup=1.1,
        ),
        "invalid option probabilities",
    ),
    (
        lambda p: p["answers"]["selection"]["probabilities"].update(
            orders_lookup=float("nan"),
        ),
        "invalid decision JSON",
    ),
    (
        lambda p: p["answers"]["selection"]["probabilities"].update(
            orders_lookup=10 ** 1000,
        ),
        "invalid option probabilities",
    ),
    (
        lambda p: p.update(model=True),
        "invalid model provenance",
    ),
    (
        lambda p: p["usage"].update(input_tokens=True),
        "malformed token usage",
    ),
    (
        lambda p: p["usage"].update(output_tokens=-1),
        "malformed token usage",
    ),
])
def test_foundry_malformed_answers_never_become_authorized_choices(mutate, error):
    payload = valid_payload("orders_lookup")
    mutate(payload)
    backend, client, _ = backend_with_payload(payload)
    try:
        with pytest.raises(PlanningError, match=error):
            choose_sync(backend, decision_request())
    finally:
        client.close()


@pytest.mark.parametrize(("raw", "error"), [
    (b'{"answers":{"selection":{"type":"choice","choice":"orders_lookup",'
     b'"choice":"none_of_above"}}}', "invalid decision JSON"),
    (b'{"answers":{"selection":{"type":"choice","choice":"orders_lookup",'
     b'"probabilities":{"orders_lookup":NaN}}}}', "invalid decision JSON"),
    (b"not json", "invalid decision JSON"),
    (b"[]", "non-object response"),
    (b"x" * (1_048_576 + 1), "maximum allowed size"),
])
def test_foundry_rejects_duplicate_keys_nan_or_oversized_response(raw, error):
    backend, client, _ = backend_with_payload(None, raw_content=raw)
    try:
        with pytest.raises(PlanningError, match=error):
            choose_sync(backend, decision_request())
    finally:
        client.close()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_foundry_http_error_does_not_repeat_provider_body_or_secret(status):
    raw = b"secret-token fake-unit-test-only"
    backend, client, _ = backend_with_payload(
        None, status=status, raw_content=raw,
    )
    try:
        with pytest.raises(PlanningError, match="request failed") as exc:
            choose_sync(backend, decision_request())
        assert "secret-token" not in str(exc.value)
        assert "fake-unit-test-only" not in str(exc.value)
    finally:
        client.close()


@pytest.mark.parametrize(("change", "reason"), [
    ({"resource_endpoint": "http://example.com"}, "HTTPS origin"),
    ({"resource_endpoint": "https://user:secret@example.com"}, "HTTPS origin"),
    ({"resource_endpoint": "https://example.com/other"}, "HTTPS origin"),
    ({"resource_endpoint": "https://example.com?key=value"}, "HTTPS origin"),
    ({"resource_endpoint": "https://example.com:invalid"}, "HTTPS origin"),
    ({"resource_endpoint": "https://example.com:99999"}, "HTTPS origin"),
    ({"resource_endpoint": "https://example.com:0"}, "HTTPS origin"),
    ({"resource_endpoint": "https://exa\nmple.com"}, "HTTPS origin"),
    ({"resource_endpoint": "https://exa mple.com"}, "HTTPS origin"),
    ({"resource_endpoint": "https://[::1"}, "HTTPS origin"),
    ({"deployment": ""}, "deployment"),
    ({"deployment": "deployment with spaces"}, "deployment"),
    ({"timeout": True}, "timeout"),
    ({"timeout": 0}, "timeout"),
    ({"timeout": 10 ** 1000}, "timeout"),
    ({"include_context": "false"}, "include_context"),
    ({"require_no_fit": "false"}, "require_no_fit"),
    ({"api_key": None}, "credential"),
    ({"bearer_token": "both-credential-types"}, "exactly one"),
])
def test_foundry_configuration_requires_explicit_secure_transport(
    change: dict[str, Any], reason: str,
):
    params = {
        "resource_endpoint": ENDPOINT, "deployment": DEPLOYMENT,
        "api_key": "fake-unit-test-only",
    }
    params.update(change)
    with pytest.raises(ValueError, match=reason):
        MicrosoftDecisionOneFoundryBackend(**params)


def test_foundry_requires_explicit_no_fit_in_options_before_network():
    backend, client, requests = backend_with_payload(valid_payload())
    without_rejection = decision_request().model_copy(
        update={"options": [
            DecisionOption(
                id="orders_lookup", description="Look up the order",
            ),
        ]},
    )
    try:
        with pytest.raises(ValueError, match="none_of_above"):
            choose_sync(backend, without_rejection)
        assert requests == []
    finally:
        client.close()


def test_foundry_context_forwarding_requires_explicit_true():
    backend, client, requests = backend_with_payload(
        valid_payload(), include_context=True,
    )
    try:
        choose_sync(backend, decision_request())
        sent = json.loads(requests[0].content)
        assert sent["state"]["context"]["tenant_secret"] == "do-not-forward"
        assert "metadata" not in sent["questions"]["selection"]
    finally:
        client.close()


def test_foundry_supports_bearer_without_api_key_header():
    requests: list[httpx.Request] = []

    def mock(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=valid_payload())

    with httpx.Client(transport=httpx.MockTransport(mock)) as client:
        backend = MicrosoftDecisionOneFoundryBackend(
            resource_endpoint=ENDPOINT, deployment=DEPLOYMENT,
            bearer_token="fake-entra-token", client=client,
        )
        result = choose_sync(backend, decision_request())
    assert result.abstained
    assert requests[0].headers["authorization"] == "Bearer fake-entra-token"
    assert "api-key" not in requests[0].headers



def test_foundry_rejects_only_no_fit_without_spending_a_request() -> None:
    backend, client, requests = backend_with_payload(valid_payload())
    only_no_fit = DecisionRequest(
        query="Perform an operation",
        options=[DecisionOption(
            id="none_of_above", description="No supported operation",
        )],
    )
    try:
        with pytest.raises(ValueError, match="actionable option"):
            choose_sync(backend, only_no_fit)
        assert requests == []
    finally:
        client.close()


@pytest.mark.parametrize(("mutation", "message"), [
    (
        {"options": [
            DecisionOption(id="orders_lookup"),
            DecisionOption(id="orders_lookup"),
            DecisionOption(id="none_of_above"),
        ]},
        "invalid choice options",
    ),
    (
        {"options": [
            {"id": True, "description": "forged route"},
            {"id": "none_of_above"},
        ]},
        "invalid choice options",
    ),
    (
        {"options": ["orders_lookup", "none_of_above"]},
        "invalid choice options",
    ),
    ({"max_selections": True}, "invalid choice options"),
    ({"max_selections": "1"}, "invalid choice options"),
    ({"max_selections": 1.0}, "invalid choice options"),
    ({"query": "   "}, "nonblank"),
])
def test_foundry_forged_pydantic_copy_fails_before_paid_io(
    mutation: dict[str, Any], message: str,
) -> None:
    backend, client, requests = backend_with_payload(valid_payload())
    unvalidated = decision_request().model_copy(update=mutation)
    try:
        with pytest.raises(ValueError, match=message):
            choose_sync(backend, unvalidated)
        assert requests == []
    finally:
        client.close()



def test_foundry_oversized_response_stops_streaming_early():
    class CountingStream(httpx.SyncByteStream):
        def __init__(self) -> None:
            self.yielded = 0
            self.closed = False

        def __iter__(self):
            for _ in range(100):
                self.yielded += 1
                yield b"X" * 65536

        def close(self) -> None:
            self.closed = True

    stream = CountingStream()

    def transport(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=stream)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        backend = MicrosoftDecisionOneFoundryBackend(
            resource_endpoint=ENDPOINT, deployment=DEPLOYMENT,
            api_key="fake-unit-test-only", client=client,
        )
        with pytest.raises(PlanningError, match="maximum allowed size"):
            choose_sync(backend, decision_request())
    assert stream.yielded <= 17
    assert stream.closed is True


@pytest.mark.parametrize("context", [
    {"unbounded": float("nan")},
    {"unbounded": float("inf")},
    {"invalid": set(["secret"])},
])
def test_foundry_non_json_context_never_initiates_network(context):
    backend, client, requests = backend_with_payload(
        valid_payload(), include_context=True,
    )
    payload = decision_request().model_copy(update={"context": context})
    try:
        with pytest.raises(ValueError, match="invalid JSON data"):
            choose_sync(backend, payload)
        assert requests == []
    finally:
        client.close()


def test_foundry_oversized_request_is_rejected_before_network():
    backend, client, requests = backend_with_payload(valid_payload())
    huge_option = DecisionOption(
        id="orders_lookup", description="x" * (1_048_576 + 1),
    )
    payload = decision_request().model_copy(update={
        "options": [
            huge_option,
            DecisionOption(id="none_of_above", description="No suitable tool"),
        ],
    })
    try:
        with pytest.raises(ValueError, match="request exceeds maximum"):
            choose_sync(backend, payload)
        assert requests == []
    finally:
        client.close()


@pytest.mark.parametrize(("contradiction", "reason"), [
    (
        {"orders_lookup": 0.1, "none_of_above": 0.9},
        "choice contradicts",
    ),
    (
        {"orders_lookup": 0.5, "none_of_above": 0.5},
        "choice contradicts",
    ),
])
def test_foundry_never_promotes_a_route_against_no_fit_probability(
    contradiction: dict[str, float], reason: str,
):
    payload = valid_payload("orders_lookup")
    payload["answers"]["selection"]["probabilities"] = contradiction
    backend, client, _ = backend_with_payload(payload)
    try:
        with pytest.raises(PlanningError, match=reason):
            choose_sync(backend, decision_request())
    finally:
        client.close()


def test_foundry_no_fit_choice_rejected_when_route_probability_is_higher():
    payload = valid_payload("none_of_above")
    payload["answers"]["selection"]["probabilities"] = {
        "orders_lookup": 0.7, "none_of_above": 0.3,
    }
    backend, client, _ = backend_with_payload(payload)
    try:
        with pytest.raises(PlanningError, match="choice contradicts"):
            choose_sync(backend, decision_request())
    finally:
        client.close()



def test_valid_https_origin_may_use_an_explicit_port() -> None:
    captured: list[httpx.Request] = []

    def response(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=valid_payload())

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        backend = MicrosoftDecisionOneFoundryBackend(
            resource_endpoint="https://example.services.ai.azure.com:8443",
            deployment=DEPLOYMENT,
            api_key="fake-unit-test-only",
            client=client,
        )
        result = choose_sync(backend, decision_request())
    assert result.abstained
    assert str(captured[0].url).startswith(
        "https://example.services.ai.azure.com:8443"
    )
