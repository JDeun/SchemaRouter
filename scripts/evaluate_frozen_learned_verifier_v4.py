"""Evaluate the exact serialized learned verifier without refitting."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import sklearn

from analyze_oof_learned_verifier_v4 import (
    CONTINUOUS_FEATURES,
    CATEGORICAL_FEATURES,
    _distribution,
    _evaluate_threshold,
    _extract_rows,
    _feature_vector,
)

PINNED_SKLEARN_VERSION = "1.7.2"
SELECTED_THRESHOLD = 0.50


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_manifest(
    model_path: Path,
    manifest: dict[str, object],
) -> None:
    if manifest.get("candidate") != "frozen-hgb-winner-verifier-v1":
        raise ValueError("unexpected frozen candidate")
    if manifest.get("selected_classifier") != "hgb":
        raise ValueError("unexpected frozen classifier")
    if float(manifest.get("selected_threshold", -1.0)) != SELECTED_THRESHOLD:
        raise ValueError("unexpected frozen threshold")
    if manifest.get("continuous_features") != list(CONTINUOUS_FEATURES):
        raise ValueError("continuous feature schema mismatch")
    if manifest.get("categorical_features") != list(CATEGORICAL_FEATURES):
        raise ValueError("categorical feature schema mismatch")
    expected_sha = str(manifest.get("model_sha256"))
    actual_sha = _sha256_file(model_path)
    if actual_sha != expected_sha:
        raise ValueError(
            f"frozen model SHA mismatch: expected {expected_sha}, got {actual_sha}"
        )
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("missing runtime manifest")
    if runtime.get("scikit_learn") != PINNED_SKLEARN_VERSION:
        raise ValueError("manifest sklearn version mismatch")
    if sklearn.__version__ != PINNED_SKLEARN_VERSION:
        raise RuntimeError(
            f"runtime sklearn mismatch: expected {PINNED_SKLEARN_VERSION}, "
            f"got {sklearn.__version__}"
        )


def evaluate_frozen(
    *,
    corpus_path: Path,
    model_path: Path,
    model_manifest_path: Path,
    dataset_role: str,
) -> dict[str, object]:
    manifest = json.loads(
        model_manifest_path.read_text(encoding="utf-8")
    )
    _verify_manifest(model_path, manifest)
    model_sha = str(manifest["model_sha256"])

    model = joblib.load(model_path)
    cases = json.loads(corpus_path.read_text(encoding="utf-8"))
    rows, extraction = _extract_rows(cases)
    x = np.asarray([_feature_vector(row) for row in rows], dtype=object)

    probabilities: list[float] = []
    prediction_latencies: list[float] = []
    classes = list(model.named_steps["classifier"].classes_)
    class_index = classes.index(1)
    for index in range(len(rows)):
        started = time.perf_counter_ns()
        probability = float(
            model.predict_proba(x[index : index + 1])[0][class_index]
        )
        prediction_latencies.append(
            (time.perf_counter_ns() - started) / 1_000_000
        )
        probabilities.append(probability)

    metrics = _evaluate_threshold(
        rows,
        probabilities,
        prediction_latencies,
        classifier_name="hgb-frozen",
        threshold=SELECTED_THRESHOLD,
    )
    authority_violations = sum(
        bool(row["authority_violation"]) for row in rows
    )
    metrics["quality_gate_pass"] = (
        bool(metrics["quality_gate_pass"])
        and authority_violations == 0
    )

    result: dict[str, object] = {
        "candidate": "frozen-hgb-winner-verifier-v1",
        "dataset_role": dataset_role,
        "model_sha256": model_sha,
        "selected_threshold": SELECTED_THRESHOLD,
        "authority_violations": authority_violations,
        "execution_errors": 0,
        "feature_extraction": extraction,
        "prediction_latency_ms": _distribution(prediction_latencies),
        "metrics": metrics,
        "policy": {
            "refit_performed": False,
            "verifier_can_select_route": False,
            "rank2_fallback": False,
            "pseudo_route": False,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--dataset-role", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate_frozen(
        corpus_path=args.corpus,
        model_path=args.model,
        model_manifest_path=args.model_manifest,
        dataset_role=args.dataset_role,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "dataset_role": result["dataset_role"],
                "model_sha256": result["model_sha256"],
                "quality_gate_pass": result["metrics"]["quality_gate_pass"],
                "supported_exact_route_accuracy": result["metrics"][
                    "supported_exact_route_accuracy"
                ],
                "near_domain_unsupported_rejection": result["metrics"][
                    "near_domain_unsupported_rejection"
                ],
                "out_of_domain_rejection": result["metrics"][
                    "out_of_domain_rejection"
                ],
                "false_route_rate": result["metrics"]["false_route_rate"],
                "combined_p95_ms": result["metrics"][
                    "combined_latency_ms"
                ]["p95"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
