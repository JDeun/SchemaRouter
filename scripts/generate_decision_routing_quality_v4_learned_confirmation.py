"""Generate a new fresh-surface DEV for the frozen learned verifier.

This generator uses a new seed and a new wrapper family. It never reads the failed
#270 confirmation artifact and only checks normalized exact overlap against the
original tuning DEV.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import generate_decision_routing_quality_v4 as v4  # noqa: E402

SURFACE_VERSION = "learned-verifier-confirmation-wrappers-v1"
WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "User task — {query}",
        "I need the following handled: {query}",
        "Can this request be processed? {query}",
    ),
    "ko": (
        "사용자 작업: {query}",
        "아래 내용을 처리하려고 합니다: {query}",
        "이 요청을 수행할 수 있나요? {query}",
    ),
    "es": (
        "Tarea del usuario — {query}",
        "Necesito gestionar lo siguiente: {query}",
        "¿Se puede procesar esta solicitud? {query}",
    ),
    "ja": (
        "ユーザータスク: {query}",
        "次の内容を処理したいです: {query}",
        "このリクエストは処理できますか: {query}",
    ),
    "de": (
        "Benutzeraufgabe — {query}",
        "Ich möchte Folgendes bearbeiten lassen: {query}",
        "Kann diese Anfrage verarbeitet werden? {query}",
    ),
    "mixed": (
        "user 작업 — {query}",
        "이 following request를 처리하고 싶어: {query}",
        "can this 요청 be handled? {query}",
    ),
}


def _wrapper_index(seed: str, case_id: str, count: int) -> int:
    digest = hashlib.sha256(
        f"{SURFACE_VERSION}|{seed}|{case_id}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big") % count


def build_confirmation(
    *,
    seed: str,
    reference_seed: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    reference = v4._build(reference_seed)
    cases = v4._build(seed)
    reference_normalized = {
        v4._normalize(str(case["query"]))
        for case in reference
    }

    transformed: list[dict[str, object]] = []
    for case in cases:
        language = str(case["language"])
        wrappers = WRAPPERS.get(language)
        if not wrappers:
            raise ValueError(
                f"missing learned confirmation wrapper for {language!r}"
            )
        template = wrappers[
            _wrapper_index(seed, str(case["id"]), len(wrappers))
        ]
        item = dict(case)
        item["query"] = template.format(query=str(case["query"]))
        item["confirmation_surface_version"] = SURFACE_VERSION
        transformed.append(item)

    v4._validate(transformed)
    transformed_normalized = {
        v4._normalize(str(case["query"]))
        for case in transformed
    }
    overlap = reference_normalized.intersection(transformed_normalized)
    if overlap:
        raise ValueError(
            "learned-verifier fresh surface overlaps tuning DEV: "
            f"{len(overlap)}"
        )
    if len(transformed_normalized) != len(transformed):
        raise ValueError(
            "learned-verifier fresh surface contains duplicate queries"
        )

    metadata: dict[str, object] = {
        "surface_version": SURFACE_VERSION,
        "seed": seed,
        "reference_seed": reference_seed,
        "normalized_exact_overlap_with_reference_dev": 0,
        "case_count": len(transformed),
        "distinct_from_failed_270_by_seed_and_surface_version": True,
        "failed_270_artifact_read": False,
    }
    return transformed, metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--reference-seed", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    cases, metadata = build_confirmation(
        seed=args.seed,
        reference_seed=args.reference_seed,
    )
    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(payload.encode()).hexdigest()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    manifest = {
        "cycle": "0.11-operation-routing-quality-v4",
        "role": "fresh_surface_development_confirmation",
        "candidate": "frozen-hgb-winner-verifier-v1",
        "source_revision": args.source_revision,
        "corpus_sha256": digest,
        "supported_operation_cases": 1152,
        "near_domain_unsupported_operation_cases": 576,
        "out_of_domain_cases": 72,
        "languages": {language: 300 for language in v4.LANGUAGES},
        "tuning_eligible": False,
        "calibration_or_blind": False,
        **metadata,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": len(cases),
                "corpus_sha256": digest,
                "surface_version": SURFACE_VERSION,
                "normalized_exact_overlap_with_reference_dev": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
