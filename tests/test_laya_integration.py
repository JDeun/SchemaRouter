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
from schemarouter.integrations import LayaDecisionBackend


class FakeAgent:
    def __init__(self, device: str) -> None:
        self.device = device


class FakeRouter:
    def __init__(
        self,
        response: Any = None,
        *,
        error: Exception | None = None,
        actual_device: str | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.actual_device = actual_device
        self.calls: list[dict[str, Any]] = []

    def predict(self, state: Any, questions: Any, **kwargs: Any) -> Any:
        self.calls.append({"state": state, "questions": questions, "kwargs": kwargs})
        if self.error is not None:
            raise self.error
        return self.response

    def load(self, model: str) -> FakeAgent:
        if self.actual_device is None:
            raise RuntimeError("no real model attached")
        return FakeAgent(self.actual_device)


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


def response(
    option_id: str = "candidate:1",
    confidence: float = 0.91,
) -> dict[str, Any]:
    return {
        "model": "laya-rl-agent",
        "answers": {
            "selection": {
                "type": "choice",
                "choice": option_id,
                "confidence": confidence,
                "probabilities": {
                    "candidate:0": 0.09,
                    "candidate:1": 0.91,
                },
            }
        },
        "usage": {"input_tokens": 27, "output_tokens": 0},
        "routing": {
            "model": "multilingual",
            "repo": "convaiinnovations/laya/multilingual",
            "reason": "non-English input",
        },
    }


def test_laya_selects_only_from_bounded_options() -> None:
    router = FakeRouter(response())
    result = choose_sync(LayaDecisionBackend(router=router), request())

    assert result.selections[0].option_id == "candidate:1"
    assert result.selections[0].score == 0.91
    assert result.metadata["provider"] == "laya"
    assert result.metadata["model"] == "multilingual"
    assert result.metadata["repo"] == "convaiinnovations/laya/multilingual"
    assert result.metadata["input_tokens"] == 27
    assert result.metadata["output_tokens"] == 0


def test_laya_records_requested_and_actual_runtime_device() -> None:
    router = FakeRouter(response(), actual_device="cpu")
    result = choose_sync(
        LayaDecisionBackend(
            router=router,
            device="cuda",
        ),
        request(),
    )

    assert result.metadata["requested_device"] == "cuda"
    assert result.metadata["actual_device"] == "cpu"


def test_laya_payload_hides_option_metadata_and_credentials() -> None:
    router = FakeRouter(response("candidate:0", 0.8))
    choose_sync(
        LayaDecisionBackend(
            router=router,
            token="secret-hf-token",
        ),
        request(),
    )

    call = router.calls[0]
    assert call["state"] == {
        "query": "choose the best endpoint",
        "context": {"tenant": "example"},
    }
    assert "private_note" not in repr(call["questions"])
    assert "do-not-send" not in repr(call["questions"])
    assert "secret-hf-token" not in repr(call)


def test_laya_can_omit_request_context() -> None:
    router = FakeRouter(response("candidate:0", 0.8))
    choose_sync(
        LayaDecisionBackend(
            router=router,
            include_context=False,
        ),
        request(),
    )

    assert router.calls[0]["state"] == {"query": "choose the best endpoint"}


def test_laya_can_pin_a_specific_checkpoint() -> None:
    router = FakeRouter(response("candidate:0", 0.8))
    choose_sync(
        LayaDecisionBackend(
            router=router,
            model="typed-decisions",
        ),
        request(),
    )

    assert router.calls[0]["kwargs"] == {"model": "typed-decisions"}


def test_laya_rejects_multi_selection_contract() -> None:
    multi = request().model_copy(update={"max_selections": 2})
    router = FakeRouter(response())

    with pytest.raises(PlanningError, match="single-selection"):
        choose_sync(LayaDecisionBackend(router=router), multi)

    assert router.calls == []


def test_laya_low_confidence_abstains() -> None:
    router = FakeRouter(response("candidate:0", 0.49))
    result = choose_sync(
        LayaDecisionBackend(
            router=router,
            min_confidence=0.5,
        ),
        request(),
    )

    assert result.abstained is True
    assert result.selections == []
    assert result.metadata["reason"] == "below_min_confidence"
    assert result.metadata["confidence"] == 0.49


def test_laya_unknown_choice_fails_closed_before_confidence_gate() -> None:
    router = FakeRouter(response("candidate:evil", 0.01))

    with pytest.raises(PlanningError, match="unknown option"):
        choose_sync(
            LayaDecisionBackend(
                router=router,
                min_confidence=0.5,
            ),
            request(),
        )


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -0.1, 1.1])
def test_laya_rejects_invalid_confidence(confidence: float) -> None:
    router = FakeRouter(response("candidate:0", confidence))

    with pytest.raises(PlanningError, match="confidence"):
        choose_sync(LayaDecisionBackend(router=router), request())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"answers": {}},
        {"answers": {"selection": {}}},
        {"answers": {"selection": {"choice": "candidate:0"}}},
        {"answers": {"selection": {"choice": "candidate:0", "confidence": "bad"}}},
    ],
)
def test_laya_rejects_malformed_response(payload: dict[str, Any]) -> None:
    with pytest.raises(PlanningError, match="invalid choice response"):
        choose_sync(
            LayaDecisionBackend(router=FakeRouter(payload)),
            request(),
        )


def test_laya_wraps_inference_errors_as_planning_errors() -> None:
    router = FakeRouter(error=RuntimeError("device failure"))

    with pytest.raises(PlanningError, match="inference failed"):
        choose_sync(LayaDecisionBackend(router=router), request())


@pytest.mark.asyncio
async def test_laya_async_mode_runs_local_inference_without_blocking_contract() -> None:
    router = FakeRouter(response("candidate:0", 0.77))
    result = await choose_async(
        LayaDecisionBackend(
            router=router,
            async_mode=True,
        ),
        request(),
    )

    assert result.selections[0].option_id == "candidate:0"
    assert result.selections[0].score == 0.77


def test_laya_sdk_router_keeps_token_out_of_state_and_preloads_explicit_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class SDKRouter:
        def __init__(self, **kwargs: Any) -> None:
            captured["router_kwargs"] = kwargs

        def preload(self, names: list[str]) -> None:
            captured["preload"] = names

        def predict(self, state: Any, questions: Any, **kwargs: Any) -> dict[str, Any]:
            captured["call"] = {
                "state": state,
                "questions": questions,
                "kwargs": kwargs,
            }
            return response("candidate:0", 0.9)

    module = ModuleType("laya")
    module.Router = SDKRouter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "laya", module)

    result = choose_sync(
        LayaDecisionBackend(
            model="english",
            device="cpu",
            token="secret-hf-token",
            preload=True,
            max_loaded=2,
        ),
        request(),
    )

    assert result.selections[0].option_id == "candidate:0"
    assert captured["router_kwargs"] == {
        "device": "cpu",
        "token": "secret-hf-token",
        "max_loaded": 2,
        "preload": False,
    }
    assert captured["preload"] == ["english"]
    assert captured["call"]["kwargs"] == {"model": "english"}
    assert "secret-hf-token" not in repr(captured["call"]["state"])
    assert "secret-hf-token" not in repr(captured["call"]["questions"])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"model": ""}, "model"),
        ({"min_confidence": -0.01}, "min_confidence"),
        ({"min_confidence": 1.01}, "min_confidence"),
        ({"min_confidence": math.nan}, "min_confidence"),
        ({"max_loaded": 0}, "max_loaded"),
        ({"max_loaded": True}, "max_loaded"),
        ({"device": ""}, "device"),
    ],
)
def test_laya_validates_trusted_configuration(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LayaDecisionBackend(**kwargs)



@pytest.mark.parametrize("choice", [
    True, False, 42, 0, None, ["candidate:0"], {"id": "candidate:0"},
])
def test_laya_non_string_choice_does_not_coerce_to_finite_id(
    choice: Any,
) -> None:
    # Both 'True' and '42' are legitimate finite STRING option IDs; a
    # Boolean/number from a malformed native wire response must not select.
    req = request().model_copy(update={
        "options": [
            DecisionOption(id="True", label="true string ID"),
            DecisionOption(id="42", label="numeric string ID"),
        ],
    })
    wire = response()
    wire["answers"]["selection"]["choice"] = choice
    with pytest.raises(PlanningError, match="invalid choice response"):
        choose_sync(LayaDecisionBackend(router=FakeRouter(wire)), req)


@pytest.mark.parametrize("primitive", [None, "noul", "score", "multiselect"])
def test_laya_refuses_to_coerce_a_non_choice_primitive(
    primitive: str | None,
) -> None:
    wire = response("candidate:0", 0.99)
    if primitive is None:
        del wire["answers"]["selection"]["type"]
    else:
        wire["answers"]["selection"]["type"] = primitive
    with pytest.raises(PlanningError, match="invalid choice response"):
        choose_sync(LayaDecisionBackend(router=FakeRouter(wire)), request())


@pytest.mark.parametrize("value", [True, False, "0.99", None, [], {}])
def test_laya_confidence_requires_numeric_non_boolean_scalar(value: Any) -> None:
    wire = response("candidate:0", 0.99)
    wire["answers"]["selection"]["confidence"] = value
    with pytest.raises(PlanningError, match="invalid choice response"):
        choose_sync(LayaDecisionBackend(router=FakeRouter(wire)), request())


def test_laya_boolean_usage_counts_are_not_reported_as_tokens() -> None:
    wire = response("candidate:0", 0.8)
    wire["usage"] = {"input_tokens": True, "output_tokens": False}
    result = choose_sync(LayaDecisionBackend(router=FakeRouter(wire)), request())
    assert result.selections[0].option_id == "candidate:0"
    assert "input_tokens" not in result.metadata
    assert "output_tokens" not in result.metadata


def test_laya_valid_numeric_confidence_and_usage_remain_compatible() -> None:
    wire = response("candidate:0", 1)
    wire["usage"] = {"input_tokens": 0, "output_tokens": 16}
    result = choose_sync(LayaDecisionBackend(router=FakeRouter(wire)), request())
    assert result.selections[0].score == 1.0
    assert result.metadata["input_tokens"] == 0
    assert result.metadata["output_tokens"] == 16


@pytest.mark.parametrize(("flag", "invalid"), [
    ("min_confidence", True),
    ("min_confidence", False),
    ("min_confidence", "0.6"),
    ("min_confidence", None),
    ("preload", "false"),
    ("preload", 1),
    ("async_mode", "false"),
    ("async_mode", 1),
    ("include_context", "false"),
    ("include_context", 1),
])
def test_laya_trusted_settings_require_explicit_scalar_types(
    flag: str,
    invalid: Any,
) -> None:
    with pytest.raises(ValueError, match=flag):
        LayaDecisionBackend(**{flag: invalid})



def test_laya_huge_numeric_confidence_fails_closed_as_planning_error() -> None:
    wire = response("candidate:0", 0.5)
    wire["answers"]["selection"]["confidence"] = 10 ** 1000
    with pytest.raises(PlanningError, match="invalid choice response"):
        choose_sync(LayaDecisionBackend(router=FakeRouter(wire)), request())


def test_laya_huge_configured_min_confidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="min_confidence"):
        LayaDecisionBackend(min_confidence=10 ** 1000)


@pytest.mark.parametrize(
    "forgery",
    [
        {"query": ["injected"]},
        {"query": ""},
        {"query": "    "},
        {"options": [None]},
        {"options": [{"id": "candidate:0"}]},
        {"options": [DecisionOption(id="candidate:0").model_copy(
            update={"id": ["invalid"]}
        )]},
        {"options": [DecisionOption(id="candidate:0"), DecisionOption(
            id="candidate:0"
        )]},
        {"max_selections": True},
        {"context": ["private", "untrusted"]},
    ],
)
def test_laya_rejects_unvalidated_choice_requests_before_local_inference(
    forgery: dict[str, Any],
) -> None:
    router = FakeRouter(response())
    unsafe = request().model_copy(update=forgery)
    with pytest.raises(PlanningError, match="invalid decision request|empty decision query"):
        choose_sync(LayaDecisionBackend(router=router), unsafe)
    assert router.calls == []


def test_laya_validated_request_roundtrip_preserves_original_options() -> None:
    req = request()
    router = FakeRouter(response())
    chosen = choose_sync(LayaDecisionBackend(router=router), req)
    assert chosen.selections[0].option_id == "candidate:1"
    assert list(router.calls[0]["questions"]["selection"]["criteria"]) == [
        "candidate:0", "candidate:1",
    ]
    assert len(req.options) == 2


@pytest.mark.parametrize(
    "invalid",
    ["", "   ", b"opaque", 123, True, "abc\r\nInjected: bad",
     "abc\x00def", "abc\x7fdef", "abc\tdef"],
)
def test_laya_local_token_preflight_fails_before_sdk_use(
    invalid: Any,
) -> None:
    router = FakeRouter(response())
    with pytest.raises(ValueError, match="token"):
        LayaDecisionBackend(router=router, token=invalid)
    assert router.calls == []


def test_laya_local_token_error_does_not_log_secret() -> None:
    dangerous = "secret\r\nInjected: bad"
    with pytest.raises(ValueError) as exc:
        LayaDecisionBackend(token=dangerous)
    assert dangerous not in str(exc.value)


def test_laya_local_opaque_token_remains_supported() -> None:
    router = FakeRouter(response("candidate:0", 0.99))
    out = choose_sync(
        LayaDecisionBackend(router=router, token="local-key-dont-echo"),
        request(),
    )
    assert out.selections[0].option_id == "candidate:0"
    assert "local-key-dont-echo" not in repr(router.calls)
