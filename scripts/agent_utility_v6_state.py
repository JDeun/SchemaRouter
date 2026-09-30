"""Typed observable execution-state helpers for #431 corrective retrieval.

This module does not execute #431. It only freezes how observable tool state is
projected into a retrieval query. Hidden future labels and free-text tool output
are intentionally excluded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemarouter import InMemoryRegistry

ROOT = Path(__file__).resolve().parents[1]
PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v6-corrective-reretrieval-preregistration.json"
)
STATUS_VALUES = {"not_run", "ok", "error", "blocked", "executed"}


def _contract() -> dict[str, Any]:
    return json.loads(PREREG.read_text(encoding="utf-8"))["state_contract"]


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"unsupported observation value type: {type(value).__name__}")


def _endpoint_for(registry: InMemoryRegistry, route_id: str) -> Any | None:
    if "." not in route_id:
        return None
    tool_key, endpoint_name = route_id.split(".", 1)
    try:
        tool = registry.get(tool_key)
        return tool.endpoint(endpoint_name)
    except KeyError:
        return None


def _normalized_error_class(error: str | None) -> str | None:
    if error is None:
        return None
    value = error.strip()
    if not value:
        return None
    return value.split(":", 1)[0]


def _identifier_value(
    field: Any | None,
    field_name: str,
    value: Any,
) -> str | None:
    if not isinstance(value, (str, int, float)):
        return None
    is_identifier = field_name.endswith("_id")
    if field is not None:
        semantic_id = field.semantic_id or ""
        is_identifier = (
            is_identifier
            or bool(field.identifier)
            or semantic_id.endswith(".id")
            or semantic_id.endswith(".identifier")
        )
    if not is_identifier:
        return None
    rendered = str(value).strip()
    return rendered or None


def empty_state(original_query: str) -> dict[str, Any]:
    query = original_query.strip()
    if not query:
        raise ValueError("original_query must be non-empty")
    return {
        "original_query": query,
        "executed_registered_route_ids": [],
        "observation_field_names": [],
        "observation_semantic_ids": [],
        "observation_value_types": [],
        "observation_units": [],
        "observation_dimensions": [],
        "observation_qualifiers": [],
        "stable_observed_identifiers": [],
        "last_execution_status": "not_run",
        "last_error_class": None,
        "task_incomplete_boolean": True,
    }


def validate_state(state: dict[str, Any]) -> None:
    contract = _contract()
    allowed = set(contract["allowed_fields"])
    forbidden = set(contract["forbidden_fields"])
    keys = set(state)

    unknown = sorted(keys - allowed)
    if unknown:
        raise ValueError("state contains non-contract fields: " + ", ".join(unknown))
    leaked = sorted(keys & forbidden)
    if leaked:
        raise ValueError("state contains forbidden fields: " + ", ".join(leaked))
    missing = sorted(allowed - keys)
    if missing:
        raise ValueError("state is missing required fields: " + ", ".join(missing))

    if not isinstance(state["original_query"], str) or not state["original_query"].strip():
        raise TypeError("original_query must be a non-empty string")

    list_fields = (
        "executed_registered_route_ids",
        "observation_field_names",
        "observation_semantic_ids",
        "observation_value_types",
        "observation_units",
        "observation_dimensions",
        "observation_qualifiers",
        "stable_observed_identifiers",
    )
    for key in list_fields:
        value = state[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item
            for item in value
        ):
            raise TypeError(f"{key} must be list[str] with non-empty values")

    ordered_routes = state["executed_registered_route_ids"]
    if len(ordered_routes) != len(set(ordered_routes)):
        raise ValueError("executed_registered_route_ids must be unique")

    sorted_fields = list_fields[1:]
    for key in sorted_fields:
        value = state[key]
        if value != sorted(set(value)):
            raise ValueError(f"{key} must be sorted and unique")

    status = state["last_execution_status"]
    if status not in STATUS_VALUES:
        raise ValueError(f"unsupported last_execution_status: {status}")

    error_class = state["last_error_class"]
    if error_class is not None and (
        not isinstance(error_class, str)
        or not error_class
        or ":" in error_class
    ):
        raise TypeError("last_error_class must be null or normalized class string")

    if not isinstance(state["task_incomplete_boolean"], bool):
        raise TypeError("task_incomplete_boolean must be boolean")


def update_state(
    state: dict[str, Any],
    *,
    registry: InMemoryRegistry,
    route_id: str,
    observation: dict[str, Any],
    error: str | None,
    task_incomplete: bool,
) -> dict[str, Any]:
    validate_state(state)
    if not isinstance(observation, dict):
        raise TypeError("observation must be an object")

    updated = {
        key: list(value) if isinstance(value, list) else value
        for key, value in state.items()
    }
    endpoint = _endpoint_for(registry, route_id)
    if endpoint is not None:
        routes = updated["executed_registered_route_ids"]
        if route_id not in routes:
            routes.append(route_id)

    field_names = set(updated["observation_field_names"])
    value_types = set(updated["observation_value_types"])
    semantic_ids = set(updated["observation_semantic_ids"])
    units = set(updated["observation_units"])
    dimensions = set(updated["observation_dimensions"])
    qualifiers = set(updated["observation_qualifiers"])
    identifiers = set(updated["stable_observed_identifiers"])

    metadata = (
        {field.name: field for field in endpoint.output_fields}
        if endpoint is not None
        else {}
    )

    for field_name, value in observation.items():
        field_names.add(str(field_name))
        value_types.add(_json_type(value))
        field = metadata.get(str(field_name))
        if field is not None:
            if field.semantic_id:
                semantic_ids.add(field.semantic_id)
            if field.unit:
                units.add(field.unit)
            if field.unit_normalization is not None:
                dimensions.add(field.unit_normalization.dimension)
            for key, qualifier_value in field.qualifiers.items():
                qualifiers.add(f"{key}={qualifier_value}")
        identifier = (
            _identifier_value(field, str(field_name), value)
            if endpoint is not None
            else None
        )
        if identifier is not None:
            identifiers.add(identifier)

    status = observation.get("status")
    if not isinstance(status, str) or status not in STATUS_VALUES:
        raise ValueError(
            "observation status must be one of: "
            + ", ".join(sorted(STATUS_VALUES))
        )

    updated["observation_field_names"] = sorted(field_names)
    updated["observation_value_types"] = sorted(value_types)
    updated["observation_semantic_ids"] = sorted(semantic_ids)
    updated["observation_units"] = sorted(units)
    updated["observation_dimensions"] = sorted(dimensions)
    updated["observation_qualifiers"] = sorted(qualifiers)
    updated["stable_observed_identifiers"] = sorted(identifiers)
    updated["last_execution_status"] = status
    updated["last_error_class"] = _normalized_error_class(error)
    updated["task_incomplete_boolean"] = bool(task_incomplete)

    validate_state(updated)
    return updated


def render_retrieval_query(state: dict[str, Any]) -> str:
    validate_state(state)
    payload = {
        key: value
        for key, value in state.items()
        if key != "original_query"
    }
    suffix = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        state["original_query"]
        + "\n\n[EXECUTION_STATE]\n"
        + suffix
    )
