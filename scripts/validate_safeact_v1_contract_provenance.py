#!/usr/bin/env python3
"""Validate SafeAct V1 runtime-contract provenance before scored execution.

This checker intentionally knows only *where* contract inputs came from. It does
not read SafeAct evaluator/gold files and must remain runnable without them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "data/safeact/cases.json",
    "env/case_evidence.json",
    "env/case_manifest.json",
    "env/case_provenance.json",
)
FORBIDDEN_FRAGMENTS = (
    "/materialized_evidence/",
    "gold_decision",
    "expected_outcome",
    "evidence_rules",
    "frozen_evidence_deltas",
    "workflow.commits",
)

ALLOWED_KINDS = {
    "public_tool_registry",
    "public_policy",
    "public_schema",
    "independent_contract",
}


def validate(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    contracts = document.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        return ["contracts must be a non-empty list"]

    for index, contract in enumerate(contracts):
        if not isinstance(contract, dict):
            errors.append(f"contracts[{index}] must be an object")
            continue
        sources = contract.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"contracts[{index}].sources must be non-empty")
            continue
        for source_index, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"contracts[{index}].sources[{source_index}] must be an object")
                continue
            kind = str(source.get("kind", ""))
            path = str(source.get("path", ""))
            if kind not in ALLOWED_KINDS:
                errors.append(f"forbidden source kind: {kind!r}")
            normalized = path.replace("\\", "/").lower()
            parts = normalized.split("/")
            if (
                not path
                or path.startswith(("/", "\\\\"))
                or ".." in parts
                or "." in parts
                or ":" in parts[0]
            ):
                errors.append(f"unsafe source path: {path}")
            if any(
                normalized == prefix
                or normalized.startswith(prefix + "/")
                or normalized.endswith("/" + prefix)
                or ("/" + prefix + "/") in normalized
                for prefix in FORBIDDEN_PREFIXES
            ):
                errors.append(f"forbidden evaluator source path: {path}")
            if any(fragment in normalized for fragment in FORBIDDEN_FRAGMENTS):
                errors.append(f"forbidden evaluator/gold source fragment: {path}")

        serialized = json.dumps(contract, sort_keys=True).lower()
        for key in (
            "gold_decision",
            "expected_outcome",
            "evidence_rules",
            "frozen_evidence_deltas",
            "case_spec",
            "gold_requirements",
        ):
            if f'"{key}"' in serialized:
                errors.append(f"forbidden evaluator field embedded in contract: {key}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract_file", type=Path)
    args = parser.parse_args()
    document = json.loads(args.contract_file.read_text(encoding="utf-8"))
    errors = validate(document)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"SafeAct V1 contract provenance OK: {len(document['contracts'])} contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
