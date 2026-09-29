"""Independent #430 adaptive-depth catalog surface.

The frozen #420/#423 B1/B2 fixtures are imported read-only for trusted
capability definitions and deterministic distractor construction. This module
extends the catalog-size surface to 100/250/500 without modifying B2.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from benchmarks.agent_utility_b2_catalog import (
    _base_tools,
    _distractor_endpoint,
)
from schemarouter import InMemoryRegistry

CATALOG_SIZES = (100, 250, 500)
BASE_ENDPOINT_COUNT = 20


def build_registry(endpoint_count: int) -> InMemoryRegistry:
    if endpoint_count not in CATALOG_SIZES:
        raise ValueError(f"unsupported adaptive DEV catalog size: {endpoint_count}")

    registry = InMemoryRegistry()
    base = _base_tools()
    registry.update_many(base)
    base_count = sum(len(tool.endpoints) for tool in base)
    if base_count != BASE_ENDPOINT_COUNT:
        raise RuntimeError(
            f"trusted base endpoint count drifted: {base_count} != {BASE_ENDPOINT_COUNT}"
        )

    for index in range(endpoint_count - base_count):
        registry.register(_distractor_endpoint(index))

    actual = sum(len(tool.endpoints) for tool in registry.tools())
    if actual != endpoint_count:
        raise RuntimeError(
            f"adaptive DEV catalog count drifted: {actual} != {endpoint_count}"
        )
    return registry


def route_ids(registry: InMemoryRegistry) -> tuple[str, ...]:
    return tuple(
        sorted(
            f"{tool.key}.{endpoint.name}"
            for tool in registry.tools()
            for endpoint in tool.endpoints
        )
    )


def _parameter_document(parameter: Any) -> dict[str, Any]:
    return {
        "name": parameter.name,
        "description": parameter.description,
        "required": parameter.required,
        "json_schema": parameter.json_schema,
    }


def _field_document(field: Any) -> dict[str, Any]:
    normalization = field.unit_normalization
    return {
        "name": field.name,
        "semantic_id": field.semantic_id,
        "description": field.description,
        "json_schema": field.json_schema,
        "unit": field.unit,
        "dimension": (
            normalization.dimension
            if normalization is not None
            else None
        ),
        "canonical_unit": (
            normalization.canonical_unit
            if normalization is not None
            else None
        ),
        "qualifiers": field.qualifiers,
    }


def catalog_documents(registry: InMemoryRegistry) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for tool in sorted(registry.tools(), key=lambda item: item.key):
        for endpoint in sorted(tool.endpoints, key=lambda item: item.name):
            documents.append(
                {
                    "route_id": f"{tool.key}.{endpoint.name}",
                    "tool_description": tool.description,
                    "endpoint_description": endpoint.description,
                    "read_only": endpoint.read_only,
                    "destructive": endpoint.destructive,
                    "parameters": [
                        _parameter_document(parameter)
                        for parameter in endpoint.parameters
                    ],
                    "outputs": [
                        _field_document(field)
                        for field in endpoint.output_fields
                    ],
                }
            )
    return documents


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def catalog_sha256(registry: InMemoryRegistry) -> str:
    return hashlib.sha256(
        _canonical_bytes(catalog_documents(registry))
    ).hexdigest()


def build_catalog_manifest() -> dict[str, Any]:
    registries = {
        size: build_registry(size)
        for size in CATALOG_SIZES
    }
    documents = {
        size: {
            row["route_id"]: row
            for row in catalog_documents(registry)
        }
        for size, registry in registries.items()
    }

    prior_routes: set[str] = set()
    for size in CATALOG_SIZES:
        current = set(documents[size])
        if not prior_routes.issubset(current):
            raise RuntimeError(
                f"catalog {size} is not nested over the prior catalog"
            )
        for route_id in prior_routes:
            previous_size = max(
                value
                for value in CATALOG_SIZES
                if value < size
            )
            if documents[size][route_id] != documents[previous_size][route_id]:
                raise RuntimeError(
                    f"nested route definition drifted: {route_id}"
                )
        prior_routes = current

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": "adaptive-capability-shortlist-depth-v1",
        "catalog_sizes": list(CATALOG_SIZES),
        "base_endpoint_count": BASE_ENDPOINT_COUNT,
        "nested": True,
        "b2_fixture_modified": False,
        "catalogs": {
            str(size): {
                "endpoint_count": len(documents[size]),
                "sha256": catalog_sha256(registries[size]),
                "route_ids_sha256": hashlib.sha256(
                    _canonical_bytes(sorted(documents[size]))
                ).hexdigest(),
            }
            for size in CATALOG_SIZES
        },
    }
