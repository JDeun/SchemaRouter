"""Paired E0: ranked versus alphabetic model-visible K5 order, real CPU opt-in.

Only the ordering of the SAME authorized E5-selected five tool definitions
changes. Existing agent/executor, public DEV tasks, Qwen/E5 weights, final
grader, source principal and candidate K are otherwise held fixed.
This cannot establish independent E2, no-fit calibration or live-provider success.
"""
from __future__ import annotations

import argparse
import json
import platform
import secrets
import subprocess
from pathlib import Path
from typing import Any

from schemarouter.decisions import DecisionBackend
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_NAME as QWEN_ID,
    MODEL_REVISION as QWEN_REVISION,
    SEED,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    CORPUS,
    MODEL_ID as E5_ID,
    MODEL_REVISION as E5_REVISION,
    PRINCIPAL,
    build_source_router,
    real_cpu_backend,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_agent_stage_evidence_e0 import E0TraceProvenance
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)
from scripts.research_real_qwen_e5_agent_fixture_dev import (
    PILOT_IDS,
    PILOT_LANGUAGES,
    PILOT_SOURCE_SHA256,
    one_step_fixture_task,
    verified_pilot_cases,
)

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("alphabetical_control", "e5_ranked_order")
ORDER = ("alphabetical_control", "e5_ranked_order",
         "e5_ranked_order", "alphabetical_control")
EVIDENCE = "REAL_LOCAL_QWEN_E5_MODEL_VISIBLE_ORDER_PUBLIC_DEV_NOT_E2"
UNATTESTED = "INJECTED_GENERATOR_E5_ORDER_PUBLIC_DEV_UNSCORED"
SCHEMA_VERSION = 1


class OrderWitnessAgent:
    """For evaluator-only order attestation; raw outputs never stored."""

    def __init__(self, agent: Any) -> None:
        self._agent = agent
        self.first_order: tuple[str, ...] | None = None

    def generate(self, messages: list[dict[str, str]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        order = tuple(item["name"].replace("__", ".", 1) for item in tools)
        if self.first_order is None:
            self.first_order = order
        elif order != self.first_order:
            raise ValueError("model-visible order changed within fixed5 episode")
        return self._agent.generate(messages, tools)


def run_order_probe(
    corpus: dict[str, Any], corpus_sha256: str,
    agent: Any, backend: DecisionBackend,
    *, source_revision: str,
) -> dict[str, Any]:
    """Run disclosed 12-case ABBA with only tool presentation ordering varied."""
    if (type(source_revision) is not str or len(source_revision) != 40
            or any(c not in "0123456789abcdef" for c in source_revision)):
        raise ValueError("invalid source revision")
    cases = verified_pilot_cases(corpus, corpus_sha256)
    if (len(cases) != 12 or len(PILOT_IDS) != 12
            or corpus_sha256 != PILOT_SOURCE_SHA256):
        raise ValueError("original immutable DEV cohort drift")

    router = build_source_router(corpus)
    provenance = E0TraceProvenance(
        source_revision=source_revision, source_sha256=corpus_sha256,
        hmac_key=secrets.token_bytes(32), seed=SEED,
    )
    totals: dict[str, dict[str, dict[str, int]]] = {
        arm: {lang: {
            "supported": 0, "supported_pass": 0,
            "supported_false_refusal": 0,
            "unsupported": 0, "unsupported_strict_no_call": 0,
            "unsupported_tool_executed": 0,
            "unsupported_tool_attempted": 0,
            "policy_blocks": 0, "unauthorized_destructive": 0,
        } for lang in PILOT_LANGUAGES} for arm in ARMS
    }
    changed_rank_positions = 0
    paired_different_outcomes = 0
    per_case_counts: list[dict[str, int]] = []
    for case in cases:
        task = one_step_fixture_task(case)
        # The next expected route and the fixture grader stay completely
        # outside the selector and the model-visible tool definitions.
        selected_for_case: tuple[str, ...] | None = None
        per_case_arm_passes: dict[str, list[bool]] = {arm: [] for arm in ARMS}
        case_different_order = False
        for arm in ORDER:
            view = capture_authorized_agent_tool_surface(
                router, case["query"], principal=PRINCIPAL,
            )
            if len(view.visible_route_ids) != 13:
                raise ValueError("principal-scoped native catalog drift")
            selector = AuthorizedFixed5DecisionSelector(view, backend)
            selected: list[tuple[str, ...]] = []

            def select(query: str, offered: tuple[str, ...]) -> list[str]:
                if selected:
                    raise ValueError("one fixed5 decision required per episode")
                choices = selector(query, offered)
                if len(choices) != 5 or len(set(choices)) != 5:
                    raise ValueError("E5 incomplete or duplicate K5 result")
                selected.append(tuple(choices))
                return choices

            witnessed = OrderWitnessAgent(agent)
            result = run_generated_episode(
                witnessed, router.registry, task,
                EXPERIMENTAL_FIXED5_CONDITION,
                experimental_candidate_selector=select,
                experimental_agent_tool_surface=view,
                experimental_e0_trace_provenance=provenance,
                experimental_preserve_candidate_order=(arm == ARMS[1]),
            )
            view.assert_source_unchanged()
            if len(selected) != 1 or witnessed.first_order is None:
                raise ValueError("missing model-visible ordered tool witness")
            ranked = selected[0]
            if selected_for_case is None:
                selected_for_case = ranked
            elif ranked != selected_for_case:
                raise ValueError("E5 selected different candidates in paired arms")
            visible = ranked if arm == ARMS[1] else tuple(sorted(ranked))
            if witnessed.first_order != visible:
                raise ValueError("model-visible order not independently observed")
            case_different_order |= ranked != tuple(sorted(ranked))
            evidence = result.get("e0_stage_evidence")
            if (type(evidence) is not dict
                    or evidence.get("language") != case["language"]
                    or evidence.get("supported") is not task["supported"]
                    or evidence.get("source_sha256") != corpus_sha256
                    or evidence.get("visible_candidate_counts") != [5]
                    or evidence.get("independent_e2_qualified") is not False
                    or result.get("independent_quality_evidence") is not False
                    or result.get("executable_authority") is not False
                    or evidence.get("unauthorized_destructive_executions") != 0):
                raise ValueError("observed synthetic E0 evidence inconsistent")
            labels = evidence["observed_stages"]
            if type(labels) is not list:
                raise ValueError("invalid E0 stage evidence")
            cell = totals[arm][case["language"]]
            if task["supported"]:
                cell["supported"] += 1
                cell["supported_pass"] += int(evidence["passed"])
                cell["supported_false_refusal"] += int(
                    "supported_no_fit_refusal_observed" in labels
                )
            else:
                cell["unsupported"] += 1
                cell["unsupported_strict_no_call"] += int(evidence["passed"])
                cell["unsupported_tool_executed"] += int(
                    "unsupported_tool_executed" in labels
                )
                cell["unsupported_tool_attempted"] += int(
                    evidence["tool_call_count"] > 0
                )
            cell["policy_blocks"] += evidence["policy_blocks"]
            cell["unauthorized_destructive"] += evidence[
                "unauthorized_destructive_executions"
            ]
            per_case_arm_passes[arm].append(evidence["passed"])
        changed_rank_positions += int(case_different_order)
        paired_different_outcomes += sum(
            a != b
            for a, b in zip(
                per_case_arm_passes[ARMS[0]],
                per_case_arm_passes[ARMS[1]],
                strict=True,
            )
        )
        per_case_counts.append({
            arm: sum(per_case_arm_passes[arm]) for arm in ARMS
        })

    for arm in ARMS:
        for lang in PILOT_LANGUAGES:
            cell = totals[arm][lang]
            if (cell["supported"] != 4 or cell["unsupported"] != 4
                    or cell["unauthorized_destructive"] != 0):
                raise ValueError("paired E0 experiment stratum denominator drift")

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_tier": UNATTESTED,
        "source_revision": source_revision,
        "source_sha256": corpus_sha256,
        "agent_model_id": QWEN_ID,
        "agent_model_revision": QWEN_REVISION,
        "e5_model_id": E5_ID,
        "e5_model_revision": E5_REVISION,
        "device": "UNATTESTED_INJECTION",
        "arms": list(ARMS),
        "sequence": list(ORDER),
        "cases": len(cases),
        "executions": len(cases) * len(ORDER),
        "fixed_k": 5,
        "candidate_set_paired_identical": True,
        "same_original_source_and_fixture": True,
        "order_changed_in_cases": changed_rank_positions,
        "paired_pass_differences": paired_different_outcomes,
        "strata": totals,
        "actual_agent_model_measured": False,
        "actual_e5_model_measured": False,
        "independent_e2_qualified": False,
        "real_provider_execution": False,
        "calibrated_no_fit": False,
        "actual_final_answer_correctness_measured": False,
        "production_default_changed": False,
        "limitations": (
            "Same 12 exposed synthetic DEV tasks with repeated unrandomized ABBA "
            "positions; neither independent provider gold nor factual final "
            "answers measured. The observed difference is NOT a causal estimate, "
            "and no fixed5 candidate ranking is calibrated no-fit."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("validate", "real-cpu"), required=True)
    parser.add_argument("--out", type=Path, default=Path(
        "artifacts/ranked-visible-order-e0/report.json",
    ))
    args = parser.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    cases = verified_pilot_cases(corpus, digest)
    if args.mode == "validate":
        print(json.dumps({
            "case_count": len(cases), "source_sha256": digest,
            "sequence": ORDER, "independent_e2_qualified": False,
        }))
        return

    backend, e5_runtime = real_cpu_backend()
    from scripts.agent_utility_v7_dev_agent import LocalQwenAgent, runtime_identity
    agent = LocalQwenAgent()
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    report = run_order_probe(
        corpus, digest, agent, backend, source_revision=git,
    )
    report["evidence_tier"] = EVIDENCE
    report["actual_agent_model_measured"] = True
    report["actual_e5_model_measured"] = True
    report["device"] = "cpu"
    report["runtime"] = {"e5": e5_runtime, "qwen": runtime_identity()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "source_revision": git,
        "strata": report["strata"],
        "order_changed_in_cases": report["order_changed_in_cases"],
        "paired_pass_differences": report["paired_pass_differences"],
        "independent_e2_qualified": False,
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
