"""Screen stronger multilingual embedding backbones on the fixed v4 DEV corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import analyze_dual_view_embedding_v4 as dual  # noqa: E402

MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "e5-base": {
        "model_name": "intfloat/multilingual-e5-base",
        "revision": "d13f1b27baf31030b7fd040960d60d909913633f",
        "trust_remote_code": False,
        "query_prefix": "query: ",
        "document_prefix": "passage: ",
    },
    "gte-multilingual-base": {
        "model_name": "Alibaba-NLP/gte-multilingual-base",
        "revision": "087a024525fd6e2fe749cb4679d218d8bcc95bdd",
        "trust_remote_code": True,
        "query_prefix": "",
        "document_prefix": "",
    },
    "bge-m3": {
        "model_name": "BAAI/bge-m3",
        "revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "trust_remote_code": False,
        "query_prefix": "",
        "document_prefix": "",
    },
}


def _prefixed(prefix: str, texts: list[str]) -> list[str]:
    return [f"{prefix}{text}" for text in texts]


def _build_embedders(model_id: str):
    if model_id not in MODEL_CONFIGS:
        raise ValueError(
            f"unknown model_id {model_id!r}; expected one of "
            f"{sorted(MODEL_CONFIGS)}"
        )
    config = MODEL_CONFIGS[model_id]
    from sentence_transformers import SentenceTransformer

    kwargs: dict[str, Any] = {
        "trust_remote_code": bool(config["trust_remote_code"]),
    }
    if config["revision"]:
        kwargs["revision"] = str(config["revision"])

    model = SentenceTransformer(str(config["model_name"]), **kwargs)

    def _encode(texts: list[str], *, prefix: str) -> list[list[float]]:
        prepared = _prefixed(prefix, texts)
        vectors = model.encode(
            prepared,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def static_embedder(texts: list[str]) -> list[list[float]]:
        return _encode(
            texts,
            prefix=str(config["document_prefix"]),
        )

    def query_embedder(texts: list[str]) -> list[list[float]]:
        return _encode(
            texts,
            prefix=str(config["query_prefix"]),
        )

    return config, static_embedder, query_embedder


def run(
    cases: list[dict[str, Any]],
    *,
    model_id: str,
) -> dict[str, Any]:
    config, static_embedder, query_embedder = _build_embedders(model_id)
    result = dual.analyze(
        cases,
        static_embedder=static_embedder,
        query_embedder=query_embedder,
    )
    result["backbone_screen"] = {
        "model_id": model_id,
        **config,
        "source_experiment": 242,
        "historical_control": {
            "model": (
                "sentence-transformers/"
                "paraphrase-multilingual-MiniLM-L12-v2"
            ),
            "best_raw_supported_exact_route_accuracy": 0.75,
            "best_canonical_supported_exact_route_accuracy": (
                0.5477430555555556
            ),
            "historical_run": 36321806711,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model-id", choices=sorted(MODEL_CONFIGS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    value = json.loads(args.corpus.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(
        not isinstance(item, dict) for item in value
    ):
        raise ValueError("corpus must be a JSON object list")

    result = run(value, model_id=args.model_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    raw = result["summary"]["raw_profiles"]
    best_raw = max(
        (
            (name, float(profile["supported_exact_route_accuracy"]))
            for name, profile in raw.items()
        ),
        key=lambda item: item[1],
    )
    print(
        json.dumps(
            {
                "model_id": args.model_id,
                "best_raw_strategy": best_raw[0],
                "best_raw_supported_exact_route_accuracy": best_raw[1],
                "best_canonical": result["summary"][
                    "best_canonical_false_budget_12"
                ],
                "screening_gate_pass_count": result["summary"][
                    "screening_gate_pass_count"
                ],
                "latency": result["summary"][
                    "query_embedding_plus_all_scoring_latency_ms"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
