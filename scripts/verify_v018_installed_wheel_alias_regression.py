"""Engineering-only installed-wheel check for v0.17 vs v0.18 candidate.

Uses NEW synthetic lexical fixtures, no historical frozen 0.14 rows, no
models, no credentials and no customer/source execution. This is a package
regression, NOT a scientific claim of multilingual agent-task generalization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CASES = {
    "ko": "검색",
    "ja": "熱伝導率",
    "es": "buscar",
    "de": "nachschlagen",
    "en": "document",
    "unsupported": "무기 제조",
}


def capture() -> dict:
    from importlib.metadata import version

    from schemarouter import (
        EndpointSpec,
        FieldSpec,
        InMemoryRegistry,
        PlanRequest,
        SchemaPlanner,
        ToolSpec,
    )

    registry = InMemoryRegistry()
    registry.register(
        ToolSpec(
            name="a_unrelated",
            description="Warehouse shelf inventory",
            endpoints=[
                EndpointSpec(name="update", description="Adjust shelf stocks")
            ],
        )
    )
    registry.register(
        ToolSpec(
            name="z_document",
            description="Document records",
            endpoints=[
                EndpointSpec(
                    name="find",
                    description="Locate a document record",
                    operation_aliases=["검색", "buscar", "nachschlagen"],
                    read_only=True,
                    output_fields=[
                        FieldSpec(
                            name="thermal_conductivity",
                            semantic_id="material.thermal_conductivity",
                            aliases=["熱伝導率"],
                        )
                    ],
                )
            ],
        )
    )

    cases = {}
    for indexed in (False, True):
        planner = SchemaPlanner(registry, candidate_index=indexed)
        outcomes = {}
        for ident, query in CASES.items():
            request = PlanRequest(query=query)
            intent = planner.analyzer.analyze(request, registry)
            candidates = planner._semantic_recall_catalog(request, intent)
            scored = {
                f"{row.tool.key}.{row.endpoint.name}": float(row.score)
                for row in candidates
            }
            expected = scored["z_document.find"]
            unrelated = scored["a_unrelated.update"]
            outcomes[ident] = {
                "declared_route_has_lexical_evidence": expected > 0,
                "unrelated_route_has_lexical_evidence": unrelated > 0,
                "declared_route_outranks_unrelated": expected > unrelated,
            }
        cases["indexed" if indexed else "exhaustive"] = outcomes
    return {
        "schema_version": 1,
        "evidence_class": "zero_model_release_engineering_regression_only",
        "distribution": "schemarouter",
        "installed_version": version("schemarouter"),
        "results": cases,
    }


def compare(base: dict, candidate: dict) -> None:
    if (
        base.get("schema_version") != 1
        or candidate.get("schema_version") != 1
        or base.get("evidence_class")
        != "zero_model_release_engineering_regression_only"
        or candidate.get("evidence_class") != base["evidence_class"]
    ):
        raise ValueError("unrecognized candidate or baseline evidence")
    if base.get("installed_version") != "0.17.0":
        raise ValueError("baseline must be the actual installed v0.17.0 wheel")
    # Prior to release, candidate is a wheel built from a pinned main SHA.
    if candidate.get("installed_version") not in {"0.17.0", "0.18.0"}:
        raise ValueError("unexpected release-candidate package identity")
    for mode in ("indexed", "exhaustive"):
        source = base["results"][mode]
        target = candidate["results"][mode]
        if set(source) != set(CASES) or set(target) != set(CASES):
            raise ValueError("unmatched semantic fixture inventory")
        for key in ("ko", "ja", "es", "de"):
            if source[key]["declared_route_has_lexical_evidence"]:
                raise ValueError(
                    "v0.17 baseline unexpectedly matches localized aliases"
                )
            if not target[key]["declared_route_outranks_unrelated"]:
                raise ValueError(f"candidate did not improve {key} alias recall")
        for group in (source, target):
            if not group["en"]["declared_route_outranks_unrelated"]:
                raise ValueError("English route regressed")
            if any(group["unsupported"].values()):
                raise ValueError("unsupported request gained invented lexical match")
            if any(
                outcome["unrelated_route_has_lexical_evidence"]
                for outcome in group.values()
            ):
                raise ValueError("unrelated route gained false lexical evidence")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    if args.capture and not (args.baseline or args.candidate):
        result = capture()
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        args.capture.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return
    if args.baseline and args.candidate and not args.capture:
        left = json.loads(args.baseline.read_text(encoding="utf-8"))
        right = json.loads(args.candidate.read_text(encoding="utf-8"))
        compare(left, right)
        print("Package regression verified (zero-model, not independent science)")
        return
    parser.error("use either --capture PATH or --baseline PATH --candidate PATH")


if __name__ == "__main__":
    main()
