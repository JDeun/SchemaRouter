"""Read-only source-pinned Qwen-Agent Nous function-call protocol E0 probe.

This module does not invoke models, SchemaRouter, network tools, or provider hosts.
Use only with the pinned optional upstream package installed by its workflow.
The upstream parser is an untrusted PROPOSAL parser, never execution authority.
"""
from __future__ import annotations

import json
from importlib.metadata import distribution

UPSTREAM_COMMIT = "31a4d36d123688581a9e9744427272b33ce940e0"
UPSTREAM_URL = (
    "https://github.com/QwenLM/Qwen-Agent/tree/" + UPSTREAM_COMMIT
)
FUNCTION_NAME = "marine__read"
FUNCTION_ARGUMENTS = {"place": "Seoul"}
OBSERVATION = {"status": "ok", "record_id": "record-321"}


def _assert_source_pin() -> None:
    """Require an actual pip VCS source pin; a same-version wheel is not enough."""
    package = distribution("qwen-agent")
    direct_url = json.loads(package.read_text("direct_url.json") or "{}")
    actual = direct_url.get("vcs_info", {}).get("commit_id")
    if actual != UPSTREAM_COMMIT:
        raise RuntimeError("Qwen-Agent must be installed from the pinned upstream Git commit")


def _text(message: object) -> str:
    """Extract only source-normalized text content; no model output is collected."""
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        raise AssertionError("upstream message content is not a list")
    if not all(isinstance(item.text, str) for item in content):
        raise AssertionError("unexpected upstream multimodal content")
    return "".join(item.text for item in content)


def run_protocol_probe() -> dict[str, object]:
    """Exercise the REAL upstream preprocess/postprocess on synthetic records."""
    _assert_source_pin()
    from qwen_agent.llm.fncall_prompts.nous_fncall_prompt import NousFnCallPrompt
    from qwen_agent.llm.function_calling import validate_num_fncall_results
    from qwen_agent.llm.schema import (
        ASSISTANT, FUNCTION, SYSTEM, USER, ContentItem, FunctionCall, Message,
    )

    call = FunctionCall(
        name=FUNCTION_NAME,
        arguments=json.dumps(FUNCTION_ARGUMENTS, sort_keys=True),
    )
    functions = [{
        "name": FUNCTION_NAME,
        "description": "Return a public marine record ID.",
        "parameters": {
            "type": "object",
            "properties": {"place": {"type": "string"}},
            "required": ["place"],
        },
    }]
    messages = [
        Message(role=SYSTEM, content=[ContentItem(text="Authorized public test only.")]),
        Message(role=USER, content=[ContentItem(text="Read the public marine record.")]),
        Message(role=ASSISTANT, content=[], function_call=call),
        Message(
            role=FUNCTION, name=FUNCTION_NAME,
            content=[ContentItem(text=json.dumps(OBSERVATION, sort_keys=True))],
        ),
    ]
    prompt = NousFnCallPrompt()
    # Unlike the SchemaRouter raw E0 pilot's role='tool' observation,
    # Qwen-Agent Nous renders a FUNCTION result under role='user'.
    processed = prompt.preprocess_fncall_messages(
        messages, functions=functions, lang="en",
    )
    assert [x.role for x in processed] == [SYSTEM, USER, ASSISTANT, USER]
    assistant_text = _text(processed[2])
    response_text = _text(processed[3])
    assert assistant_text.startswith("<tool_call>\\n")
    assert assistant_text.endswith("\\n</tool_call>")
    assert response_text.startswith("<tool_response>\\n")
    assert response_text.endswith("\\n</tool_response>")
    assert json.loads(
        assistant_text.removeprefix("<tool_call>\\n").removesuffix("\\n</tool_call>")
    ) == {"name": FUNCTION_NAME, "arguments": FUNCTION_ARGUMENTS}
    assert json.loads(
        response_text.removeprefix("<tool_response>\\n").removesuffix("\\n</tool_response>")
    ) == OBSERVATION

    # Actually invoke Qwen-Agent's parser; the host is still the only invoker.
    raw = assistant_text
    decoded = prompt.postprocess_fncall_messages([
        Message(role=ASSISTANT, content=[ContentItem(text=raw)]),
    ])
    assert len(decoded) == 1
    assert decoded[0].role == ASSISTANT
    assert decoded[0].function_call is not None
    assert decoded[0].function_call.name == FUNCTION_NAME
    assert json.loads(decoded[0].function_call.arguments) == FUNCTION_ARGUMENTS

    # Upstream permits >1 proposed call. Existing E0 host contract deliberately
    # only permits a single reauthorized call per turn.
    parallel = prompt.postprocess_fncall_messages([
        Message(role=ASSISTANT, content=[
            ContentItem(text=raw + "\\n" + raw),
        ]),
    ])
    assert len([m for m in parallel if m.function_call]) == 2

    # Native helper diagnoses mismatched function-result names/order.
    validate_num_fncall_results(
        [
            Message(role=USER, content=[ContentItem(text="Request")]),
            Message(role=ASSISTANT, content=[], function_call=call),
            Message(role=FUNCTION, name=FUNCTION_NAME, content=[ContentItem(text="ok")]),
        ],
        support_multimodal_input=False,
    )
    mismatch_blocked = False
    try:
        validate_num_fncall_results(
            [
                Message(role=USER, content=[ContentItem(text="Request")]),
                Message(role=ASSISTANT, content=[], function_call=call),
                Message(role=FUNCTION, name="vault__read", content=[ContentItem(text="ok")]),
            ],
            support_multimodal_input=False,
        )
    except ValueError:
        mismatch_blocked = True
    assert mismatch_blocked

    return {
        "evidence": "UPSTREAM_QWEN_AGENT_NOUS_READ_ONLY_PROTOCOL_E0",
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream": UPSTREAM_URL,
        "source_attested_by_pip_vcs": True,
        "assistant_tool_call_role": ASSISTANT,
        "function_result_model_role": USER,
        "upstream_parser_single_call_roundtrip": True,
        "upstream_parser_parallel_proposals": 2,
        "mismatched_function_result_rejected": True,
        "provider_calls_executed": 0,
        "model_inference_executed": False,
        "schemarouter_host_authorization_qualified": False,
        "independent_e2_qualified": False,
        "model_promoted": False,
        "release_qualified": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_protocol_probe(), sort_keys=True))
