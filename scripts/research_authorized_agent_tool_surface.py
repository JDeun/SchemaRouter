"""Principal-scoped MODEL DISCLOSURE + trace redaction research boundary (#1477).

Read-only adapter for future opt-in evaluation; not a product authorization
receipt, not an invoker, not an agent loop or independent model quality score.
The trusted host supplies SchemaRouter + PrincipalContext, never the backend.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from schemarouter import (
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
)

MAX_SOURCE_ENDPOINTS = 500
MAX_TOOL_DEFINITIONS = 5
MAX_MODEL_TOOL_JSON_BYTES = 131072
SCALAR_TYPES = (type(None), bool, int, float, str)
ALLOWED_SCHEMA_TYPES = frozenset({
    "boolean", "integer", "number", "string",
})
ALLOWED_OBSERVATION_STATUSES = frozenset({"ok", "blocked", "error"})


@dataclass(frozen=True)
class AuthorizedAgentToolSurface:
    """A checked, scoped model-view snapshot, NOT an execution grant."""

    router: SchemaRouter
    witness: tuple[Any, ...]
    registered_route_count: int
    visible_route_ids: tuple[str, ...]
    _tool_definitions: dict[str, dict[str, Any]]
    _visible_output_names: dict[str, frozenset[str]]
    independent_quality_evidence: bool = False
    executable_authority: bool = False

    def assert_source_unchanged(self) -> None:
        self.router._check_retrieval_authority_witness(self.witness)

    def tool_definitions(
        self, selected_route_ids: list[str], *, k: int = MAX_TOOL_DEFINITIONS,
    ) -> list[dict[str, Any]]:
        """Authorize what the MODEL may SEE, not what an invoker may DO."""
        self.assert_source_unchanged()
        if type(k) is not int or not 1 <= k <= MAX_TOOL_DEFINITIONS:
            raise ValueError("invalid fixed K for model disclosure")
        if (
            type(selected_route_ids) is not list
            or len(selected_route_ids) > k
            or any(type(value) is not str for value in selected_route_ids)
            or len(set(selected_route_ids)) != len(selected_route_ids)
            or any(route not in self._tool_definitions for route in selected_route_ids)
        ):
            raise PolicyViolationError("candidate not in principal-visible source set")
        result = [
            copy.deepcopy(self._tool_definitions[route])
            for route in selected_route_ids
        ]
        self.assert_source_unchanged()
        return result

    def project_observation(
        self, route_id: str, observation: dict[str, Any],
    ) -> dict[str, Any]:
        """Minimal scalar projected model observation, never raw fixture state."""
        self.assert_source_unchanged()
        if route_id not in self._tool_definitions or type(observation) is not dict:
            raise PolicyViolationError("unavailable scoped observation route")
        raw_status = observation.get("status", "error")
        status = (
            raw_status
            if type(raw_status) is str
            and raw_status in ALLOWED_OBSERVATION_STATUSES
            else "error"
        )
        if status != "ok":
            # Raw provider error text may contain secrets. Only report a
            # coarse code to the agent; keep original internal evidence private.
            return {"status": status, "error": "provider_call_failed"}
        projected: dict[str, Any] = {"status": "ok"}
        for field in self._visible_output_names[route_id]:
            if field not in observation:
                continue
            value = observation[field]
            if type(value) not in SCALAR_TYPES or (
                type(value) is float and not math.isfinite(value)
            ):
                # Never serialize a structured value that may contain hidden
                # nested keys until an explicit nested schema projector exists.
                raise PolicyViolationError("nested output requires scoped projector")
            projected[field] = value
        self.assert_source_unchanged()
        return projected

    def public_trace(self, episode_row: dict[str, Any]) -> dict[str, Any]:
        """Safe metrics-only record: NO prompts, gold, args, raw outputs or COT."""
        self.assert_source_unchanged()
        if type(episode_row) is not dict:
            raise ValueError("episode row must be a dictionary")
        allowed = set(self.visible_route_ids)
        result: dict[str, Any] = {
            "source_registered_route_count": self.registered_route_count,
            "visible_scored_route_count": len(allowed),
            "independent_quality_evidence": False,
            "executable_authority": False,
        }
        # Only strictly typed, nonsensitive scalar totals; no original
        # task IDs, user query, final generated text or expected gold routes.
        for name in (
            "passed", "task_complete", "supported", "context_overflow",
        ):
            value = episode_row.get(name)
            if type(value) is bool:
                result[name] = value
        for name in (
            "turns", "tool_call_count", "policy_blocks",
            "unauthorized_destructive_executions", "input_tokens",
            "output_tokens", "tool_schema_tokens", "retrieval_calls",
        ):
            value = episode_row.get(name)
            if type(value) is int and value >= 0:
                result[name] = value
        # Do not echo candidate history containing foreign route IDs.
        history = episode_row.get("candidate_history")
        if type(history) is list:
            result["visible_candidate_counts"] = [
                len([route for route in event if route in allowed])
                if type(event) is list else 0 for event in history
            ]
        # Export no raw turn_rows, attempts, source details or error messages.
        self.assert_source_unchanged()
        return result


def capture_authorized_agent_tool_surface(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    max_registered_routes: int = MAX_SOURCE_ENDPOINTS,
) -> AuthorizedAgentToolSurface:
    """Construct agent-visible definitions from the real SOURCE-SCOPED output."""
    if type(query) is not str or not query.strip():
        raise ValueError("original nonempty query required")
    if (
        type(max_registered_routes) is not int
        or not 1 <= max_registered_routes <= MAX_SOURCE_ENDPOINTS
    ):
        raise ValueError("invalid source cap")
    witness = router._retrieval_authority_witness()
    physical = sum(len(tool.endpoints) for tool in router.registry.tools())
    if physical > max_registered_routes:
        raise ValueError("original catalog exceeds research cap")

    # The public API enforces principal-scoped RBAC/ABAC, data-rule
    # projection and availability. Only positively scored visible routes can
    # become a model tool definition; hidden route cardinality is not shown.
    result = router.retrieve_authorized(
        query, principal=principal, k=max(1, physical),
    )
    router._check_retrieval_authority_witness(witness)
    if (
        result.registry_version != witness[1]
        or result.total_ranked != len(result.candidates)
        or len(result.candidates) > physical
        or len({c.route_id for c in result.candidates}) != len(result.candidates)
    ):
        raise PolicyViolationError("incomplete authorized model source capture")

    field_scoped = bool(
        router.authorization_policy is not None
        and router.authorization_policy.data_rules
    )
    definitions: dict[str, dict[str, Any]] = {}
    visible: dict[str, frozenset[str]] = {}
    for candidate in result.candidates:
        params: dict[str, dict[str, Any]] = {}
        required: list[str] = []
        for parameter in candidate.parameters:
            if field_scoped:
                # Never send unstructured descriptions, arbitrary nested
                # schemas, examples, defaults or data enumerations that may
                # mention a hidden source field or private value.
                declared_type = parameter.json_schema.get("type")
                if type(declared_type) is not str or (
                    declared_type not in ALLOWED_SCHEMA_TYPES
                ):
                    raise PolicyViolationError("complex field-scoped parameter unavailable")
                schema = {"type": declared_type}
            else:
                schema = copy.deepcopy(parameter.json_schema)
                if parameter.description:
                    schema["description"] = parameter.description
            params[parameter.name] = schema
            if parameter.required:
                required.append(parameter.name)

        field_labels = [
            field.semantic_id or field.name for field in candidate.output_fields
        ]
        parts = [
            f"Registered source route: {candidate.route_id}.",
            f"read_only={candidate.read_only}; destructive={candidate.destructive}.",
        ]
        if not field_scoped:
            parts[0:0] = [
                candidate.tool_description.strip(),
                candidate.endpoint_description.strip(),
            ]
        if field_labels:
            parts.append("Visible output fields: " + "; ".join(field_labels) + ".")
        definition = {
            "name": candidate.route_id.replace(".", "__", 1),
            "description": " ".join(part for part in parts if part),
            "parameters": {
                "type": "object",
                "properties": params,
                "required": required,
                "additionalProperties": False,
            },
        }
        definitions[candidate.route_id] = definition
        visible[candidate.route_id] = frozenset(
            field.name for field in candidate.output_fields
        )
    router._check_retrieval_authority_witness(witness)
    return AuthorizedAgentToolSurface(
        router=router, witness=witness, registered_route_count=physical,
        visible_route_ids=tuple(definitions),
        _tool_definitions=definitions,
        _visible_output_names=visible,
    )
