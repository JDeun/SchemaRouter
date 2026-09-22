import json

import httpx
import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    PlanningError,
    choose_async,
    choose_sync,
)
from schemarouter.integrations.ollama import OllamaDecisionBackend


def request(*, max_selections: int = 1) -> DecisionRequest:
    return DecisionRequest(
        query="choose the best endpoint",
        options=[
            DecisionOption(
                id="endpoint:0",
                label="search",
                description="Search the knowledge base",
                metadata={"secret": "must-not-leak"},
            ),
            DecisionOption(
                id="endpoint:1",
                label="get",
                description="Fetch one item by id",
                metadata={"internal": True},
            ),
        ],
        max_selections=max_selections,
        context={"tenant": "demo"},
    )


def ollama_response(content: dict, **extra) -> httpx.Response:
    payload = {
        "model": "qwen3:8b",
        "message": {
            "role": "assistant",
            "content": json.dumps(content),
        },
        "prompt_eval_count": 42,
        "eval_count": 7,
        "total_duration": 123456,
        **extra,
    }
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )


def test_ollama_backend_uses_bounded_structured_output_and_hides_metadata() -> None:
    captured: dict = {}

    def handler(request_: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request_.content))
        return ollama_response(
            {
                "selections": [{"option_id": "endpoint:1", "score": 0.9}],
                "abstained": False,
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        backend = OllamaDecisionBackend("qwen3:8b", http_client=client)
        result = choose_sync(backend, request())
    finally:
        client.close()

    assert result.selections[0].option_id == "endpoint:1"
    assert result.selections[0].score == 0.9
    assert result.metadata["provider"] == "ollama"
    assert result.metadata["model"] == "qwen3:8b"
    assert result.metadata["input_tokens"] == 42
    assert result.metadata["output_tokens"] == 7

    assert captured["stream"] is False
    assert captured["options"]["temperature"] == 0
    ids = captured["format"]["properties"]["selections"]["items"]["properties"]["option_id"]["enum"]
    assert ids == ["endpoint:0", "endpoint:1"]
    assert json.dumps(captured["format"], ensure_ascii=False, sort_keys=True) in (
        captured["messages"][0]["content"]
    )

    user_payload = json.loads(captured["messages"][1]["content"])
    assert user_payload["context"] == {"tenant": "demo"}
    assert user_payload["options"][0]["id"] == "endpoint:0"
    assert "metadata" not in user_payload["options"][0]
    assert "secret" not in captured["messages"][1]["content"]


def test_ollama_backend_can_exclude_context() -> None:
    captured: dict = {}

    def handler(request_: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request_.content))
        return ollama_response(
            {
                "selections": [{"option_id": "endpoint:0"}],
                "abstained": False,
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = choose_sync(
            OllamaDecisionBackend(
                "qwen3:8b",
                http_client=client,
                include_context=False,
            ),
            request(),
        )
    finally:
        client.close()

    assert result.selections[0].option_id == "endpoint:0"
    user_payload = json.loads(captured["messages"][1]["content"])
    assert "context" not in user_payload


def test_ollama_backend_abstention_is_preserved() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: ollama_response({"selections": [], "abstained": True})
        )
    )
    try:
        result = choose_sync(
            OllamaDecisionBackend("qwen3:8b", http_client=client),
            request(),
        )
    finally:
        client.close()

    assert result.abstained is True
    assert result.selections == []


def test_ollama_backend_rejects_unknown_option_ids_even_if_server_ignores_schema() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: ollama_response(
                {
                    "selections": [{"option_id": "endpoint:evil", "score": 1.0}],
                    "abstained": False,
                }
            )
        )
    )
    try:
        with pytest.raises(PlanningError, match="unknown option"):
            choose_sync(
                OllamaDecisionBackend("qwen3:8b", http_client=client),
                request(),
            )
    finally:
        client.close()


@pytest.mark.parametrize(
    "content",
    [
        {"selections": [], "abstained": False},
        {"selections": [{"option_id": "endpoint:0", "score": 1.5}], "abstained": False},
        {"selections": [{"option_id": "endpoint:0"}], "abstained": True},
        {
            "selections": [
                {"option_id": "endpoint:0"},
                {"option_id": "endpoint:1"},
            ],
            "abstained": False,
        },
        {
            "selections": [
                {"option_id": "endpoint:0"},
                {"option_id": "endpoint:0"},
            ],
            "abstained": False,
        },
    ],
)
def test_ollama_backend_rejects_malformed_bounded_decisions(content: dict) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: ollama_response(content))
    )
    try:
        with pytest.raises(PlanningError):
            choose_sync(
                OllamaDecisionBackend("qwen3:8b", http_client=client),
                request(),
            )
    finally:
        client.close()


def test_ollama_backend_rejects_invalid_message_content() -> None:
    response = httpx.Response(
        200,
        json={
            "model": "qwen3:8b",
            "message": {"role": "assistant", "content": "not-json"},
        },
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda _: response))
    try:
        with pytest.raises(PlanningError, match="invalid bounded decision"):
            choose_sync(
                OllamaDecisionBackend("qwen3:8b", http_client=client),
                request(),
            )
    finally:
        client.close()


@pytest.mark.asyncio
async def test_ollama_backend_supports_async_http_execution() -> None:
    def handler(request_: httpx.Request) -> httpx.Response:
        assert request_.url == httpx.URL("http://127.0.0.1:11434/api/chat")
        return ollama_response(
            {
                "selections": [{"option_id": "endpoint:0", "score": 0.8}],
                "abstained": False,
            }
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        backend = OllamaDecisionBackend(
            "qwen3:8b",
            async_mode=True,
            http_client=client,
        )
        result = await choose_async(backend, request())

    assert result.selections[0].option_id == "endpoint:0"
    assert result.metadata["input_tokens"] == 42


def test_ollama_backend_supports_multiple_selections_with_local_bound() -> None:
    captured: dict = {}

    def handler(request_: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request_.content))
        return ollama_response(
            {
                "selections": [
                    {"option_id": "endpoint:0", "score": 0.8},
                    {"option_id": "endpoint:1", "score": 0.7},
                ],
                "abstained": False,
            }
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = choose_sync(
            OllamaDecisionBackend("qwen3:8b", http_client=client),
            request(max_selections=2),
        )
    finally:
        client.close()

    assert [item.option_id for item in result.selections] == ["endpoint:0", "endpoint:1"]
    assert captured["format"]["properties"]["selections"]["maxItems"] == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"model": ""}, "model"),
        ({"model": "qwen3:8b", "base_url": "not-a-url"}, "base_url"),
        ({"model": "qwen3:8b", "base_url": "http://user:pass@localhost:11434"}, "credentials"),
        ({"model": "qwen3:8b", "base_url": "http://localhost:11434?x=1"}, "query"),
        ({"model": "qwen3:8b", "timeout": 0}, "timeout"),
    ],
)
def test_ollama_backend_validates_trusted_configuration(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        OllamaDecisionBackend(**kwargs)
