"""Principal-scoped MODEL DISCLOSURE + trace redaction research boundary (#1477).

Read-only adapter for future opt-in evaluation; not a product authorization
receipt, not an invoker, not an agent loop or independent model quality score.
The trusted host supplies SchemaRouter + PrincipalContext, never the backend.
"""
from __future__ import annotations

import copy
import hmac
import json
import math
import secrets
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
)
from scripts.research_bounded_authorized_semantic_diagnostic import (
    CapturedAuthorizedSemanticRoute,
    scoped_semantic_model_description,
)

MAX_SOURCE_ENDPOINTS = 500
MAX_TOOL_DEFINITIONS = 5
MAX_MODEL_TOOL_JSON_BYTES = 131072
MAX_MODEL_CATALOG_INDEX_JSON_BYTES = 32768
MAX_MODEL_OBSERVATION_JSON_BYTES = 32768
SCALAR_TYPES = (type(None), bool, int, float, str)
ALLOWED_SCHEMA_TYPES = frozenset({
    "boolean", "integer", "number", "string",
})
ALLOWED_OBSERVATION_STATUSES = frozenset({"ok", "blocked", "error"})
# Process-local integrity receipt; not a portable credential or a tool grant.
# This guards accidental or adversarial dataclass/dict source-view mutations.
_SCOPED_VIEW_HMAC_KEY = secrets.token_bytes(32)


def _checked_scoped_view_receipt(view: AuthorizedAgentToolSurface) -> str:
    """Commit to model-visible source contents without exporting source bytes.

    No cross-request cache: this evaluates precisely the trusted capture's
    source metadata. Arbitrary code executing in this process is outside this
    receipt's trust boundary, as it could access private runtime state.
    """
    try:
        if (
            type(view.visible_route_ids) is not tuple
            or type(view._tool_definitions) is not dict
            or type(view._visible_output_names) is not dict
            or type(view._semantic_source_routes) is not tuple
            or any(
                type(route) is not CapturedAuthorizedSemanticRoute
                for route in view._semantic_source_routes
            )
        ):
            raise ValueError("captured source container changed")
        payload = {
            "original_query": view.original_query,
            "principal_claims": view._principal_claims_snapshot,
            "registered_route_count": view.registered_route_count,
            "registry_version": view.witness[1],
            "visible_route_ids": view.visible_route_ids,
            "tool_definitions": view._tool_definitions,
            "output_names": {
                name: sorted(fields)
                for name, fields in view._visible_output_names.items()
            },
            "semantic_routes": [
                (
                    route.route_id,
                    route.description,
                    route.tool_fingerprint,
                    route.endpoint_fingerprint,
                )
                for route in view._semantic_source_routes
            ],
        }
        serialized = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, AttributeError, IndexError):
        raise PolicyViolationError(
            "captured authorized source identity drift",
        ) from None
    return hmac.digest(_SCOPED_VIEW_HMAC_KEY, serialized, "sha256").hex()



def _authorization_policy_receipt(policy: AuthorizationPolicy | None) -> str:
    """HMAC current policy contents and mutable compiled authorization indexes.

    The library's general authority witness is identity/version-based. This
    opt-in model-disclosure guard also rejects in-place policy mutations.
    It is not an atomic transaction across concurrent host threads.
    """
    try:
        if policy is None:
            payload: dict[str, Any] = {"policy": None}
        elif type(policy) is AuthorizationPolicy:
            def index_rows(index: Any) -> list[dict[str, Any]]:
                if type(index.partitions) is not dict:
                    raise ValueError("invalid compiled rule index")
                rows = [
                    {"key": list(key), "positions": list(positions)}
                    for key, positions in index.partitions.items()
                ]
                return sorted(
                    rows, key=lambda row: json.dumps(row["key"], sort_keys=True),
                )

            payload = {
                "default_effect": policy.default_effect,
                "rules": [asdict(rule) for rule in policy.rules],
                "data_rules": [asdict(rule) for rule in policy.data_rules],
                "compiled_rule_index": {
                    "rules": [asdict(rule) for rule in policy._rule_index.rules],
                    "partitions": index_rows(policy._rule_index),
                },
                "compiled_data_rule_index": {
                    "rules": [asdict(rule) for rule in policy._data_rule_index.rules],
                    "partitions": index_rows(policy._data_rule_index),
                },
            }
        else:
            raise ValueError("invalid policy type")
        encoded = json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, AttributeError, OverflowError, RecursionError):
        raise PolicyViolationError("unverifiable in-process authorization policy") from None
    return hmac.digest(_SCOPED_VIEW_HMAC_KEY, encoded, "sha256").hex()


@dataclass(frozen=True)
class AuthorizedAgentToolSurface:
    """A checked, scoped model-view snapshot, NOT an execution grant."""

    router: SchemaRouter
    witness: tuple[Any, ...]
    _principal: PrincipalContext
    _principal_claims_snapshot: str
    original_query: str
    registered_route_count: int
    visible_route_ids: tuple[str, ...]
    _tool_definitions: dict[str, dict[str, Any]]
    _visible_output_names: dict[str, frozenset[str]]
    _semantic_source_routes: tuple[CapturedAuthorizedSemanticRoute, ...] = dataclass_field(
        default_factory=tuple, repr=False,
    )
    _scoped_view_receipt: str = dataclass_field(
        default="", init=False, repr=False, compare=False,
    )
    _authorization_policy_receipt: str = dataclass_field(
        default="", init=False, repr=False, compare=False,
    )
    independent_quality_evidence: bool = False
    executable_authority: bool = False

    def assert_source_unchanged(self) -> None:
        self.router._check_retrieval_authority_witness(self.witness)
        if _principal_claims_canonical(self._principal) != self._principal_claims_snapshot:
            raise PolicyViolationError("principal claims changed during model request")
        # Frozen dataclass does not freeze nested dictionaries, and replace()
        # can swap an otherwise correctly fingerprinted semantic description.
        # Reject any changed model-visible bytes BEFORE backend disclosure.
        if (
            type(self._scoped_view_receipt) is not str
            or not hmac.compare_digest(
                self._scoped_view_receipt, _checked_scoped_view_receipt(self),
            )
        ):
            raise PolicyViolationError("captured authorized source identity drift")
        # Diagnose a forged view with the original source-integrity error
        # before checking the additional host-policy content receipt.
        current_policy_receipt = _authorization_policy_receipt(
            self.router.authorization_policy,
        )
        if (
            type(self._authorization_policy_receipt) is not str
            or not hmac.compare_digest(
                self._authorization_policy_receipt, current_policy_receipt,
            )
        ):
            raise PolicyViolationError("authorization policy modified in place")

    def catalog_index(
        self, *, max_json_bytes: int = MAX_MODEL_CATALOG_INDEX_JSON_BYTES,
    ) -> tuple[tuple[str, str], ...]:
        """Read-only authorized route ID + description index; NEVER an action.

        The index exposes only the previously captured, policy-projected,
        native source descriptions. It does not carry argument schemas,
        fingerprints, raw fixture data, callable tools or execution grants.
        Fail closed on oversize catalogs rather than silently truncating
        the available routes; disclosure still requires a fresh witness.
        """
        if (
            type(max_json_bytes) is not int
            or not 1 <= max_json_bytes <= MAX_MODEL_TOOL_JSON_BYTES
        ):
            raise ValueError("invalid scoped catalog index byte budget")
        self.assert_source_unchanged()
        routes = self._semantic_source_routes
        if (
            len(routes) != len(self.visible_route_ids)
            or tuple(route.route_id for route in routes) != self.visible_route_ids
        ):
            raise PolicyViolationError("scoped catalog source identity mismatch")
        entries = tuple(
            (route.route_id, route.description) for route in routes
        )
        try:
            encoded = json.dumps(
                entries, ensure_ascii=False, separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            raise PolicyViolationError(
                "scoped catalog index could not be serialized",
            ) from None
        if len(encoded) > max_json_bytes:
            raise ValueError("scoped catalog index exceeds research byte cap")
        self.assert_source_unchanged()
        return entries

    def ranked_catalog_preview(
        self, *, k: int = MAX_TOOL_DEFINITIONS,
        max_json_bytes: int = MAX_MODEL_CATALOG_INDEX_JSON_BYTES,
    ) -> tuple[tuple[str, str], ...]:
        """Read-only top-K route titles, chosen by prior authorized retrieval.

        This does NOT present the physical or full authorized catalog to
        the model. The top K are the currently ranked, principal-visible
        native routes from the captured query. The model/agent remains
        responsible for choosing among them and deciding whether to act.
        No executable receipt, model call or invoker can be returned.
        """
        if type(k) is not int or not 1 <= k <= MAX_TOOL_DEFINITIONS:
            raise ValueError("invalid scoped catalog preview K")
        if (
            type(max_json_bytes) is not int
            or not 1 <= max_json_bytes <= MAX_MODEL_TOOL_JSON_BYTES
        ):
            raise ValueError("invalid scoped catalog index byte budget")
        self.assert_source_unchanged()
        routes = self._semantic_source_routes
        if (
            len(routes) != len(self.visible_route_ids)
            or tuple(route.route_id for route in routes) != self.visible_route_ids
        ):
            raise PolicyViolationError("scoped catalog source identity mismatch")
        entries = tuple(
            (route.route_id, route.description) for route in routes[:k]
        )
        try:
            encoded = json.dumps(
                entries, ensure_ascii=False, separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            raise PolicyViolationError(
                "scoped catalog preview could not be serialized",
            ) from None
        if len(encoded) > max_json_bytes:
            raise ValueError("scoped catalog preview exceeds research byte cap")
        self.assert_source_unchanged()
        return entries

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
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_MODEL_TOOL_JSON_BYTES:
            raise ValueError("model-visible tool definitions exceed research byte cap")
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
            self.assert_source_unchanged()
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
        # One authorized scalar can still exhaust an agent context budget.
        # Bound the actual JSON payload, not only the schema declaration.
        try:
            encoded = json.dumps(
                projected, ensure_ascii=False, separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError, OverflowError):
            raise PolicyViolationError(
                "model-visible observation cannot be serialized safely",
            ) from None
        if len(encoded.encode("utf-8")) > MAX_MODEL_OBSERVATION_JSON_BYTES:
            raise PolicyViolationError(
                "model-visible observation exceeds research byte cap",
            )
        self.assert_source_unchanged()
        return projected

    def public_trace(self, episode_row: dict[str, Any]) -> dict[str, Any]:
        """Safe metrics-only record: NO prompts, gold, args, raw outputs or COT."""
        self.assert_source_unchanged()
        if type(episode_row) is not dict:
            raise ValueError("episode row must be a dictionary")
        allowed = set(self.visible_route_ids)
        result: dict[str, Any] = {
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
        # Finite nonnegative aggregate timing is safe to publish. Keep
        # CPU/cost comparison possible without revealing raw data or gold.
        for name in (
            "candidate_selection_latency_ms", "model_generation_latency_ms",
            "episode_wall_latency_ms",
        ):
            value = episode_row.get(name)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                result[name] = float(value)
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


def _principal_claims_canonical(principal: PrincipalContext) -> str:
    """Detect mutable trusted roles/attributes changing after source selection."""
    return json.dumps(
        principal.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
    policy_receipt_before = _authorization_policy_receipt(router.authorization_policy)
    claims_snapshot = _principal_claims_canonical(principal)
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
    if _authorization_policy_receipt(router.authorization_policy) != policy_receipt_before:
        raise PolicyViolationError("authorization policy modified during source capture")
    if _principal_claims_canonical(principal) != claims_snapshot:
        raise PolicyViolationError("principal claims changed during model request")
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
    semantic_routes: list[CapturedAuthorizedSemanticRoute] = []
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
            "name": candidate.route_id.replace(".", "__"),
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
        semantic_routes.append(CapturedAuthorizedSemanticRoute(
            route_id=candidate.route_id,
            description=scoped_semantic_model_description(
                candidate, field_scoped=field_scoped,
            ),
            tool_fingerprint=candidate.tool_fingerprint,
            endpoint_fingerprint=candidate.endpoint_fingerprint,
        ))
    router._check_retrieval_authority_witness(witness)
    if _authorization_policy_receipt(router.authorization_policy) != policy_receipt_before:
        raise PolicyViolationError("authorization policy modified during source capture")
    if _principal_claims_canonical(principal) != claims_snapshot:
        raise PolicyViolationError("principal claims changed during model request")
    view = AuthorizedAgentToolSurface(
        router=router, witness=witness, _principal=principal,
        _principal_claims_snapshot=claims_snapshot, original_query=query,
        registered_route_count=physical,
        visible_route_ids=tuple(definitions),
        _tool_definitions=definitions,
        _visible_output_names=visible,
        _semantic_source_routes=tuple(semantic_routes),
    )
    object.__setattr__(view, "_scoped_view_receipt", _checked_scoped_view_receipt(view))
    object.__setattr__(view, "_authorization_policy_receipt", policy_receipt_before)
    view.assert_source_unchanged()
    return view
