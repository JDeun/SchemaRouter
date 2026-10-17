"""Real, CPU-local E5 vs lexical vs authorized RRF-K5 *retrieval* DEV.

No agent is run. Disclosed synthetic multilingual corpus, not independent
E2 task utility, not calibrated no-fit, not a product default or release gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    E5CachedEmbedder,
    EmbeddingDecisionBackend,
    EndpointSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from scripts.evaluate_multilingual_embedding_cpu_dev import (
    load_development_corpus,
    percentile,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)
from scripts.research_authorized_hybrid_fixed5 import AuthorizedHybridFixed5Selector

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks/multilingual-embedding-cpu-dev-20261015.json"
MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
ARMS = ("lexical_k5", "e5_k5", "hybrid_rrf60_k5")
LANGUAGES = ("en", "ko", "ja", "es", "de", "mixed")
PRINCIPAL = PrincipalContext(subject="cpu-dev-eval-only", roles=("dev_evaluator",))


def build_source_router(corpus: dict[str, Any]) -> SchemaRouter:
    """Native endpoint descriptions from exactly the pinned 13-route DEV input."""
    options = corpus["catalog"]
    if type(options) is not list or len(options) != 13:
        raise ValueError("native DEV catalog size drift")
    grouped: dict[str, list[EndpointSpec]] = defaultdict(list)
    ids: set[str] = set()
    for option in options:
        if type(option) is not dict or set(option) != {"id", "description"}:
            raise ValueError("untrusted DEV source catalog")
        raw_id = option["id"]
        desc = option["description"]
        if (
            type(raw_id) is not str or raw_id.count(".") != 1
            or type(desc) is not str or not desc.strip()
            or raw_id in ids
        ):
            raise ValueError("bad or duplicate source-native route")
        ids.add(raw_id)
        tool, endpoint = raw_id.split(".")
        grouped[tool].append(EndpointSpec(
            name=endpoint, description=desc, read_only=True,
        ))
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                name="synthetic-dev-read-only",
                effect="allow", operation="*.*", roles_any=("dev_evaluator",),
            ),),
        ),
    )
    for tool, endpoints in grouped.items():
        router.add_tool(ToolSpec(
            name=tool, description="Read-only published synthetic DEV operation",
            endpoints=endpoints,
        ))
    if sum(len(t.endpoints) for t in router.registry.tools()) != len(ids):
        raise ValueError("native DEV registry construction drift")
    return router


def run_three_arm_dev(
    corpus: dict[str, Any],
    corpus_sha256: str,
    backend: EmbeddingDecisionBackend,
) -> dict[str, Any]:
    """Score retrieval only; no fixture grader or agent execution authority."""
    if (
        corpus.get("surface") != "prospective_development_only"
        or corpus.get("validation_or_holdout_claim_allowed") is not False
        or type(corpus_sha256) is not str or len(corpus_sha256) != 64
        or any(c not in "0123456789abcdef" for c in corpus_sha256)
        or len(corpus.get("cases", [])) != 84
        or set(corpus.get("languages", [])) != set(LANGUAGES)
    ):
        raise ValueError("cannot qualify an unverified or non-DEV corpus")
    # Fingerprint the exact already-verified content as an input commitment;
    # no corpus mutation, task-ID cherry-picking or generator side effects.
    router = build_source_router(corpus)
    rows: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for case in corpus["cases"]:
        query, language = case["query"], case["language"]
        if language not in LANGUAGES:
            raise ValueError("unregistered DEV task language")
        view = capture_authorized_agent_tool_surface(
            router, query, principal=PRINCIPAL,
        )
        visible = view.visible_route_ids
        if len(visible) != 13:
            raise ValueError("source authorization drift or unavailable routes")
        start = time.perf_counter_ns()
        native = router.retrieve_authorized(query, principal=PRINCIPAL, k=5)
        lexical = [candidate.route_id for candidate in native.candidates]
        lex_ms = (time.perf_counter_ns() - start) / 1e6
        semantic_selector = AuthorizedFixed5DecisionSelector(view, backend)
        start = time.perf_counter_ns()
        semantic = semantic_selector(query, visible)
        semantic_ms = (time.perf_counter_ns() - start) / 1e6
        hybrid_selector = AuthorizedHybridFixed5Selector(view, backend)
        start = time.perf_counter_ns()
        hybrid = hybrid_selector(query, visible)
        hybrid_ms = (time.perf_counter_ns() - start) / 1e6
        choices = {
            "lexical_k5": (lexical, lex_ms),
            "e5_k5": (semantic, semantic_ms),
            "hybrid_rrf60_k5": (hybrid, hybrid_ms),
        }
        for arm, (ranked, elapsed) in choices.items():
            if (
                len(ranked) != 5 or len(set(ranked)) != 5
                or not set(ranked).issubset(visible)
                or not math.isfinite(elapsed) or elapsed < 0
            ):
                raise ValueError("unbounded / unregistered / drifted K5 output")
            supported = case["kind"] == "supported"
            expected = case["expected_route"]
            if (supported and expected not in visible) or (
                not supported and expected is not None
            ):
                raise ValueError("task-native source or supported label drift")
            rows[arm].append({
                "language": language,
                "kind": case["kind"],
                "hit_at_1": (ranked[0] == expected) if supported else None,
                "hit_at_5": (expected in ranked) if supported else None,
                "nonempty_unsupported": not supported and bool(ranked),
                "selection_latency_ms": elapsed,
            })
        view.assert_source_unchanged()

    results: dict[str, Any] = {}
    for arm, values in rows.items():
        per_language = {}
        for lang in LANGUAGES:
            subset = [v for v in values if v["language"] == lang]
            if len(subset) != 14:
                raise ValueError("DEV language denominators drifted")
            positives = [v for v in subset if v["kind"] == "supported"]
            negatives = [v for v in subset if v["kind"] == "unsupported"]
            if len(positives) != 8 or len(negatives) != 6:
                raise ValueError("supported/OOD denominators drifted")
            per_language[lang] = {
                "supported": len(positives),
                "unsupported": len(negatives),
                "supported_recall_at_1": sum(v["hit_at_1"] for v in positives) / 8,
                "supported_recall_at_5": sum(v["hit_at_5"] for v in positives) / 8,
                "unsupported_nonempty_candidate_rate": (
                    sum(v["nonempty_unsupported"] for v in negatives) / 6
                ),
            }
        positives = [v for v in values if v["kind"] == "supported"]
        negatives = [v for v in values if v["kind"] == "unsupported"]
        latencies = [v["selection_latency_ms"] for v in values]
        results[arm] = {
            "supported": len(positives),
            "unsupported": len(negatives),
            "supported_recall_at_1": statistics.fmean(v["hit_at_1"] for v in positives),
            "supported_recall_at_5": statistics.fmean(v["hit_at_5"] for v in positives),
            "unsupported_nonempty_candidate_rate": statistics.fmean(
                v["nonempty_unsupported"] for v in negatives
            ),
            "selection_latency_ms_p50": percentile(latencies, 50),
            "selection_latency_ms_p95": percentile(latencies, 95),
            "languages": per_language,
        }
    return {
        "schema_version": 1,
        "issue": 1477,
        "surface": "prospective_development_only",
        "evidence_tier": "REAL_E5_CPU_RETRIEVAL_DEV_ONLY",
        "independent_e2_qualified": False,
        "agent_task_success_measured": False,
        "real_model_routing_measured": True,
        "calibrated_no_fit": False,
        "product_default_promoted": False,
        "publication_gate_passed": False,
        "source_corpus_sha256": corpus_sha256,
        "catalog_size": 13,
        "case_count": 84,
        "fixed_k": 5,
        "arms": list(ARMS),
        "results": results,
        "limitation": (
            "Previously disclosed synthetic DEV retrieval only. Unsupported "
            "nonempty shortlist is not a provider call or calibrated false accept. "
            "Semantic cache is warm from earlier requests; hybrid ranking "
            "also performs lexical and semantic retrieval, so p95 includes "
            "different work and is descriptive, not a matched agent budget."
        ),
    }


def real_cpu_backend() -> tuple[EmbeddingDecisionBackend, dict[str, Any]]:
    """Actual local pinned model inference; NEVER loads weights for offline tests."""
    import resource

    import torch
    from sentence_transformers import SentenceTransformer

    torch.manual_seed(20261017)
    torch.set_num_threads(min(os.cpu_count() or 1, 4))
    load_start = time.perf_counter()
    model = SentenceTransformer(
        MODEL_ID, revision=MODEL_REVISION, device="cpu",
        trust_remote_code=False,
    )
    model.eval()
    if model.device.type != "cpu":
        raise RuntimeError("model was not loaded entirely on CPU")

    def encode(texts: list[str]) -> list[list[float]]:
        # The existing E5CachedEmbedder adds query/pass prefixes.
        vectors = model.encode(
            texts, batch_size=16, normalize_embeddings=True,
            show_progress_bar=False, convert_to_numpy=True,
        )
        return vectors.tolist()

    return (
        EmbeddingDecisionBackend(
            E5CachedEmbedder(encode, max_cached_passages=500)
        ),
        {
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "device": "cpu",
            "encoder_dimension": model.get_sentence_embedding_dimension(),
            "model_load_ms": (time.perf_counter() - load_start) * 1000,
            "torch": torch.__version__,
            "python": platform.python_version(),
            "runner": platform.platform(),
            "rss_mb_linux_before_scoring": resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss / 1024,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("validate", "real-e5-cpu"), required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/e5-rrf-dev/report.json"))
    args = parser.parse_args()
    corpus, sha = load_development_corpus(CORPUS)
    build_source_router(corpus)
    if args.mode == "validate":
        print(json.dumps({"corpus_sha256": sha, "cases": len(corpus["cases"]),
                          "evidence_tier": "DEV_INPUT_ONLY"}))
        return
    backend, runtime = real_cpu_backend()
    report = run_three_arm_dev(corpus, sha, backend)
    source_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=10,
    ).stdout.strip()
    if len(source_revision) != 40 or any(c not in "0123456789abcdef" for c in source_revision):
        raise RuntimeError("source SHA cannot be authenticated")
    report["source_revision"] = source_revision
    report["runtime"] = runtime
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source_revision": source_revision,
        "evidence_tier": report["evidence_tier"],
        "summary": report["results"],
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
