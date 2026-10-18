"""No-model, synthetic-only E0 catalog vs selected schema UTF-8 disclosure costs.

Not a token-count estimate, model routing score, or permission certification.
No native tool invokers, network, model inference, agent loop, raw IDs or text
are exported. Deliberately report an oversized *complete* catalog instead
of truncating it or raising K to inflate outcomes.
"""
from __future__ import annotations

import json
from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import SIZES, build_fixture
from scripts.research_authorized_agent_tool_surface import (
    MAX_MODEL_CATALOG_INDEX_JSON_BYTES,
    capture_authorized_agent_tool_surface,
)

ROLES = ("viewer", "editor")
QUERY = "invoice total amount"
STRICT_K = 5


def _encoded_size(value: Any) -> int:
    return len(json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
    ).encode("utf-8"))


def profile(
    *, sizes: tuple[int, ...] = SIZES,
    roles: tuple[str, ...] = ROLES,
    max_index_bytes: int = MAX_MODEL_CATALOG_INDEX_JSON_BYTES,
) -> dict[str, Any]:
    """Paired fixed K5 diagnostic; outputs aggregate synthetic costs only."""
    if (
        type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(n) is not int or n not in SIZES for n in sizes)
        or type(roles) is not tuple or not roles
        or len(set(roles)) != len(roles)
        or any(type(role) is not str or role not in ROLES for role in roles)
        or type(max_index_bytes) is not int
        or not 1 <= max_index_bytes <= 131072
    ):
        raise ValueError("unregistered bounded E0 catalog cost configuration")

    rows: list[dict[str, Any]] = []
    for size in sizes:
        # Synthetic source catalog; fixed declared policy and query.
        router, _ = build_fixture(size)
        for role in roles:
            view = capture_authorized_agent_tool_surface(
                router, QUERY, principal=principal(role),
            )
            selected = list(view.visible_route_ids[:STRICT_K])
            definitions = view.tool_definitions(selected, k=STRICT_K)
            selected_schema_bytes = _encoded_size(definitions)
            first_schema_bytes = _encoded_size(
                view.tool_definitions(selected[:1], k=1)
            ) if selected else 2

            try:
                index = view.catalog_index(max_json_bytes=max_index_bytes)
            except ValueError as exc:
                # Only one explicitly budget-related, fail-closed condition.
                if str(exc) != "scoped catalog index exceeds research byte cap":
                    raise
                index_status = "rejected_oversize_complete_catalog"
                index_bytes: int | None = None
            else:
                index_status = "complete_authorized_catalog"
                assert len(index) == len(view.visible_route_ids)
                index_bytes = _encoded_size(index)
                assert index_bytes <= max_index_bytes
            view.assert_source_unchanged()
            rows.append({
                "synthetic_catalog_size": size,
                "synthetic_role": role,
                "visible_route_count": len(view.visible_route_ids),
                "index_status": index_status,
                "index_bytes": index_bytes,
                "full_selected_k5_schema_bytes": selected_schema_bytes,
                "first_selected_schema_bytes": first_schema_bytes,
                "index_plus_one_detail_bytes": (
                    None if index_bytes is None else index_bytes + first_schema_bytes
                ),
                "selected_count": len(selected),
                "execution_calls": 0,
                "model_calls": 0,
            })
    return {
        "study": "SYNTHETIC_AUTHORIZED_CATALOG_BYTE_COST_E0",
        "independent_e2": False,
        "measured_tokens": False,
        "proves_routing_accuracy": False,
        "model_calls": 0,
        "execution_calls": 0,
        "strict_selected_k": STRICT_K,
        "synthetic_only": True,
        "rows": rows,
    }
