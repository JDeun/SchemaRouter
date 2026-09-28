# ruff: noqa: E501
"""Generate identity-disjoint V6G corpora for experiment #408."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6g_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import ACTION_PHRASES, compile_registry_contracts  # noqa: E402
from benchmarks.schema_cross_encoder_membership import (  # noqa: E402
    BACKGROUND_DOCUMENTS,
    compile_tool_evidence_banks,
)
from scripts.generate_operation_routing_v6e import (  # noqa: E402
    CONFIRM_OOD,
    EVAL_ACTIONS,
    OOD,
    TEMPORAL,
    WRAPPERS,
)

ALL_TOOL_LEAVES = tuple(ACTION_PHRASES)

QUERY_PREFIX = {
    "en": "Resolve this request against the registered capabilities: ",
    "ko": "등록된 기능 기준으로 이 요청을 처리해줘: ",
    "es": "Resuelve esta solicitud contra las capacidades registradas: ",
    "ja": "登録済み機能に照らしてこの依頼を処理して: ",
    "de": "Bearbeite diese Anfrage anhand der registrierten Fähigkeiten: ",
    "mixed": "registered capability 기준으로 이 request 처리해줘: ",
}


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _object(spec: RouteCaseSpec, language: str) -> str:
    obj = spec.objects[language]
    if spec.temporal_scope:
        return f"{TEMPORAL[spec.temporal_scope][language]} {obj}"
    return obj


def _query(leaf: str, language: str, obj: str, variant: int) -> str:
    body = WRAPPERS[language][variant].format(
        obj=obj,
        action=EVAL_ACTIONS[leaf][language],
    )
    return f"{QUERY_PREFIX[language]}{body}"


def _supported(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        slug = spec.route_id.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            obj = _object(spec, language)
            for variant in range(2):
                rows.append(
                    {
                        "id": f"{prefix}-supported-{slug}-{language}-{variant + 1}",
                        "query": _query(spec.leaf, language, obj, variant),
                        "expected": spec.route_id,
                        "category": "supported",
                        "language": language,
                    }
                )
    return rows


def _by_tool(
    specs: tuple[RouteCaseSpec, ...],
) -> dict[str, list[RouteCaseSpec]]:
    result: dict[str, list[RouteCaseSpec]] = {}
    for spec in specs:
        result.setdefault(spec.route_id.split(".", 1)[0], []).append(spec)
    return result


def _near(
    specs: tuple[RouteCaseSpec, ...],
    prefix: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool, tool_specs in sorted(_by_tool(specs).items()):
        supported = {spec.leaf for spec in tool_specs}
        absent = [leaf for leaf in ALL_TOOL_LEAVES if leaf not in supported][:6]
        anchor = tool_specs[0]
        for language in LANGUAGES:
            obj = anchor.objects[language]
            for index, leaf in enumerate(absent):
                rows.append(
                    {
                        "id": f"{prefix}-near-{tool}-{language}-{index + 1}",
                        "query": _query(leaf, language, obj, index % 2),
                        "expected": None,
                        "category": "near_domain_unsupported_operation",
                        "language": language,
                        "unsupported_action": leaf,
                        "unsupported_family": f"{tool}.{leaf}",
                    }
                )
    return rows


def _ood(
    prefix: str,
    bank: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{prefix}-ood-{language}-{index}",
            "query": f"{QUERY_PREFIX[language]}{query}",
            "expected": None,
            "category": "out_of_domain",
            "language": language,
        }
        for language in LANGUAGES
        for index, query in enumerate(bank[language], start=1)
    ]


def _evidence_surfaces(registry: Any) -> set[str]:
    banks, unknown = compile_tool_evidence_banks(registry)
    if unknown:
        raise ValueError(f"V6G fixture contains unknown evidence tools: {sorted(unknown)}")
    surfaces = {document.text for document in BACKGROUND_DOCUMENTS}
    for bank in banks.values():
        surfaces.update(document.text for document in bank.supported)
        surfaces.update(document.text for document in bank.complement)
    return surfaces


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v6g-dev"
        ood_bank = OOD
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6g-confirm"
        ood_bank = CONFIRM_OOD
    else:
        raise ValueError("role must be development or confirmation")

    contracts = compile_registry_contracts(registry)
    expected = {spec.route_id for spec in specs}
    if set(contracts) != expected:
        raise ValueError(
            "route fixture mismatch "
            f"missing={sorted(expected-set(contracts))} "
            f"extra={sorted(set(contracts)-expected)}"
        )
    unknown = sorted(
        route for route, contract in contracts.items() if contract.leaf is None
    )
    if unknown:
        raise ValueError(
            f"evaluation endpoint leaves must be known before freeze: {unknown}"
        )

    rows = [
        *_supported(specs, prefix),
        *_near(specs, prefix),
        *_ood(prefix, ood_bank),
    ]
    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]

    if (
        len(rows) != 552
        or len(supported) != 228
        or len(near) != 252
        or len(ood) != 72
    ):
        raise ValueError("V6G category counts drifted")

    collisions = sorted(
        {str(row["query"]) for row in rows}.intersection(
            _evidence_surfaces(registry)
        )
    )
    if collisions:
        raise ValueError(
            f"evaluation wording collided with V6G evidence: {collisions[:3]}"
        )

    banks, unknown_tools = compile_tool_evidence_banks(registry)
    if unknown_tools:
        raise ValueError(f"unexpected unknown V6G tools: {sorted(unknown_tools)}")

    manifest = {
        "role": role,
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "route_count": len(contracts),
        "tool_count": len(registry.tools()),
        "endpoint_counts": sorted(
            len(tool.endpoints) for tool in registry.tools()
        ),
        "languages": list(LANGUAGES),
        "adapters": sorted(
            {contract.adapter or "native" for contract in contracts.values()}
        ),
        "supported_document_count": sum(
            len(bank.supported) for bank in banks.values()
        ),
        "complement_document_count": sum(
            len(bank.complement) for bank in banks.values()
        ),
        "background_document_count": len(BACKGROUND_DOCUMENTS),
        "evaluation_wording_bank": (
            "V6G uses a new capability-resolution prefix, new registry route "
            "identities, and the previously frozen multilingual operation grammar; "
            "queries are exact-string disjoint from V6A-F and V6G evidence."
        ),
        "corpus_sha256": hashlib.sha256(_canonical(rows)).hexdigest(),
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    freeze: dict[str, Any] = {}
    query_sets: dict[str, set[str]] = {}
    for role in ("development", "confirmation"):
        rows, manifest = build(role)
        query_sets[role] = {str(row["query"]) for row in rows}
        (args.out_dir / f"{role}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (args.out_dir / f"{role}-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        freeze[role] = manifest

    overlap = query_sets["development"].intersection(
        query_sets["confirmation"]
    )
    if overlap:
        raise ValueError(
            f"DEV/confirmation query identities overlap: {sorted(overlap)[:3]}"
        )

    (args.out_dir / "freeze-manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
