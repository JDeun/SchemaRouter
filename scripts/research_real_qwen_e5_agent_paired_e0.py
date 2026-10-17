"""Real local Qwen agent + pinned E5 native-K5 E0 task-completion pilot.

Only six *already published* EN/KO/JA synthetic tasks, with real CPU
generation and real native candidate-selection but deterministic fixture
execution. NOT independent E2, host/provider end-to-end or calibrated no-fit.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import platform
import secrets
import subprocess
from pathlib import Path
from typing import Any

from schemarouter import PolicyViolationError
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    canonical_bytes,
    run_generated_episode,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_NAME as AGENT_MODEL_ID,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_REVISION as AGENT_MODEL_REVISION,
)
from scripts.agent_utility_v7_dev_agent import (
    SEED,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    CORPUS,
    MODEL_ID,
    MODEL_REVISION,
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
from scripts.research_authorized_hybrid_fixed5 import AuthorizedHybridFixed5Selector
from scripts.research_paired_agent_fixed5_e0 import (
    ARMS,
    EVIDENCE_TIER,
    aggregate_paired_e0,
)

ROOT = Path(__file__).resolve().parents[1]
# Locked BEFORE first Qwen inference. No case search/tuning from outcomes.
TASK_IDS = (
    "supported-en-weather.current",
    "unsupported-en-materials.delete_sample",
    "supported-ko-inventory.lookup",
    "unsupported-ko-calendar.create_event",
    "supported-ja-papers.search",
    "unsupported-ja-flights.book_ticket",
)
CASE_COUNTS = {"en": 2, "ko": 2, "ja": 2}
PUBLIC_TASK_COUNT = 6
ORIGINAL_CATALOG_SIZE = 13


def _pilot_cases(corpus: dict[str, Any], source_digest: str) -> list[dict[str, Any]]:
    original, digest = load_development_corpus(CORPUS)
    if (
        corpus != original or source_digest != digest
        or corpus.get("surface") != "prospective_development_only"
        or corpus.get("validation_or_holdout_claim_allowed") is not False
    ):
        raise ValueError("frozen public agent pilot source/gold was modified")
    cases = {c["id"]: c for c in corpus["cases"]}
    if (
        len(cases) != len(corpus["cases"])
        or any(case_id not in cases for case_id in TASK_IDS)
    ):
        raise ValueError("missing/duplicate frozen preselected agent pilot tasks")
    chosen = [cases[name] for name in TASK_IDS]
    for language, count in CASE_COUNTS.items():
        subset = [c for c in chosen if c["language"] == language]
        if (
            len(subset) != count
            or {c["kind"] for c in subset} != {"supported", "unsupported"}
        ):
            raise ValueError("paired EN/KO/JA supported/OOD cohort drift")
    for case in chosen:
        route = case["expected_route"]
        if (case["kind"] == "supported") != (type(route) is str and bool(route)):
            raise ValueError("inconsistent frozen source-native case label")
    return chosen


def _fixture_task(case: dict[str, Any]) -> dict[str, Any]:
    """Grader-only post-inference execution fixture: never passed to selector."""
    supported = case["kind"] == "supported"
    route = case["expected_route"]
    return {
        "semantic_task_id": case["id"],
        "language": case["language"],
        "task_stratum": "read_only_supported" if supported else "unsupported_no_fit",
        "query": case["query"],
        "supported": supported,
        "required_routes": [route] if supported else [],
        "executor_fixture": {
            "steps": [{
                "route_id": route,
                "argument_rules": {},
                "observation": {"status": "ok"},
            }] if supported else [],
        },
    }


def run_paired_agent_pilot(
    corpus: dict[str, Any],
    digest: str,
    backend: Any,
    agent: Any,
    *,
    source_revision: str,
    hardware: str,
    runtime_label: str,
    key: bytes,
) -> dict[str, Any]:
    """Runs actual existing source-scoped agent turns; backend is unattested.

    The model/agent implementation injected by a caller CANNOT claim
    authenticated real weights; that marker belongs only to the CLI which
    constructs both pinned runtime objects itself.
    """
    cases = _pilot_cases(corpus, digest)
    if (
        type(source_revision) is not str or len(source_revision) != 40
        or any(c not in "0123456789abcdef" for c in source_revision)
        or type(hardware) is not str or not hardware.strip()
        or type(runtime_label) is not str or not runtime_label.strip()
        or type(key) is not bytes or len(key) < 16
    ):
        raise ValueError("invalid private/host agent pilot provenance")
    router = build_source_router(corpus)
    if (
        sum(len(t.endpoints) for t in router.registry.tools()) != ORIGINAL_CATALOG_SIZE
        or any(
            not endpoint.read_only or endpoint.destructive
            for tool in router.registry.tools() for endpoint in tool.endpoints
        )
    ):
        raise PolicyViolationError("agent E0 requires read-only original source")
    split_hash = hashlib.sha256(canonical_bytes({
        "public_corpus_sha256": digest,
        "precommitted_task_ids": TASK_IDS,
    })).hexdigest()
    identity = {
        "source_revision": source_revision,
        "source_sha256": digest,
        "split_sha256": split_hash,
        "model_revision": f"{MODEL_REVISION};{AGENT_MODEL_REVISION}",
        "model_runtime": runtime_label,
        "hardware": hardware,
        "split_name": "PUBLISHED_SYNTHETIC_DEV_6_NO_E2",
        "seed": SEED,
        "max_k": 5,
    }
    provenance = E0TraceProvenance(
        source_revision=source_revision, source_sha256=digest,
        hmac_key=key, seed=SEED,
    )
    tasks = [_fixture_task(case) for case in cases]
    manifest = {
        "schema_version": 1,
        "evidence_tier": EVIDENCE_TIER,
        "independent_e2_qualified": False,
        "arms": list(ARMS),
        **identity,
        "tasks": [{
            "task_hmac_sha256": hmac.new(
                key, t["semantic_task_id"].encode("utf-8"), hashlib.sha256,
            ).hexdigest(),
            "language": t["language"],
            "task_stratum": t["task_stratum"],
            "supported": t["supported"],
        } for t in tasks],
    }
    arm_rows: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for task in tasks:
        for arm in ARMS:
            # Every arm sees exactly the same original native registered
            # authorized source, query, fixed K and agent object. The gold,
            # state fixture and supported flag remain grader-only.
            view = capture_authorized_agent_tool_surface(
                router, task["query"], principal=PRINCIPAL,
            )
            if len(view.visible_route_ids) != ORIGINAL_CATALOG_SIZE:
                raise PolicyViolationError("agent E0 original source changed")

            if arm == "lexical_k5":
                def selector(query: str, route_ids: tuple[str, ...]) -> list[str]:
                    view.assert_source_unchanged()
                    if query != view.original_query or route_ids != view.visible_route_ids:
                        raise PolicyViolationError("lexical source/query mismatch")
                    candidates = router.retrieve_authorized(
                        query, principal=PRINCIPAL, k=5,
                    ).candidates
                    ids = [c.route_id for c in candidates]
                    view.assert_source_unchanged()
                    return ids
            elif arm == "e5_k5":
                selector = AuthorizedFixed5DecisionSelector(view, backend)
            else:
                selector = AuthorizedHybridFixed5Selector(view, backend)
            # No external provider is invoked. THIS IS the repository's
            # original frozen deterministic tool-call/argument/state executor.
            episode = run_generated_episode(
                agent, router.registry, task,
                EXPERIMENTAL_FIXED5_CONDITION,
                experimental_candidate_selector=selector,
                experimental_agent_tool_surface=view,
                experimental_e0_trace_provenance=provenance,
            )
            safe = episode.get("e0_stage_evidence")
            if type(safe) is not dict or safe.get("condition") != EXPERIMENTAL_FIXED5_CONDITION:
                raise ValueError("missing sanitized post-agent outcome witness")
            if episode.get("unauthorized_destructive_executions") != 0:
                raise PolicyViolationError("unauthorized tool action cannot be scored")
            arm_rows[arm].append(safe)
            view.assert_source_unchanged()
    runs = {
        arm: {"arm": arm, "evidence_tier": EVIDENCE_TIER, **identity,
              "rows": arm_rows[arm]}
        for arm in ARMS
    }
    report = aggregate_paired_e0(manifest, runs)
    if (
        report["task_count"] != PUBLIC_TASK_COUNT
        or any(report["summary"][arm]["task_count"] != PUBLIC_TASK_COUNT for arm in ARMS)
    ):
        raise ValueError("paired agent outcomes are incomplete")
    report.update({
        "surface": "EXPOSED_SYNTHETIC_DEV_TASKS_AND_DETERMINISTIC_FIXTURE",
        "real_agent_model_inference_measured": False,
        "real_retrieval_model_inference_measured": False,
        "agent_execution_measured": True,
        "real_provider_invocation_measured": False,
        "task_success_definition": (
            "Grader-observed fixture-step completion for supported tasks; "
            "zero actual executable fixture calls AND exact "
            "REQUEST_MORE_TOOLS response for unsupported tasks."
        ),
        "agent_model_id": AGENT_MODEL_ID,
        "retrieval_model_id": MODEL_ID,
        "predeclared_task_count": PUBLIC_TASK_COUNT,
        "same_agent_instance_across_arms": True,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "limitations": (
            "Real Qwen/E5 inference is proven only on direct CLI loading, "
            "never via injected backend. Six previously exposed synthetic "
            "queries (three supported, three unsupported), not independent E2; "
            "fixture tool execution, not real native external provider I/O. "
            "Fixed order EN/KO/JA task × lexical/E5/hybrid can confound cache; "
            "tiny per-language denominators cannot support commercial gates."
        ),
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("validate", "real-cpu"))
    parser.add_argument("--out", type=Path, default=Path(
        "artifacts/real-qwen-agent-e5-e0/report.json",
    ))
    args = parser.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    cases = _pilot_cases(corpus, digest)
    if args.mode == "validate":
        print(json.dumps({
            "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
            "fixed_k": 5, "precommitted_tasks": len(cases),
            "supported": 3, "unsupported": 3,
            "languages": list(CASE_COUNTS),
            "source_sha256": digest,
            "independent_e2_qualified": False,
        }))
        return
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("actual source revision missing")
    backend, retrieval_runtime = real_cpu_backend()
    from scripts.agent_utility_v7_dev_agent import LocalQwenAgent, runtime_identity

    agent = LocalQwenAgent()
    report = run_paired_agent_pilot(
        corpus, digest, backend, agent,
        source_revision=revision,
        hardware=platform.platform(),
        runtime_label=json.dumps(
            {"agent": runtime_identity(), "e5": retrieval_runtime},
            sort_keys=True, ensure_ascii=False,
        ),
        key=secrets.token_bytes(32),
    )
    report["evidence_tier"] = "REAL_QWEN_E5_AGENT_SYNTHETIC_E0_DEV_ONLY"
    report["real_agent_model_inference_measured"] = True
    report["real_retrieval_model_inference_measured"] = True
    report["source_revision"] = revision
    report["agent_model_revision"] = AGENT_MODEL_REVISION
    report["retrieval_model_revision"] = MODEL_REVISION
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True,
                   indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "source_revision": revision,
        "task_count": report["task_count"],
        "summary": report["summary"],
        "paired_task_pass_delta_vs_lexical_k5": (
            report["paired_task_pass_delta_vs_lexical_k5"]
        ),
        "independent_e2_qualified": False,
        "publication_gate_passed": False,
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
