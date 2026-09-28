# ruff: noqa: E501
"""Generate identity-disjoint supported-only V6F corpora for experiment #406."""

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

from benchmarks.operation_routing_v6f_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts  # noqa: E402
from scripts.generate_operation_routing_v6e import (  # noqa: E402
    EVAL_ACTIONS,
    TEMPORAL,
    WRAPPERS,
)

QUERY_PREFIX = {
    "en": "Route this concrete request: ",
    "ko": "이 구체적 요청을 라우팅해줘: ",
    "es": "Enruta esta solicitud concreta: ",
    "ja": "この具体的な依頼をルーティングして: ",
    "de": "Route diese konkrete Anfrage: ",
    "mixed": "이 concrete request를 route해줘: ",
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
                        "id": (
                            f"{prefix}-supported-{slug}-{language}-{variant + 1}"
                        ),
                        "query": _query(spec.leaf, language, obj, variant),
                        "expected": spec.route_id,
                        "category": "supported",
                        "language": language,
                    }
                )
    return rows


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v6f-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v6f-confirm"
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

    rows = _supported(specs, prefix)
    if len(rows) != 228:
        raise ValueError("V6F supported count drifted")
    if any(row["expected"] is None for row in rows):
        raise ValueError("V6F is a supported-only retrieval diagnostic")

    manifest = {
        "role": role,
        "case_count": len(rows),
        "supported_cases": len(rows),
        "near_domain_cases": 0,
        "out_of_domain_cases": 0,
        "route_count": len(contracts),
        "tool_count": len(registry.tools()),
        "endpoint_counts": sorted(
            len(tool.endpoints) for tool in registry.tools()
        ),
        "languages": list(LANGUAGES),
        "adapters": sorted(
            {contract.adapter or "native" for contract in contracts.values()}
        ),
        "evaluation_wording_bank": (
            "V6F reuses the frozen V6E operation/wrapper grammar with a new "
            "natural routing prefix and new registry identities; it is "
            "supported-only and must be exact-string disjoint from V6A-E."
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
