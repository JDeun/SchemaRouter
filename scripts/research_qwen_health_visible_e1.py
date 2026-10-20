"""Pinned Qwen CPU E1: what does the model attempt when health hides a tool?

No actual provider business requests, no model-selected tool execution, no
independent E2 or end-to-end task success claim. Exposed host-authored DEV only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
from pathlib import Path
from typing import Any

import httpx

from scripts.agent_utility_v7_dev_agent import (
    MODEL_NAME,
    MODEL_REVISION,
    LocalQwenAgent,
    runtime_identity,
)
from scripts.research_long_lived_health_session_e1 import (
    LongLivedOpenMeteoHealthSessionE1,
)
from scripts.research_live_health_model_menu_e1 import GEO, WEATHER
from scripts.research_open_meteo_live_two_hop_e1 import CASES
from scripts.research_real_qwen_bound_two_step_e0 import parse_one_model_action
from scripts.research_real_qwen_open_meteo_two_hop_e1 import (
    PRINCIPAL,
    SYSTEM,
    USER_REQUESTS,
)

PHASES = ("healthy", "unavailable", "recovered")
EXPECTED = {"healthy": (GEO,), "unavailable": (), "recovered": (GEO,)}
EVIDENCE_TIER = "REAL_LOCAL_QWEN_SIMULATED_HOST_HEALTH_VISIBLE_E1_NOT_E2"


def _safe_generation(outcome: Any, offered: tuple[str, ...]) -> dict[str, Any]:
    if (
        type(outcome) is not dict
        or type(outcome.get("text")) is not str
        or type(outcome.get("context_overflow")) is not bool
        or type(outcome.get("latency_ms")) not in (int, float)
        or not math.isfinite(outcome["latency_ms"])
        or outcome["latency_ms"] < 0
        or type(outcome.get("input_tokens")) is not int
        or type(outcome.get("tool_tokens")) is not int
        or type(outcome.get("output_tokens")) is not int
        or any(outcome[key] < 0 for key in (
            "input_tokens", "tool_tokens", "output_tokens",
        ))
    ):
        raise ValueError("invalid actual generated model envelope")
    label = "context_overflow" if outcome["context_overflow"] else "invalid_format"
    if not outcome["context_overflow"]:
        try:
            kind, content = parse_one_model_action(outcome["text"])
        except (ValueError, TypeError, OverflowError):
            label = "invalid_format"
        else:
            if kind == "final":
                label = "terminal_no_tool"
            elif kind == "tool" and type(content) is dict:
                route = content["route"]
                label = (
                    "attempt_visible_tool" if route in offered
                    else "attempt_hidden_or_unknown_tool"
                )
    return {
        "action_class": label,
        "input_tokens": outcome["input_tokens"],
        "tool_tokens": outcome["tool_tokens"],
        "output_tokens": outcome["output_tokens"],
        "model_latency_ms": round(float(outcome["latency_ms"]), 3),
        "attempts_executed": 0,
        "provider_http_requests": 0,
    }


async def run_visibility_probe(agent: Any) -> dict[str, Any]:
    """Three host-health phases, three exposed languages, ONE router and agent.

    Model emits only *proposals*. There are no provider calls even when Qwen
    attempts a tool, and no auto-refill of unavailable candidate definitions.
    """
    if not callable(getattr(agent, "generate", None)):
        raise ValueError("frozen Qwen generate-compatible agent required")

    healthy = {"geo": True, "forecast": True}
    probes = {"geo": 0, "forecast": 0}

    async def probe_geocode() -> bool:
        probes["geo"] += 1
        return healthy["geo"]

    async def probe_forecast() -> bool:
        probes["forecast"] += 1
        return healthy["forecast"]

    def prevent_provider_request(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("E1 Qwen visibility-only study prohibits provider GET")

    reports: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(prevent_provider_request),
    ) as client:
        session = LongLivedOpenMeteoHealthSessionE1(
            client,
            trusted_health_probes={GEO: probe_geocode, WEATHER: probe_forecast},
            probe_interval_seconds=30.0,
            max_probe_age_seconds=3600.0,
        )
        identity = id(session.router)
        async with session:
            for language, city, country in CASES:
                if language not in USER_REQUESTS:
                    raise ValueError("source-language case drift")
                outputs: dict[str, Any] = {}
                for phase in PHASES:
                    healthy["geo"] = phase != "unavailable"
                    # Host, NOT the model, triggers the trusted probe update.
                    await session.router.check_health_once()
                    host = {
                        "name": city, "language": language,
                        "country_code": country,
                    }
                    menu = session._menu(
                        USER_REQUESTS[language], PRINCIPAL, host,
                    )
                    # Refresh source readiness with long CPU generation budget.
                    # E1 only: a new positive heartbeat is permitted if the
                    # principal, route binding, status and health stay valid.
                    if menu.route_ids != EXPECTED[phase] or (
                        phase == "unavailable" and menu.status != "temporary_unavailable"
                    ):
                        raise ValueError("strict healthy tool disclosure invariant")
                    expected_tool_names = {
                        route.replace(".", "__", 1) for route in menu.route_ids
                    }
                    if {tool["name"] for tool in menu.definitions} != expected_tool_names:
                        raise ValueError("actual model tool-schema names drift")
                    messages = [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": USER_REQUESTS[language]},
                    ]
                    menu.assert_current()
                    # Keep the background health monitor responsive while the
                    # pinned CPU model runs in a worker, unlike sync block.
                    generated = await asyncio.to_thread(
                        agent.generate, messages, list(menu.definitions),
                    )
                    # Force one more genuine healthy/unhealthy probe after
                    # inference, testing a benign healthy heartbeat does not
                    # invalidate a still-authorized model-visible snapshot.
                    await session.router.check_health_once()
                    if phase != "unavailable":
                        menu.assert_current()
                    elif menu.route_ids or menu.definitions:
                        raise ValueError("unhealthy phase cannot disclose tools")
                    report = _safe_generation(generated, menu.route_ids)
                    report["exposed_tool_count"] = len(menu.route_ids)
                    report["menu_status"] = menu.status
                    outputs[phase] = report
                reports[language] = outputs
                if id(session.router) != identity:
                    raise ValueError("long-lived router identity drift")
            assert session.router.health_monitor.running

    if len(reports) != 3 or sum(len(row) for row in reports.values()) != 9:
        raise ValueError("incomplete pinned model exposure cohort")
    if probes["geo"] < 9 or probes["forecast"] < 9:
        raise ValueError("missing trusted probe receipts")

    return {
        "schema_version": 1,
        "evidence_tier": (
            EVIDENCE_TIER if isinstance(agent, LocalQwenAgent)
            else "INJECTED_AGENT_NO_REAL_QWEN_E1"
        ),
        "model_id": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "phases": list(PHASES),
        "languages": [row[0] for row in CASES],
        "results": reports,
        "shared_router_across_episodes": True,
        "executed_model_tool_calls": 0,
        "external_provider_http_requests": 0,
        "real_provider_success_qualified": False,
        "independent_e2_qualified": False,
        "model_task_completion_measured": False,
        "production_default_changed": False,
        "limitations": (
            "Public exposed language prompts. One-step model proposals only; "
            "host fake probe outcomes, no real provider data; no request "
            "execution, task success, factual final answer or E2 claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("real-cpu",), required=True)
    parser.add_argument("--out", type=Path, default=Path(
        "artifacts/qwen-health-visible-e1/summary.json",
    ))
    args = parser.parse_args()
    agent = LocalQwenAgent()
    report = asyncio.run(run_visibility_probe(agent))
    report["runtime"] = runtime_identity()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "by_language": report["results"],
        "external_provider_http_requests": 0,
        "independent_e2_qualified": False,
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
