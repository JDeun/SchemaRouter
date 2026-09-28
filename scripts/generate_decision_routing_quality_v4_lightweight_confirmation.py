"""Generate a new independent fresh surface for the frozen lightweight candidate."""

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

SURFACE_VERSION = "lightweight-bge-gte-operational-envelope-v1"
REFERENCE_SEED = "operation-routing-quality-v4-development-2026-09-27"
FRESH_SEED = "operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a"

WRAPPERS: dict[str, tuple[str, ...]] = {
    "en": (
        "Operational note — please act on this item: {query}",
        "For the current workflow, I need this done: {query}",
        "A separate task needs handling now: {query}",
    ),
    "ko": (
        "업무 메모입니다. 이 항목을 처리해 주세요: {query}",
        "현재 작업 흐름에서 필요한 요청입니다: {query}",
        "별도 작업으로 다음을 진행해 주세요: {query}",
    ),
    "es": (
        "Nota operativa — gestiona este punto: {query}",
        "Para el flujo actual necesito lo siguiente: {query}",
        "Hay una tarea aparte que debe hacerse ahora: {query}",
    ),
    "ja": (
        "作業メモです。この項目を処理してください: {query}",
        "現在の作業で必要な依頼です: {query}",
        "別件として次を進めてください: {query}",
    ),
    "de": (
        "Arbeitsnotiz — bearbeite bitte diesen Punkt: {query}",
        "Für den aktuellen Ablauf brauche ich Folgendes: {query}",
        "Eine separate Aufgabe soll jetzt erledigt werden: {query}",
    ),
    "mixed": (
        "ops 메모: 이 item을 처리해줘 — {query}",
        "current workflow에서 필요한 request야: {query}",
        "별도 task로 다음을 진행해줘: {query}",
    ),
}

_PREVIOUS_SURFACES: tuple[
    tuple[str, str, str, dict[str, tuple[str, ...]]],
    ...,
] = (
    (
        "zero-false-confirmation-wrappers-v1",
        "operation-routing-quality-v4-zero-false-confirmation-2026-09-28-a",
        "7255e4875f92eff4f31cc02d46292ba2b59d9a950d8e18fc48c825cf4886ef1b",
        {
            "en": (
                "Request context: {query}",
                "Please handle this request: {query}",
                "Here is the request I need handled: {query}",
            ),
            "ko": (
                "요청 내용입니다: {query}",
                "다음 요청을 처리해 주세요: {query}",
                "이 요청을 확인해 주세요: {query}",
            ),
            "es": (
                "Contexto de la solicitud: {query}",
                "Por favor, atiende esta solicitud: {query}",
                "Esta es la solicitud que necesito resolver: {query}",
            ),
            "ja": (
                "依頼内容です: {query}",
                "次の依頼を処理してください: {query}",
                "この依頼を確認してください: {query}",
            ),
            "de": (
                "Anfragekontext: {query}",
                "Bitte bearbeite diese Anfrage: {query}",
                "Hier ist die zu bearbeitende Anfrage: {query}",
            ),
            "mixed": (
                "request 내용: {query}",
                "please 이 요청을 처리해줘: {query}",
                "다음 request를 확인해줘: {query}",
            ),
        },
    ),
    (
        "learned-verifier-confirmation-wrappers-v1",
        "operation-routing-quality-v4-learned-verifier-confirmation-2026-09-28-a",
        "c08068e7c68d466b04c96433abd17a6b5da62eaa47969b536f8551ed9db201c6",
        {
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
        },
    ),
)


def _wrapper_index(surface: str, seed: str, case_id: str, count: int) -> int:
    digest = hashlib.sha256(f"{surface}|{seed}|{case_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % count


def _transform(
    *,
    seed: str,
    surface: str,
    wrappers_by_language: dict[str, tuple[str, ...]],
    add_split_marker: bool,
) -> list[dict[str, object]]:
    cases = v4._build(seed)
    transformed: list[dict[str, object]] = []
    for case in cases:
        language = str(case["language"])
        wrappers = wrappers_by_language[language]
        template = wrappers[
            _wrapper_index(surface, seed, str(case["id"]), len(wrappers))
        ]
        item = dict(case)
        item["query"] = template.format(query=str(case["query"]))
        item["confirmation_surface_version"] = surface
        transformed.append(item)
    return transformed


def _payload_sha(cases: list[dict[str, object]]) -> str:
    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_confirmation() -> tuple[list[dict[str, object]], dict[str, object]]:
    reference = v4._build(REFERENCE_SEED)
    reference_normalized = {
        v4._normalize(str(case["query"]))
        for case in reference
    }

    previous_normalized: dict[str, set[str]] = {}
    previous_verified: dict[str, bool] = {}
    for surface, seed, expected_sha, wrappers in _PREVIOUS_SURFACES:
        prior = _transform(
            seed=seed,
            surface=surface,
            wrappers_by_language=wrappers,
            add_split_marker=False,
        )
        actual_sha = _payload_sha(prior)
        if actual_sha != expected_sha:
            raise ValueError(
                f"could not reproduce prior surface {surface}: "
                f"{actual_sha} != {expected_sha}"
            )
        previous_verified[surface] = True
        previous_normalized[surface] = {
            v4._normalize(str(case["query"]))
            for case in prior
        }

    transformed = _transform(
        seed=FRESH_SEED,
        surface=SURFACE_VERSION,
        wrappers_by_language=WRAPPERS,
        add_split_marker=True,
    )
    # Reuse the v4 structural/label-leak validation. This surface is confirmation-only.
    v4._validate(transformed)

    normalized = {
        v4._normalize(str(case["query"]))
        for case in transformed
    }
    if len(normalized) != len(transformed):
        raise ValueError("fresh confirmation contains duplicate normalized queries")

    reference_overlap = len(reference_normalized.intersection(normalized))
    if reference_overlap:
        raise ValueError(
            f"fresh confirmation overlaps canonical DEV: {reference_overlap}"
        )

    prior_overlap: dict[str, int] = {}
    for surface, prior_set in previous_normalized.items():
        count = len(prior_set.intersection(normalized))
        prior_overlap[surface] = count
        if count:
            raise ValueError(
                f"fresh confirmation overlaps prior surface {surface}: {count}"
            )

    metadata: dict[str, object] = {
        "surface_version": SURFACE_VERSION,
        "seed": FRESH_SEED,
        "reference_seed": REFERENCE_SEED,
        "case_count": len(transformed),
        "normalized_exact_overlap_with_reference_dev": reference_overlap,
        "normalized_exact_overlap_with_prior_fresh_surfaces": prior_overlap,
        "prior_surface_regeneration_verified": previous_verified,
        "tuning_eligible": False,
        "calibration_or_blind": False,
    }
    return transformed, metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    cases, metadata = build_confirmation()
    payload = json.dumps(cases, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    manifest = {
        "cycle": "0.11-operation-routing-quality-v4",
        "role": "fresh_surface_development_confirmation",
        "candidate": "lightweight-bge-negative-gte-executable-v1",
        "source_revision": args.source_revision,
        "corpus_sha256": digest,
        "supported_operation_cases": 1152,
        "near_domain_unsupported_operation_cases": 576,
        "out_of_domain_cases": 72,
        "languages": {language: 300 for language in v4.LANGUAGES},
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
                "reference_overlap": metadata[
                    "normalized_exact_overlap_with_reference_dev"
                ],
                "prior_overlap": metadata[
                    "normalized_exact_overlap_with_prior_fresh_surfaces"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
