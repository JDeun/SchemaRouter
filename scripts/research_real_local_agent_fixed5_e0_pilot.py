"""Pinned local Qwen agent × real E5 K5 source-native fixture DEV pilot.

This invokes the EXISTING generated-agent loop and deterministic fixture executor.
It is NOT real provider invocation, independent E2 or end-to-end agent factual success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import secrets
import subprocess
from pathlib import Path
from typing import Any

from schemarouter import PrincipalContext, SchemaRouter
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    canonical_bytes,
    run_generated_episode,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_NAME as AGENT_MODEL,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_REVISION as AGENT_REVISION,
)
from scripts.agent_utility_v7_dev_agent import SEED
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    CORPUS,
    LANGUAGES,
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
    aggregate_paired_e0,
)

ROOT = Path(__file__).resolve().parents[1]
# Source-frozen *already published* case IDs, never chosen from model outcomes.
# Two positive and two unsupported per language; same operations per language.
CASE_IDS = tuple(
    f"{kind}-{lang}-{route}"
    for lang in ("en", "ko", "ja")
    for kind, routes in (
        ("supported", ("materials.search", "weather.current")),
        ("unsupported", ("materials.delete_sample", "calendar.create_event")),
    )
    for route in routes
)
PILOT_SYSTEM_PROMPT = (
    "You are a tool-using agent. Use only the registered tools supplied. "
    "For a required tool, emit exactly <tool_call>{\"name\":\"tool__operation\","
    "\"arguments\":{}}</tool_call>, one call per turn, then wait for the "
    "observation. Never invent a tool. If the required capability is absent, "
    "answer exactly REQUEST_MORE_TOOLS. After completing a task, provide a "
    "short final response. No tool is authorized outside the listed schema."
)
def _cases(corpus: dict[str, Any], digest: str) -> tuple[list[dict[str, Any]], str]:
    original, authentic = load_development_corpus(CORPUS)
    if corpus != original or digest != authentic:
        raise ValueError("unverified published DEV bytes or gold mutation")
    if len(original["catalog"]) != 13 or len(original["cases"]) != 84:
        raise ValueError("published DEV cohort changed")
    if not set(("en", "ko", "ja")).issubset(set(LANGUAGES)):
        raise ValueError("language configuration changed")
    indexed = {case["id"]: case for case in original["cases"]}
    if len(indexed) != 84 or any(key not in indexed for key in CASE_IDS):
        raise ValueError("predeclared task ID set changed")
    chosen = [indexed[key] for key in CASE_IDS]
    for row in chosen:
        prefix, lang, route = row["id"].split("-", 2)
        if (
            row["kind"] != prefix or row["language"] != lang
            or (prefix == "supported" and row["expected_route"] != route)
            or (prefix == "unsupported" and row["expected_route"] is not None)
            or type(row["query"]) is not str or not row["query"].strip()
        ):
            raise ValueError("predeclared case label or route drift")
    frozen = {
        "origin_corpus_sha256": authentic,
        "case_ids": list(CASE_IDS),
        "fixture_recipe": "single_read_only_no_arguments_status_ok_v1",
        "system_prompt": PILOT_SYSTEM_PROMPT,
        "fixed_k": 5,
    }
    return chosen, hashlib.sha256(canonical_bytes(frozen)).hexdigest()


def _fixture_task(case: dict[str, Any]) -> dict[str, Any]:
    """The model/selector sees neither route gold nor fixture outputs."""
    supported = case["kind"] == "supported"
    expected = case["expected_route"]
    return {
        "semantic_task_id": case["id"],
        "task_stratum": "single_read_only" if supported else "unsupported_operation",
        "language": case["language"],
        "supported": supported,
        "query": case["query"],
        "required_routes": [expected] if supported else [],
        "executor_fixture": {
            "steps": [{
                "route_id": expected,
                "argument_rules": {},
                "observation": {"status": "ok", "answer": "FIXTURE_ONLY_NOT_LIVE"},
            }] if supported else [],
        },
    }


def _lexical_selector(view: Any):
    def select(query: str, source_ids: tuple[str, ...]) -> list[str]:
        view.assert_source_unchanged()
        if query != view.original_query or source_ids != view.visible_route_ids:
            raise ValueError("lexical candidate source and query drift")
        ranked = view.router.retrieve_authorized(
            query, principal=view._principal, k=5,
        )
        view.assert_source_unchanged()
        result = [candidate.route_id for candidate in ranked.candidates]
        if len(result) > 5 or len(set(result)) != len(result) or not set(result) <= set(source_ids):
            raise ValueError("lexical K5 result exceeds trusted source")
        return result
    return select


def run_agent_pilot(
    corpus: dict[str, Any],
    digest: str,
    *,
    backend: Any,
    agent: Any,
    source_revision: str,
    hmac_key: bytes,
    hardware: str,
) -> dict[str, Any]:
    """The injected-model path is permanently UNATTESTED mock E0 evidence."""
    if type(source_revision) is not str or len(source_revision) != 40 or any(
        c not in "0123456789abcdef" for c in source_revision
    ):
        raise ValueError("exact source revision required")
    if type(hmac_key) is not bytes or len(hmac_key) < 16:
        raise ValueError("private HMAC key required")
    if type(hardware) is not str or not hardware.strip():
        raise ValueError("hardware identity required")
    cases, split_sha = _cases(corpus, digest)
    router = build_source_router(corpus)
    if not isinstance(router, SchemaRouter) or not isinstance(PRINCIPAL, PrincipalContext):
        raise ValueError("native source or principal identity changed")
    provenance = E0TraceProvenance(
        source_revision=source_revision, source_sha256=digest,
        hmac_key=hmac_key, seed=SEED,
    )
    model_tag = f"{AGENT_MODEL}@{AGENT_REVISION}+intfloat/multilingual-e5-small"
    identity: dict[str, Any] = {
        "source_revision": source_revision,
        "source_sha256": digest,
        "split_sha256": split_sha,
        "model_revision": model_tag,
        "model_runtime": "injected-unattested-agent-and-backend",
        "hardware": hardware,
        "split_name": "predeclared_disclosed_multilingual_fixture_dev",
        "seed": SEED,
        "max_k": 5,
    }
    task_manifest = []
    arm_rows: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for case in cases:
        task = _fixture_task(case)
        for arm in ARMS:
            # Fresh actual native principal-scoped capture per arm, same
            # registry/query/principal: never pass fixture or expected tool.
            view = capture_authorized_agent_tool_surface(
                router, case["query"], principal=PRINCIPAL,
            )
            if len(view.visible_route_ids) != 13:
                raise ValueError("authorized original source inventory drift")
            selector = (
                _lexical_selector(view)
                if arm == "lexical_k5" else
                AuthorizedFixed5DecisionSelector(view, backend)
                if arm == "e5_k5" else
                AuthorizedHybridFixed5Selector(view, backend)
            )
            result = run_generated_episode(
                agent, router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
                system_prompt=PILOT_SYSTEM_PROMPT,
                experimental_candidate_selector=selector,
                experimental_agent_tool_surface=view,
                experimental_e0_trace_provenance=provenance,
            )
            # Existing agent loop must return its allowlisted scoped trace,
            # never a raw fixture/evaluator row or user/agent transcript.
            if any(name in result for name in (
                "query", "task_id", "semantic_task_id", "required_routes",
                "attempts", "turn_rows", "candidate_history", "final_text",
                "tool_arguments", "private_fixture",
            )):
                raise ValueError("unexpected agent private evidence in output")
            if "e0_stage_evidence" not in result:
                raise ValueError("missing trusted post-execution E0 grading")
            row = result["e0_stage_evidence"]
            if row["unauthorized_destructive_executions"] != 0:
                raise ValueError("unauthorized destructive tool executed: STOP")
            arm_rows[arm].append(row)
            if arm == "lexical_k5":
                task_manifest.append({
                    "task_hmac_sha256": row["task_hmac_sha256"],
                    "language": task["language"],
                    "task_stratum": task["task_stratum"],
                    "supported": task["supported"],
                })
    manifest = {
        "schema_version": 1,
        "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
        "independent_e2_qualified": False,
        "arms": list(ARMS),
        "tasks": task_manifest,
        **identity,
    }
    runs = {
        arm: {"arm": arm, "evidence_tier": "E0_SYNTHETIC_DEV_ONLY",
              "rows": arm_rows[arm], **identity}
        for arm in ARMS
    }
    summary = aggregate_paired_e0(manifest, runs)
    return {
        "schema_version": 1,
        "issue": 1477,
        "evidence_tier": "UNATTESTED_AGENT_AND_BACKEND_E0_DEV_ONLY",
        "real_agent_generation_measured": False,
        "real_e5_inference_measured": False,
        "independent_e2_qualified": False,
        "real_native_provider_execution": False,
        "actual_agent_final_answer_correctness_measured": False,
        "no_fit_calibrated": False,
        "product_default_promoted": False,
        "publication_gate_passed": False,
        "fixed_k": 5,
        "source_corpus_sha256": digest,
        "split_sha256": split_sha,
        "source_revision": source_revision,
        "cohort": {
            "tasks": len(cases),
            "supported": sum(c["kind"] == "supported" for c in cases),
            "unsupported": sum(c["kind"] == "unsupported" for c in cases),
            "languages": ["en", "ko", "ja"],
        },
        "agent_task_fixture_pass": summary,
        "limitations": (
            "Published synthetic DEV prompts, six supported and six unsupported. "
            "Existing generated-agent deterministic fixture advances a read-only "
            "step but does not invoke actual native providers or validate "
            "real-world factual final answers. Not independent E2."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("validate", "real-cpu"))
    parser.add_argument(
        "--out", type=Path,
        default=Path("artifacts/agent-fixed5-e5-qwen-dev/report.json"),
    )
    args = parser.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    chosen, split = _cases(corpus, digest)
    build_source_router(corpus)
    if args.mode == "validate":
        print(json.dumps({
            "evidence_tier": "PREDECLARED_DEV_NO_MODEL",
            "source_sha256": digest, "split_sha256": split,
            "cases": len(chosen), "supported": 6, "unsupported": 6,
        }))
        return

    source_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    backend, e5_runtime = real_cpu_backend()
    # Loaded only on this CLI path: injectable tests cannot claim real models.
    from scripts.agent_utility_v7_dev_agent import LocalQwenAgent, runtime_identity

    agent = LocalQwenAgent()
    report = run_agent_pilot(
        corpus, digest, backend=backend, agent=agent,
        source_revision=source_revision, hmac_key=secrets.token_bytes(32),
        hardware=platform.platform(),
    )
    report["evidence_tier"] = "REAL_LOCAL_QWEN_E5_FIXTURE_TASK_DEV_ONLY"
    report["real_agent_generation_measured"] = True
    report["real_e5_inference_measured"] = True
    report["agent_runtime"] = {
        "model_name": AGENT_MODEL,
        "revision": AGENT_REVISION,
        "device": "cpu",
        **runtime_identity(),
    }
    report["e5_runtime"] = e5_runtime
    report["source_revision"] = source_revision
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "source_revision": source_revision,
        "summary": report["agent_task_fixture_pass"]["summary"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
