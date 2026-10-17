"""Real Qwen3+E5 *fixture-execution* agent DEV, never independent E2.

Uses the EXISTING FrozenCorpusExecutor via run_generated_episode, with real
CPU model inference only in the --mode real-cpu CLI. The small, previously
published multilingual retrieval corpus contains operation gold but no
provider-native arguments, responses or final-answer oracle: consequently this
experiment measures one-step synthetic operation completion/unsupported
no-call behavior, NOT factual final answers or live provider task success.
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

from schemarouter.decisions import DecisionBackend
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_NAME as AGENT_MODEL_ID,
)
from scripts.agent_utility_v7_dev_agent import (
    MODEL_REVISION as AGENT_MODEL_REVISION,
)
from scripts.agent_utility_v7_dev_agent import (
    SEED as AGENT_SEED,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    CORPUS,
    PRINCIPAL,
    build_source_router,
    real_cpu_backend,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_ID as E5_MODEL_ID,
)
from scripts.evaluate_authorized_e5_hybrid_cpu_dev import (
    MODEL_REVISION as E5_MODEL_REVISION,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import load_development_corpus
from scripts.research_agent_stage_evidence_e0 import (
    EVIDENCE_TIER,
    E0TraceProvenance,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)
from scripts.research_authorized_hybrid_fixed5 import (
    AuthorizedHybridFixed5Selector,
)
from scripts.research_paired_agent_fixed5_e0 import (
    ARMS,
    aggregate_paired_e0,
)

ROOT = Path(__file__).resolve().parents[1]
# Exact IDs from an already-published (NOT held-out) 2026-10-15 DEV file.
# Two supported + two unsupported cases per EN/KO/JA. No adaptive picking.
PILOT_IDS = (
    "supported-en-materials.search",
    "supported-en-papers.search",
    "unsupported-en-materials.delete_sample",
    "unsupported-en-papers.submit_paper",
    "supported-ko-weather.current",
    "supported-ko-inventory.lookup",
    "unsupported-ko-inventory.adjust_stock",
    "unsupported-ko-flights.book_ticket",
    "supported-ja-flights.search",
    "supported-ja-finance.convert_currency",
    "unsupported-ja-finance.transfer_money",
    "unsupported-ja-calendar.create_event",
)
PILOT_LANGUAGES = ("en", "ko", "ja")
PILOT_SOURCE_SHA256 = "dc8b0a7c9325c8767d9b323b24040e0dfe94f3fd170b829b6f977c0e629b2110"
FIXTURE_EVIDENCE = "E0_SYNTHETIC_ONE_STEP_REAL_AGENT_CPU_DEV_ONLY"
UNATTESTED_EVIDENCE = "E0_SYNTHETIC_ONE_STEP_UNATTESTED_AGENT_DEV_ONLY"


def verified_pilot_cases(
    corpus: dict[str, Any], digest: str,
) -> tuple[dict[str, Any], ...]:
    """Fail closed on any changed published source, order, gold or task count."""
    original, source_digest = load_development_corpus(CORPUS)
    if (
        type(corpus) is not dict or corpus != original
        or digest != source_digest
        or digest != PILOT_SOURCE_SHA256
        or type(corpus.get("cases")) is not list
    ):
        raise ValueError("original published synthetic DEV provenance drift")
    ids = {case["id"]: case for case in corpus["cases"]}
    if len(ids) != len(corpus["cases"]) or len(PILOT_IDS) != 12:
        raise ValueError("duplicate source case IDs")
    selected = tuple(ids[name] for name in PILOT_IDS)
    for lang in PILOT_LANGUAGES:
        items = [case for case in selected if case["language"] == lang]
        if (
            len(items) != 4
            or sum(case["kind"] == "supported" for case in items) != 2
            or sum(case["kind"] == "unsupported" for case in items) != 2
        ):
            raise ValueError("synthetic DEV pilot stratum drift")
    original_ids = {x["id"] for x in corpus["cases"]}
    if not set(PILOT_IDS).issubset(original_ids):
        raise ValueError("missing original authoring IDs")
    catalog_ids = {tool["id"] for tool in corpus["catalog"]}
    for case in selected:
        if (
            case["kind"] == "supported"
            and case["expected_route"] not in catalog_ids
        ) or (
            case["kind"] == "unsupported"
            and case["expected_route"] is not None
        ):
            raise ValueError("invalid synthetic operation gold")
    return selected


def one_step_fixture_task(case: dict[str, Any]) -> dict[str, Any]:
    """Post-selection deterministic fixture gold, NEVER given to selector."""
    supported = case["kind"] == "supported"
    route = case["expected_route"]
    return {
        "semantic_task_id": case["id"],
        "task_stratum": "one_step_supported" if supported else "unsupported_no_call",
        "query": case["query"],
        "language": case["language"],
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


def _verified_lexical(view: Any, query: str, offered: tuple[str, ...]) -> list[str]:
    view.assert_source_unchanged()
    if (
        query != view.original_query
        or offered != view.visible_route_ids
        or type(offered) is not tuple
    ):
        raise ValueError("lexical source-native scope changed")
    result = view.router.retrieve_authorized(
        query, principal=view._principal, k=5,
    )
    view.assert_source_unchanged()
    choices = [candidate.route_id for candidate in result.candidates]
    if (
        result.registry_version != view.witness[1]
        or len(choices) != 5
        or len(set(choices)) != 5
        or not set(choices).issubset(offered)
    ):
        raise ValueError("lexical fixed-K5 source validation failed")
    return choices


def run_paired_fixture_pilot(
    corpus: dict[str, Any],
    corpus_digest: str,
    agent: Any,
    backend: DecisionBackend,
    *,
    source_revision: str,
    hardware: str,
) -> dict[str, Any]:
    """Run unchanged existing agent loop, then aggregate sanitized E0 traces.

    Injected agents/backends must never claim real-model observations. Gold,
    internal state, raw prompts and task arguments are excluded from output.
    """
    cases = verified_pilot_cases(corpus, corpus_digest)
    if (
        type(source_revision) is not str or len(source_revision) != 40
        or any(c not in "0123456789abcdef" for c in source_revision)
        or type(hardware) is not str or not hardware.strip()
    ):
        raise ValueError("source revision or CPU hardware receipt invalid")

    router = build_source_router(corpus)
    hmac_key = secrets.token_bytes(32)
    split_digest = hashlib.sha256(json.dumps(
        PILOT_IDS, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    provenance = E0TraceProvenance(
        source_revision=source_revision,
        source_sha256=corpus_digest,
        hmac_key=hmac_key,
        seed=AGENT_SEED,
    )
    manifest = {
        "schema_version": 1,
        "evidence_tier": EVIDENCE_TIER,
        "independent_e2_qualified": False,
        "arms": list(ARMS),
        "source_revision": source_revision,
        "source_sha256": corpus_digest,
        "split_sha256": split_digest,
        "model_revision": (
            f"{AGENT_MODEL_ID}@{AGENT_MODEL_REVISION};"
            f"{E5_MODEL_ID}@{E5_MODEL_REVISION}"
        ),
        "model_runtime": "INJECTED_NOT_ATTESTED",
        "hardware": hardware,
        "split_name": "previously_published_multilingual_12case_dev",
        "seed": AGENT_SEED,
        "max_k": 5,
        "tasks": [],
    }
    runs = {arm: {
        "arm": arm,
        "evidence_tier": EVIDENCE_TIER,
        "rows": [],
    } for arm in ARMS}
    for key in (
        "source_revision", "source_sha256", "split_sha256", "model_revision",
        "model_runtime", "hardware", "split_name", "seed", "max_k",
    ):
        for arm in ARMS:
            runs[arm][key] = manifest[key]

    # The same existing frozen agent and same originally published tasks are
    # used for all conditions; rotate arm order to reduce warm-up bias.
    for index, case in enumerate(cases):
        task = one_step_fixture_task(case)
        # Use the identical canonical HMAC identity as sanitized_e0_trace.
        identity = hmac.new(
            hmac_key, case["id"].encode("utf-8"), "sha256",
        ).hexdigest()
        manifest["tasks"].append({
            "task_hmac_sha256": identity,
            "language": case["language"],
            "task_stratum": task["task_stratum"],
            "supported": task["supported"],
        })
        for offset in range(3):
            arm = ARMS[(index + offset) % 3]
            view = capture_authorized_agent_tool_surface(
                router, case["query"], principal=PRINCIPAL,
            )
            if len(view.visible_route_ids) != 13:
                raise ValueError("principal-visible catalog drift")
            if arm == "lexical_k5":
                def selector(query, offered, scoped=view):
                    return _verified_lexical(scoped, query, offered)
            elif arm == "e5_k5":
                selector = AuthorizedFixed5DecisionSelector(view, backend)
            else:
                selector = AuthorizedHybridFixed5Selector(view, backend)

            outcome = run_generated_episode(
                agent, router.registry, task,
                EXPERIMENTAL_FIXED5_CONDITION,
                experimental_candidate_selector=selector,
                experimental_agent_tool_surface=view,
                experimental_e0_trace_provenance=provenance,
            )
            stage = outcome["e0_stage_evidence"]
            if (
                stage["language"] != case["language"]
                or stage["task_hmac_sha256"] != identity
                or stage["supported"] is not task["supported"]
                or stage["unauthorized_destructive_executions"] != 0
                or len(stage["visible_candidate_counts"]) != 1
            ):
                raise ValueError("actual executor trace or safe source contract drift")
            runs[arm]["rows"].append(stage)

    report = aggregate_paired_e0(manifest, runs)
    if (
        report["task_count"] != len(PILOT_IDS)
        or report["independent_e2_qualified"] is not False
        or report["publication_gate_passed"] is not False
    ):
        raise ValueError("untrusted E0 summary attribution")
    report.update({
        "experimental_condition": EXPERIMENTAL_FIXED5_CONDITION,
        "evidence_tier": UNATTESTED_EVIDENCE,
        "real_e5_model_routing_measured": False,
        "real_qwen_agent_generation_measured": False,
        "live_provider_execution_measured": False,
        "factual_final_answer_correctness_measured": False,
        "source_corpus_sha256": corpus_digest,
        "source_split_sha256": split_digest,
        "original_published_cases": len(corpus["cases"]),
        "pilot_case_count": len(cases),
        "languages": list(PILOT_LANGUAGES),
        "agent_model_revision": AGENT_MODEL_REVISION,
        "e5_model_revision": E5_MODEL_REVISION,
        "fixed_k": 5,
        "limitations": [
            "All 12 cases come from previously published synthetic DEV; "
            "this is not independent E2.",
            "Original source has operation gold but no arguments, "
            "provider responses or final-answer oracle.",
            "FrozenCorpusExecutor grades one-step operation completion, "
            "not factual final answers.",
            "Unsupported cases require no executable tool and a REQUEST_MORE_TOOLS final response.",
            "Only 13 visible original routes; no 500-route or "
            "multi-step agent measurement.",
            "Synthetic tool execution is not native provider integration "
            "or authorized write dispatch.",
            "Injected backends and model stubs must never be labeled real model inference.",
        ],
    })
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", required=True, choices=("validate", "real-cpu"))
    p.add_argument("--out", type=Path, default=Path(
        "artifacts/agent-fixed5-qwen-e5-cpu-dev/report.json",
    ))
    args = p.parse_args()
    corpus, digest = load_development_corpus(CORPUS)
    cases = verified_pilot_cases(corpus, digest)
    if args.mode == "validate":
        print(json.dumps({
            "case_count": len(cases), "language": PILOT_LANGUAGES,
            "supported": 6, "unsupported": 6,
            "source_sha256": digest, "independent_e2_qualified": False,
        }))
        return

    # Genuine locally loaded pinned E5 and Qwen3 weights. Other callers
    # cannot set real_model flags through the injectable test helper.
    backend, e5_runtime = real_cpu_backend()
    from scripts.agent_utility_v7_dev_agent import (
        LocalQwenAgent,
        runtime_identity,
    )
    agent = LocalQwenAgent()
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    report = run_paired_fixture_pilot(
        corpus, digest, agent, backend,
        source_revision=revision, hardware=platform.platform(),
    )
    report["evidence_tier"] = FIXTURE_EVIDENCE
    report["real_e5_model_routing_measured"] = True
    report["real_qwen_agent_generation_measured"] = True
    report["source_revision"] = revision
    report["runtime"] = {
        "e5": e5_runtime,
        "qwen3_0_6b": runtime_identity(),
        "agent_model_id": AGENT_MODEL_ID,
        "agent_model_revision": AGENT_MODEL_REVISION,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence_tier": report["evidence_tier"],
        "source_revision": revision,
        "pilot_case_count": report["pilot_case_count"],
        "summary": report["summary"],
        "paired": report["paired_task_pass_delta_vs_lexical_k5"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
