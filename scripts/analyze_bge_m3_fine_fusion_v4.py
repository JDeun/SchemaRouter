"""Fine-sweep BGE-M3 dual-view fusion weights on fixed v4 DEV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import analyze_dual_view_embedding_v4 as dual  # noqa: E402
import analyze_embedding_backbone_screen_v4 as screen  # noqa: E402

SCHEMA_WEIGHTS = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
FINE_STRATEGIES = {
    f"fusion_schema_{weight:.2f}": weight
    for weight in SCHEMA_WEIGHTS
}


def run(cases: list[dict]) -> dict:
    _config, static_embedder, query_embedder = screen._build_embedders("bge-m3")
    original = dict(dual.WEIGHTED_STRATEGIES)
    try:
        dual.WEIGHTED_STRATEGIES = dict(FINE_STRATEGIES)
        result = dual.analyze(
            cases,
            static_embedder=static_embedder,
            query_embedder=query_embedder,
        )
    finally:
        dual.WEIGHTED_STRATEGIES = original

    strict: list[dict] = []
    secondary: list[dict] = []
    for strategy, modes in result["winner_only_route_local_frontiers"].items():
        if strategy not in FINE_STRATEGIES:
            continue
        points = modes["none"]
        for point in points:
            if int(point["false_budget"]) == 6:
                strict.append(point)
            elif int(point["false_budget"]) == 12:
                secondary.append(point)

    strict.sort(
        key=lambda item: (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            int(item["wrong_supported"]),
            str(item["strategy"]),
        )
    )
    secondary.sort(
        key=lambda item: (
            -float(item["supported_exact_route_accuracy"]),
            int(item["false_routes"]),
            int(item["wrong_supported"]),
            str(item["strategy"]),
        )
    )
    latency_p95 = result["summary"][
        "query_embedding_plus_all_scoring_latency_ms"
    ]["p95"]
    passes = [
        point for point in strict
        if float(point["supported_exact_route_accuracy"]) >= 0.85
        and float(point["near_domain_unsupported_rejection"]) >= 0.97
        and float(point["canonical_false_route_rate"]) <= 0.01
        and latency_p95 is not None
        and float(latency_p95) <= 250.0
    ]

    result["fine_fusion"] = {
        "schema_weights": list(SCHEMA_WEIGHTS),
        "primary_false_budget": 6,
        "best_strict": strict[0] if strict else None,
        "best_secondary": secondary[0] if secondary else None,
        "strict_gate_pass_count": len(passes),
        "strict_gate_passes": passes,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or any(not isinstance(item, dict) for item in cases):
        raise ValueError("corpus must be a JSON object list")

    result = run(cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "best_strict": result["fine_fusion"]["best_strict"],
        "best_secondary": result["fine_fusion"]["best_secondary"],
        "strict_gate_pass_count": result["fine_fusion"]["strict_gate_pass_count"],
        "latency": result["summary"]["query_embedding_plus_all_scoring_latency_ms"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
