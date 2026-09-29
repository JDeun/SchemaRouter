from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "benchmarks" / "research-prior-art-registry.json"


def _load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _tool_retrieval_workstream(data: dict) -> dict:
    return next(
        row
        for row in data["workstreams"]
        if row["id"] == "tool-retrieval-alignment"
    )


def test_014_prior_art_registry_points_to_active_b2() -> None:
    data = _load()
    active = data["active_cycle"]
    workstream = _tool_retrieval_workstream(data)

    assert active["current_experiment"] == 423
    assert active["b1_status"] == "terminal_canonical_b1"
    assert active["b2_status"] == "attempt6_running_runner_hardened"
    assert active["b2_workflow_run_id"] == 36577044417
    assert workstream["current_experiment"]["issue"] == 423
    assert workstream["current_experiment"]["partial_outcomes_tuning_eligible"] is False
    assert workstream["current_experiment"]["expected_episode_count"] == 460


def test_014_prior_art_registry_contains_current_tool_retrieval_lineage() -> None:
    data = _load()
    workstream = _tool_retrieval_workstream(data)
    titles = {row["title"] for row in workstream["canonical_references"]}

    assert {
        (
            "Retrieval Models Aren't Tool-Savvy: Benchmarking Tool Retrieval "
            "for Large Language Models"
        ),
        (
            "ToolReAGt: Tool Retrieval for LLM-based Complex Task Solution "
            "via Retrieval Augmented Generation"
        ),
        "How Many Tools Should an LLM Agent See? A Chance-Corrected Answer",
        "Dynamic Tool Dependency Retrieval for Lightweight Function Calling",
        "Beyond Single-Shot: Multi-step Tool Retrieval via Query Planning",
        "Multi-Field Tool Retrieval",
        "Toollery: Scaling LLM Agents to Thousands of Skills and Tools",
        (
            "ToolSense: A Diagnostic Framework for Auditing Parametric Tool "
            "Knowledge in LLMs"
        ),
        "ToolSearcher: Optimizing Tool Selection at Scale via Reinforcement Learning",
        (
            "RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via "
            "Retrieval-Augmented Generation"
        ),
        "Risk-Aware Reranking for Agentic Tool Retrieval",
    } <= titles


def test_014_prior_art_registry_keeps_claim_boundaries() -> None:
    data = _load()
    active = data["active_cycle"]
    workstream = _tool_retrieval_workstream(data)

    assert active["b1_terminal_result"]["claim_scope"] == (
        "controlled mechanism evidence only"
    )
    assert workstream["terminal_b1"]["interpretation"] == (
        "mechanism/sanity evidence only"
    )
    assert workstream["current_experiment"]["expected_episode_count"] == 460
    assert workstream["current_experiment"]["max_parallel"] == 4
