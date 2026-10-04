"""Emit a frozen shared-catalog package for external tool-router validation.

The package reuses the already reviewed Gearlynx-derived catalog and cases so
external routers can run against exactly the same tool names and queries as
SchemaRouter without requiring emulator execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.external_validation_gearlynx import CASES, FIXTURE, evaluate, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    )


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def build_package() -> dict[str, Any]:
    fixture = load_catalog()
    tools = fixture["tools"]
    cases = [
        {
            "id": f"case-{index:02d}",
            "query": query,
            "required_tools": [] if required is None else [required],
            "label": "unsupported" if required is None else "supported",
        }
        for index, (query, required) in enumerate(CASES, start=1)
    ]
    catalog = [
        {
            "name": tool["name"],
            "description": " ".join(
                [tool["title"], tool["description"], "category", tool["category"]]
            ),
            "parameter_names": tool["parameter_names"],
            "schema_source_bytes": tool["schema_source_bytes"],
        }
        for tool in tools
    ]
    baseline = evaluate()
    return {
        "schema_version": 1,
        "package_id": "gearlynx-shared-router-v1",
        "schema_router_commit": "4fcb2dddeaa67157322301a9f9356b0ea1bc1fbe",
        "catalog_source": {
            "repository": fixture["upstream"]["repository"],
            "commit": fixture["upstream"]["commit"],
            "license": fixture["upstream"].get("license", "upstream source license"),
            "derived_fixture": str(FIXTURE.relative_to(ROOT)),
        },
        "catalog": catalog,
        "catalog_sha256": sha256(catalog),
        "cases": cases,
        "cases_sha256": sha256(cases),
        "budget": {
            "top_k": 3,
            "schema_budget_definition": (
                "schema_source_bytes from the frozen Gearlynx C++ inputSchema "
                "initializer; not wire JSON bytes"
            ),
        },
        "metrics": {
            "tool_recall": True,
            "unsupported_rejection": True,
            "selected_set_size": True,
            "schema_source_bytes": True,
            "latency_ms": True,
            "field_recall": False,
            "field_recall_reason": (
                "The pinned Gearlynx fixture has parameter names but no normalized "
                "output-field ground truth. No output-field labels are imputed."
            ),
        },
        "schemarouter_result": {
            "native_summary": baseline["native_summary"],
            "schemarouter_summary": baseline["schemarouter_summary"],
        },
        "external_runner_contract": {
            "input": "catalog + cases above",
            "return_per_case": [
                "selected_tools",
                "latency_ms",
                "schema_source_bytes",
            ],
            "notes": [
                "Do not execute external tools.",
                "Do not use paid-model calls unless separately agreed.",
                "Preserve the external router's native retrieval semantics.",
                "Report negative results unchanged.",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = build_package()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
