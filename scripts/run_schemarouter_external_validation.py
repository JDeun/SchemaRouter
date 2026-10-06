"""Run SchemaRouter's native typed retrieval on the shared SmartMCP fixture."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median
from typing import Any

import schemarouter as schemarouter_package
from schemarouter import SchemaRouter
from schemarouter.models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec

from scripts.external_validation_provenance import implementation_provenance


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parameter_specs(input_schema: dict[str, Any]) -> list[ParameterSpec]:
    required = set(input_schema.get("required", []))
    properties = input_schema.get("properties", {})
    if not isinstance(properties, dict):
        return []

    parameters: list[ParameterSpec] = []
    for name, raw_schema in properties.items():
        schema = raw_schema if isinstance(raw_schema, dict) else {}
        parameters.append(
            ParameterSpec(
                name=name,
                description=str(schema.get("description", "")),
                required=name in required,
                json_schema=schema,
            )
        )
    return parameters


def _field_specs(raw_fields: list[dict[str, Any]]) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    for raw in raw_fields:
        fields.append(
            FieldSpec(
                name=raw["name"],
                semantic_id=raw.get("semantic_id"),
                json_schema=raw.get("json_schema", {}),
                unit=raw.get("unit"),
            )
        )
    return fields


def _output_schema(fields: list[FieldSpec]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            field.name: field.json_schema
            for field in fields
        },
        "required": [field.name for field in fields],
        "additionalProperties": False,
    }


def build_router(catalog: dict[str, Any]) -> SchemaRouter:
    router = SchemaRouter()
    for raw_tool in catalog["tools"]:
        input_schema = raw_tool["input_schema"]
        fields = _field_specs(raw_tool.get("output_fields", []))
        operation = raw_tool["name"].split("__", 1)[-1]
        endpoint = EndpointSpec(
            name=operation,
            description=raw_tool["description"],
            parameters=_parameter_specs(input_schema),
            input_schema=input_schema,
            output_fields=fields,
            output_schema=_output_schema(fields),
            read_only=raw_tool.get("read_only"),
            destructive=raw_tool.get("destructive"),
        )
        router.add_tool(
            ToolSpec(
                name=raw_tool["name"],
                description=raw_tool["description"],
                endpoints=[endpoint],
                source_type="benchmark_fixture",
                provider="smartmcp-cross-project-dev",
                access_mode="offline-fixture",
            )
        )
    return router


def run(
    *,
    package_dir: Path,
    repeats: int,
    implementation_revision: str | None = None,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")

    manifest = _load(package_dir / "manifest.json")
    catalog = _load(package_dir / manifest["files"]["catalog"])
    cases = _load(package_dir / manifest["files"]["cases"])
    top_k = int(manifest["comparison"]["max_candidates"])

    build_start = time.perf_counter()
    router = build_router(catalog)
    # Force lazy retrieval indexes to materialize before hot-path measurements.
    router.retrieve("__benchmark_index_build__", k=1)
    index_build_ms = (time.perf_counter() - build_start) * 1000.0

    rows: list[dict[str, Any]] = []
    for case in cases["cases"]:
        query = case["query"]
        router.retrieve(query, k=top_k)

        durations: list[float] = []
        final = None
        for _ in range(repeats):
            start = time.perf_counter()
            current = router.retrieve(query, k=top_k)
            durations.append((time.perf_counter() - start) * 1000.0)
            final = current

        assert final is not None
        rows.append(
            {
                "id": case["id"],
                "candidate_tools": [
                    candidate.tool
                    for candidate in final.candidates
                ],
                "exposed_contracts": [
                    candidate.model_dump(mode="json")
                    for candidate in final.candidates
                ],
                "latency_ms": median(durations),
            }
        )

    provenance = implementation_provenance(
        fixture_reference_revision=manifest["source_revisions"].get("schemarouter"),
        explicit_revision=implementation_revision,
        source_path=(
            Path(schemarouter_package.__file__)
            if schemarouter_package.__file__
            else None
        ),
        distribution="schemarouter",
    )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "SchemaRouter typed capability retrieval",
            **provenance,
            "configuration": {
                "repeats_per_query": repeats,
                "top_k": top_k,
                "api": "SchemaRouter.retrieve",
                "structural_retrieval": False,
                "execution": "disabled",
            },
        },
        "index_build_ms": index_build_ms,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument(
        "--implementation-revision",
        help="Exact SchemaRouter commit/revision used when it cannot be detected from a git checkout.",
    )
    args = parser.parse_args()

    payload = run(
        package_dir=args.package_dir,
        repeats=args.repeats,
        implementation_revision=args.implementation_revision,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.out)


if __name__ == "__main__":
    main()
