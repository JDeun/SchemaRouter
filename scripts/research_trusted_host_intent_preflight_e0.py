"""Opt-in host-attested intent preflight over an *authorized* tool snapshot.

This is a read-only pre-model decision from a trusted host-authored frame.
It does not infer intent from a user's language, authenticate the principal,
run a provider, establish no-fit calibration, or confer execution authority.

Crucial privacy invariant: "unknown route" and "registered but not permitted"
produce the same opaque public outcome, with no count or route name.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Literal

from schemarouter.errors import PolicyViolationError
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
)

Decision = Literal["ready", "needs_input", "ambiguous", "unavailable"]
# These literals are protocol-only, not localized user-facing copy.
PROTOCOL: dict[str, str] = {
    "needs_input": "REQUEST_INPUT",
    "ambiguous": "CLARIFY_REQUEST",
    "unavailable": "REQUEST_MORE_TOOLS",
}
_SIMPLE_TYPES = frozenset({"string", "integer", "number", "boolean"})
_MAX_FIELDS = 16
_MAX_HYPOTHESES = 8
_MAX_JSON_BYTES = 4096


@dataclass(frozen=True, slots=True)
class TrustedIntentPreflightE0:
    disposition: Decision
    protocol: str | None
    # No route IDs, hidden existence, arguments, user text, authorization
    # rule details, field names or scores appear in this returned receipt.
    real_native_provider_execution: bool = False
    independent_e2_qualified: bool = False
    calibrated_no_fit: bool = False
    model_default_promoted: bool = False
    executable_authority: bool = False


def _fits_public_schema(schema: dict[str, Any], value: Any) -> bool:
    """Conservatively check only a bounded subset of public JSON types.

    Unknown schema keywords do not create a permission to call a tool.
    A production invoker must still validate the whole native schema.
    """
    if type(schema) is not dict:
        return False
    kind = schema.get("type")
    if kind not in _SIMPLE_TYPES:
        return False
    if kind == "string":
        valid = type(value) is str and bool(value.strip())
    elif kind == "integer":
        valid = type(value) is int
    elif kind == "number":
        valid = type(value) in (int, float) and math.isfinite(value)
    else:
        valid = type(value) is bool
    if not valid:
        return False
    enum = schema.get("enum")
    if enum is not None and (
        type(enum) is not list
        or not any(type(option) is type(value) and option == value for option in enum)
    ):
        return False
    if kind in ("integer", "number"):
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        if minimum is not None and (
            type(minimum) not in (int, float) or value < minimum
        ):
            return False
        if maximum is not None and (
            type(maximum) not in (int, float) or value > maximum
        ):
            return False
    if kind == "string":
        if "minLength" in schema and (
            type(schema["minLength"]) is not int
            or len(value) < schema["minLength"]
        ):
            return False
        if "maxLength" in schema and (
            type(schema["maxLength"]) is not int
            or len(value) > schema["maxLength"]
        ):
            return False
    # Pattern/format/complex schema constraints require a real host
    # schema validator before any native execution, never infer "ready".
    unsupported = set(schema).intersection({
        "$ref", "pattern", "format", "oneOf", "anyOf", "allOf", "not",
        "const", "multipleOf", "exclusiveMinimum", "exclusiveMaximum",
    })
    return not unsupported


def preflight_trusted_host_intent_e0(
    view: AuthorizedAgentToolSurface,
    *,
    query: str,
    host_candidate_routes: tuple[str, ...],
    host_supplied_fields: dict[str, Any],
) -> TrustedIntentPreflightE0:
    """Check trusted host input against *only* the principal-visible catalog.

    The host MUST author/validate route hypotheses and structured inputs
    outside the model. Do not pass user/model-supplied labels as host truth.
    "ready" only means no obvious public-schema blocker, NOT executable.
    """
    if type(view) is not AuthorizedAgentToolSurface:
        raise PolicyViolationError("principal-scoped host view required")
    view.assert_source_unchanged()
    if type(query) is not str or query != view.original_query:
        raise PolicyViolationError("host intent query differs from captured source")
    if (
        type(host_candidate_routes) is not tuple
        or len(host_candidate_routes) > _MAX_HYPOTHESES
        or any(type(route) is not str or not route for route in host_candidate_routes)
        or len(set(host_candidate_routes)) != len(host_candidate_routes)
    ):
        raise PolicyViolationError("invalid trusted host route hypotheses")
    if (
        type(host_supplied_fields) is not dict
        or len(host_supplied_fields) > _MAX_FIELDS
        or any(type(k) is not str or not k for k in host_supplied_fields)
    ):
        raise PolicyViolationError("invalid structured host inputs")
    try:
        encoded = json.dumps(
            host_supplied_fields, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise PolicyViolationError("unverifiable structured host inputs") from exc
    if len(encoded.encode("utf-8")) > _MAX_JSON_BYTES:
        raise PolicyViolationError("structured host inputs exceed preflight bound")
    allowed = frozenset(view.visible_route_ids)
    # A guessed hidden route cannot be distinguished from a nonexistent one;
    # if *any* host hypothesis is hidden, do NOT silently choose another.
    if not host_candidate_routes or not set(host_candidate_routes) <= allowed:
        view.assert_source_unchanged()
        return TrustedIntentPreflightE0(
            disposition="unavailable", protocol=PROTOCOL["unavailable"],
        )
    if len(host_candidate_routes) != 1:
        view.assert_source_unchanged()
        return TrustedIntentPreflightE0(
            disposition="ambiguous", protocol=PROTOCOL["ambiguous"],
        )
    definitions = view.tool_definitions([host_candidate_routes[0]], k=1)
    spec = definitions[0].get("parameters")
    if (
        type(spec) is not dict or spec.get("type") != "object"
        or spec.get("additionalProperties") is not False
        or type(spec.get("required")) is not list
        or type(spec.get("properties")) is not dict
        or len(spec["properties"]) > _MAX_FIELDS
        or any(type(k) is not str for k in spec["required"])
    ):
        raise PolicyViolationError("invalid authorized host input schema")
    properties = spec["properties"]
    required = spec["required"]
    blocked = (
        any(key not in properties for key in host_supplied_fields)
        or any(key not in host_supplied_fields for key in required)
        or any(
            not _fits_public_schema(properties[key], value)
            for key, value in host_supplied_fields.items()
            if key in properties
        )
    )
    view.assert_source_unchanged()
    if blocked:
        return TrustedIntentPreflightE0(
            disposition="needs_input", protocol=PROTOCOL["needs_input"],
        )
    return TrustedIntentPreflightE0(disposition="ready", protocol=None)
