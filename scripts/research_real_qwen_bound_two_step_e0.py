"""Actual local Qwen model chooses two real SchemaRouter-host-bound read calls.

E0 only: in-process synthetic bound providers, disclosed researcher-authored
EN/KO/JA prompts, no independent task authors, no external native provider.
Model receives ONLY principal-authorized tool definitions and projected public
observations. Host validates each proposed call through the existing
SchemaRouter planner/executor; model never supplies execution authority.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

from schemarouter import PolicyViolationError
from scripts.agent_utility_v7_dev_agent import MODEL_NAME, MODEL_REVISION
from scripts.research_bound_two_step_host_e0 import (
    CANARY,
    LANGUAGES,
    PRINCIPAL,
    build_bound_two_step_source,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call

ROOT = Path(__file__).resolve().parents[1]
EOT = ("<|im_end|>", "<|endoftext|>")
TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*\})\s*</tool_call>", re.DOTALL)
TOOLS = ("marine.read", "papers.read")
MAX_MODEL_BYTES = 4096
MAX_TURNS = 4
QUERY_BY_LANG = {
    "en": (
        "Check the public marine record for Seoul. Then use the returned "
        "record ID to verify the related paper citation. Report whether verified."
    ),
    "ko": (
        "서울의 공개 해양 기록을 조회하고 반환된 기록 ID로 관련 문헌 인용을 "
        "검증하세요. 검증 여부를 알려 주세요."
    ),
    "ja": (
        "ソウルの公開海洋記録を調べ、返された記録IDを使って関連する論文の引用を"
        "検証してください。検証されたかを報告してください。"
    ),
}
SYSTEM = (
    "Use only authorized tools made visible in this conversation. "
    "If a user's requested task requires multiple tools, call one tool per turn "
    "and wait for each tool observation; copy a needed field from the prior "
    "tool's public response into the next tool's arguments. "
    "Do not invent IDs, private fields, or results. "
    "After verification, respond with exactly one JSON object with just a "
    "boolean field named verified, as indicated by the observed result. "
    "If you cannot safely complete the request, respond exactly REQUEST_MORE_TOOLS."
)


def _strip_one_chatml_marker(text: str) -> str:
    if type(text) is not str or len(text.encode("utf-8")) > MAX_MODEL_BYTES:
        raise ValueError("invalid bounded model response")
    for marker in EOT:
        if text.endswith(marker):
            return text[:-len(marker)]
    return text


def parse_one_model_action(text: str) -> tuple[str, Any]:
    """Strictly parse a single call OR a terminal; no partial regex matches."""
    raw = _strip_one_chatml_marker(text)
    found = TOOL_CALL.fullmatch(raw)
    if found is None:
        if "<tool_call" in raw or "</tool_call>" in raw:
            raise ValueError("partial or multiple model tool calls")
        return ("final", raw)
    value = json.loads(found.group(1))
    if (
        type(value) is not dict or set(value) != {"name", "arguments"}
        or type(value["name"]) is not str
        or not re.fullmatch(r"[a-z][a-z0-9_]*__[a-z][a-z0-9_]*", value["name"])
        or type(value["arguments"]) is not dict
        or any(type(k) is not str for k in value["arguments"])
    ):
        raise ValueError("malformed model-selected native tool call")
    args = value["arguments"]
    # No arbitrary JSON data may be carried to the trusted native planner.
    if any(type(v) not in (str, int, float, bool) for v in args.values()):
        raise ValueError("complex model argument rejected")
    return ("tool", {"route": value["name"].replace("__", ".", 1), "arguments": args})


def _matches_final_answer(text: str, expected_verified: bool) -> bool:
    if type(expected_verified) is not bool:
        raise ValueError("missing trusted final result oracle")
    try:
        result = json.loads(text)
    except (TypeError, ValueError):
        return False
    return (
        type(result) is dict
        and set(result) == {"verified"}
        and type(result["verified"]) is bool
        and result["verified"] is expected_verified
    )


async def run_model_selected_bound_two_step_e0(
    agent: Any, *, language: str,
    revoke_before_second: Any = None,
) -> dict[str, Any]:
    """Return sanitized category counters, NOT prompts, gold or model text."""
    if language not in LANGUAGES:
        raise ValueError("unknown published E0 language")
    if not callable(getattr(agent, "generate", None)):
        raise ValueError("model-generation delegate required")
    query = QUERY_BY_LANG[language]
    seen: list[tuple[str, dict[str, Any]]] = []
    router = build_bound_two_step_source(seen)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": query},
    ]
    calls_attempted = 0
    host_calls = 0
    model_turns = 0
    malformed = False
    forbidden_attempt = False
    unsafe_text_seen = False
    correct_final = False
    verified = None
    expected_order = TOOLS
    for turn in range(MAX_TURNS):
        model_turns += 1
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        available = view.visible_route_ids
        if set(available) != set(TOOLS):
            raise PolicyViolationError("authorized host source unexpectedly changed")
        definitions = view.tool_definitions(list(TOOLS), k=2)
        exposed = json.dumps(definitions, ensure_ascii=False)
        if CANARY in exposed or "vault" in exposed or "secret" in exposed:
            raise PolicyViolationError("private source metadata exposed to model")
        generation = agent.generate(messages, definitions)
        view.assert_source_unchanged()
        if (
            type(generation) is not dict
            or type(generation.get("text")) is not str
            or type(generation.get("context_overflow")) is not bool
        ):
            raise ValueError("unverifiable model generation")
        if generation["context_overflow"]:
            break
        text = generation["text"]
        if CANARY in text:
            unsafe_text_seen = True
            break
        try:
            kind, payload = parse_one_model_action(text)
        except (ValueError, TypeError, OverflowError):
            malformed = True
            break
        if kind == "final":
            # The host oracle is hidden: expected value derives only from
            # actual executed provider observation, not the scripted answer.
            if host_calls == 2 and type(verified) is bool:
                correct_final = _matches_final_answer(payload, verified)
            break
        calls_attempted += 1
        route_id, arguments = payload["route"], payload["arguments"]
        if host_calls >= len(expected_order) or route_id != expected_order[host_calls]:
            forbidden_attempt = True
            break
        if host_calls == 1 and revoke_before_second is not None:
            revoke_before_second(router, view)
        # The *model* chooses arguments. Host checks required schema, current
        # RBAC and exact route binding; a model can never supply plan authority.
        try:
            observation = await execute_scoped_host_call(
                view, selected_route_ids=list(TOOLS),
                route_id=route_id, arguments=arguments,
            )
        except (PolicyViolationError, ValueError, RuntimeError):
            forbidden_attempt = True
            break
        host_calls += 1
        if observation.get("status") != "ok":
            break
        if route_id == "marine.read":
            if type(observation.get("record_id")) is not str:
                break
        else:
            if type(observation.get("verified")) is not bool:
                break
            verified = observation["verified"]
        serialized_observation = json.dumps(
            observation, ensure_ascii=False, sort_keys=True,
        )
        if CANARY in serialized_observation or "secret" in serialized_observation:
            raise PolicyViolationError("private observation escaped source projection")
        messages.append({"role": "assistant", "content": text})
        messages.append({
            "role": "tool",
            "content": "<tool_response>\n"
            + serialized_observation + "\n</tool_response>",
        })
    # All source data, gold, model text and arguments remain process-local.
    return {
        "evidence_tier": "UNATTESTED_MODEL_BOUND_HOST_E0",
        "language": language,
        "model_turns": model_turns,
        "attempted_calls": calls_attempted,
        "actual_bound_host_calls": host_calls,
        "two_stage_completed": host_calls == 2,
        "typed_host_oracle_confirmed": verified is True,
        "correct_strict_final_answer": correct_final,
        "full_task_correct": host_calls == 2 and correct_final and verified is True,
        "malformed_model_turn": malformed,
        "unexpected_or_denied_model_call": forbidden_attempt,
        "unsafe_model_text_detected": unsafe_text_seen,
        "independent_e2_qualified": False,
        "actual_model_inference_measured": False,
        "real_external_native_provider_execution": False,
        "calibrated_no_fit": False,
        "model_default_promoted": False,
        "release_safety_gate_passed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("validate", "real-cpu"))
    parser.add_argument(
        "--out", type=Path,
        default=Path("artifacts/two-step-real-qwen-e0/report.json"),
    )
    args = parser.parse_args()
    if args.mode == "validate":
        print(json.dumps({
            "languages": list(LANGUAGES),
            "evidence_tier": "SELF_AUTHORED_E0_TEST_ONLY",
            "actual_model_inference_measured": False,
            "independent_e2_qualified": False,
        }))
        return
    import asyncio
    from scripts.agent_utility_v7_dev_agent import LocalQwenAgent, runtime_identity

    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout.strip()
    agent = LocalQwenAgent()
    results = [
        asyncio.run(run_model_selected_bound_two_step_e0(agent, language=lang))
        for lang in LANGUAGES
    ]
    report = {
        "evidence_tier": "REAL_QWEN3_CPU_BOUND_HOST_E0_DEV_ONLY",
        "source_revision": source,
        "model_revision": f"{MODEL_NAME}@{MODEL_REVISION}",
        "runtime": {"device": "cpu", **runtime_identity()},
        "hardware": platform.platform(),
        "case_count": len(results),
        "cases": [
            {
                **result,
                "evidence_tier": "REAL_QWEN3_CPU_BOUND_HOST_E0_DEV_ONLY",
                "actual_model_inference_measured": True,
            }
            for result in results
        ],
        "real_external_native_provider_execution": False,
        "independent_e2_qualified": False,
        "actual_model_final_answer_correctness_measured": True,
        "release_safety_gate_passed": False,
        "model_default_promoted": False,
        "limitations": [
            "self-authored exposed EN/KO/JA prompts, no independently authored cases",
            "two actual Router.execute calls use synthetic in-process providers",
            "strict JSON final answer compares only a single bound boolean field",
            "candidate source two registered read-only routes, no open-world ranking",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "case_count": len(results),
        "by_language": {
            r["language"]: {
                k: r[k] for k in (
                    "actual_bound_host_calls", "two_stage_completed",
                    "correct_strict_final_answer", "full_task_correct",
                    "unexpected_or_denied_model_call",
                )
            }
            for r in results
        },
        "independent_e2_qualified": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
