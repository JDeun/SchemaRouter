"""Run SchemaRouter preselection over the frozen ServiceNow readonly MCP surface."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median
from typing import Any

try:
    from scripts.external_validation_servicenow_platform_mcp import validate_package
except ModuleNotFoundError:  # direct python scripts/... invocation
    from external_validation_servicenow_platform_mcp import validate_package

import schemarouter as schemarouter_package
from schemarouter import SchemaRouter
from schemarouter.adapters.mcp import tool_from_mcp

try:
    from scripts.external_validation_provenance import implementation_provenance
except ModuleNotFoundError:
    from external_validation_provenance import implementation_provenance


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _materialize(contracts: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        contracts,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def run(
    *,
    package_dir: Path,
    snapshot_path: Path,
    repeats: int | None,
    implementation_revision: str | None,
    top_k: int | None,
) -> dict[str, Any]:
    manifest = _load(package_dir / "manifest.json")
    cases = _load(package_dir / manifest["files"]["cases"])
    snapshot = _load(snapshot_path)
    # Validate the exact native source/labels BEFORE constructing a model index
    # or materializing any simulated exposure; never work from drifted inputs.
    validate_package(manifest, cases, snapshot)
    if repeats is None:
        repeats = manifest["comparison"]["latency_repeats"]
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    if top_k is None:
        top_k = manifest["comparison"]["schemarouter_top_k"]
    allowed_k = manifest["comparison"]["development_top_k_sensitivity"]
    if (
        type(top_k) is not int
        or type(allowed_k) is not list
        or not allowed_k
        or any(type(k) is not int or k < 1 for k in allowed_k)
        or top_k not in allowed_k
    ):
        raise ValueError("top_k must be a preregistered development budget")

    tools = snapshot["tools"]
    tool_map = {tool["name"]: tool for tool in tools}

    build_start = time.perf_counter()
    router = SchemaRouter()
    router.add_tool(
        tool_from_mcp(
            "servicenow-platform-mcp",
            {"tools": tools},
            namespace="external-validation-servicenow-platform-mcp",
        )
    )
    router.retrieve("__servicenow_benchmark_index_build__", k=1)
    index_build_ms = (time.perf_counter() - build_start) * 1000.0

    rows: list[dict[str, Any]] = []
    for case in cases["cases"]:
        query = case["query"]
        router.retrieve(query, k=top_k)

        durations: list[float] = []
        final_names: list[str] = []
        final_contracts: list[dict[str, Any]] = []
        for _ in range(repeats):
            start = time.perf_counter()
            retrieval = router.retrieve(query, k=top_k)
            names = [candidate.endpoint for candidate in retrieval.candidates]
            contracts = [tool_map[name] for name in names]
            _materialize(contracts)
            durations.append((time.perf_counter() - start) * 1000.0)
            final_names = names
            final_contracts = contracts

        rows.append(
            {
                "id": case["id"],
                "candidate_tools": final_names,
                "visible_contracts": final_contracts,
                "latency_ms": median(durations),
            }
        )

    provenance = implementation_provenance(
        fixture_reference_revision=manifest["source_revisions"]["schemarouter"],
        explicit_revision=implementation_revision,
        source_path=Path(schemarouter_package.__file__) if schemarouter_package.__file__ else None,
        distribution="schemarouter",
    )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "SchemaRouter over ServiceNow readonly MCP tools/list",
            **provenance,
            "configuration": {
                "condition": "readonly_plus_schemarouter_preselection",
                "api": "SchemaRouter.retrieve",
                "mcp_ingestion": "schemarouter.adapters.mcp.tool_from_mcp",
                "top_k": top_k,
                "repeats_per_query": repeats,
                "execution": "disabled",
                "latency_boundary": "typed retrieval + canonical native-contract materialization",
                "upstream_tool_package": "readonly",
            },
        },
        "index_build_ms": index_build_ms,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--implementation-revision")
    args = parser.parse_args()

    payload = run(
        package_dir=args.package_dir,
        snapshot_path=args.snapshot,
        repeats=args.repeats,
        implementation_revision=args.implementation_revision,
        top_k=args.top_k,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.out)


if __name__ == "__main__":
    main()
