"""Fit and serialize the preregistered HGB winner verifier exactly once."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import scipy
import sklearn
from analyze_oof_learned_verifier_v4 import (
    ACCEPTANCE_THRESHOLDS,
    CATEGORICAL_FEATURES,
    CONTINUOUS_FEATURES,
    RANDOM_STATE,
    _build_classifier,
    _extract_rows,
    _feature_vector,
)

EXPECTED_CORPUS_SHA256 = (
    "fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216"
)
SELECTED_CLASSIFIER = "hgb"
SELECTED_THRESHOLD = 0.50
PINNED_SKLEARN_VERSION = "1.7.2"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def freeze(
    *,
    corpus_path: Path,
    model_path: Path,
    manifest_path: Path,
    source_revision: str,
) -> dict[str, object]:
    corpus_sha = _sha256_file(corpus_path)
    if corpus_sha != EXPECTED_CORPUS_SHA256:
        raise ValueError(
            f"tuning corpus SHA mismatch: expected {EXPECTED_CORPUS_SHA256}, "
            f"got {corpus_sha}"
        )
    if sklearn.__version__ != PINNED_SKLEARN_VERSION:
        raise RuntimeError(
            f"scikit-learn version mismatch: expected "
            f"{PINNED_SKLEARN_VERSION}, got {sklearn.__version__}"
        )
    if SELECTED_THRESHOLD not in ACCEPTANCE_THRESHOLDS:
        raise RuntimeError("selected threshold is not preregistered")

    cases = json.loads(corpus_path.read_text(encoding="utf-8"))
    rows, extraction = _extract_rows(cases)
    x = np.asarray([_feature_vector(row) for row in rows], dtype=object)
    y = np.asarray(
        [int(row["verifier_target"]) for row in rows],
        dtype=int,
    )

    model = _build_classifier(SELECTED_CLASSIFIER)
    model.fit(x, y)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path, compress=3)
    model_sha = _sha256_file(model_path)

    manifest: dict[str, object] = {
        "candidate": "frozen-hgb-winner-verifier-v1",
        "source_experiment": 285,
        "work_item": 287,
        "source_revision": source_revision,
        "fit_once": True,
        "fit_cases": len(rows),
        "fit_match_targets": int(y.sum()),
        "fit_no_match_targets": int(len(y) - y.sum()),
        "fit_corpus_sha256": corpus_sha,
        "model_path": model_path.name,
        "model_sha256": model_sha,
        "selected_classifier": SELECTED_CLASSIFIER,
        "selected_threshold": SELECTED_THRESHOLD,
        "random_state": RANDOM_STATE,
        "continuous_features": list(CONTINUOUS_FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "runtime": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "joblib": joblib.__version__,
        },
        "feature_extraction": extraction,
        "policy": {
            "refit_allowed_in_confirmation": False,
            "query_text_feature": False,
            "language_feature": False,
            "label_feature": False,
            "verifier_can_select_route": False,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()

    manifest = freeze(
        corpus_path=args.corpus,
        model_path=args.model,
        manifest_path=args.manifest,
        source_revision=args.source_revision,
    )
    print(
        json.dumps(
            {
                "fit_cases": manifest["fit_cases"],
                "model_sha256": manifest["model_sha256"],
                "selected_threshold": manifest["selected_threshold"],
                "runtime": manifest["runtime"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
