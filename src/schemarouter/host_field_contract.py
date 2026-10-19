"""Opt-in, host-supplied exact field-contract selection over authorized tools.

This is a *read-only capability diagnostic*, NEVER an execution authorization.
The caller must independently authenticate its PrincipalContext and validate
the structured request contract. Predicted/model-supplied fields are not
trusted requirements, and no inference or tool execution happens here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from .authorization import AuthorizationPolicy, PrincipalContext
from .errors import PolicyViolationError
from .models import (
    CapabilityCandidate,
    CapabilityRetrieval,
    ParameterSpec,
    PlanRequest,
    StrictModel,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


class RequiredEnumValue(StrictModel):
    """Exact published query parameter and enumerated value, not free text."""

    parameter: str
    value: str

    @model_validator(mode="after")
    def validate_exact_identity(self) -> RequiredEnumValue:
        if not _ID.fullmatch(self.parameter) or not _ID.fullmatch(self.value):
            raise ValueError("host field requirement must be a bounded exact identifier")
        return self


class HostFieldContract(StrictModel):
    """Trusted host's explicit *read-only* field contract.

    No defaults: the host must deliberately supply at least one exact input
    enum or output field. The API will NOT infer missing domain/time/intent.
    """

    operation: Literal["read"]
    required_enums: list[RequiredEnumValue] = Field(default_factory=list, max_length=8)
    required_output_fields: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_field_contract(self) -> HostFieldContract:
        if not self.required_enums and not self.required_output_fields:
            raise ValueError("host contract needs at least one declared field")
        pairs = [(item.parameter, item.value) for item in self.required_enums]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate required parameter/enum identity")
        if (
            any(not _ID.fullmatch(field) for field in self.required_output_fields)
            or len(set(self.required_output_fields)) != len(self.required_output_fields)
        ):
            raise ValueError("invalid or duplicate required output field")
        return self


class AuthorizedContractSelection(StrictModel):
    """A non-executable selection receipt for the *current* registry version."""

    disposition: Literal["selected", "abstained"]
    reason: Literal[
        "unique_contract_match",
        "empty_authorized_catalog",
        "incomplete_authorized_catalog",
        "no_contract_match",
        "ambiguous_contract_match",
    ]
    query: str
    registry_version: int
    requested_k: int
    candidate_count: int
    matching_route_ids: list[str] = Field(default_factory=list)
    selected_route_id: str | None = None
    selected_tool_fingerprint: str | None = None
    selected_endpoint_fingerprint: str | None = None


# Only these JSON Schema keywords have a known nonrestrictive meaning
# (annotations), or are fully checked below for this *proof of fit*.
# An unknown keyword may constrain an enum further; abstain instead of
# converting a partial schema understanding into a "unique" tool receipt.
_SCHEMA_ANNOTATIONS = frozenset({
    "title", "description", "default", "examples", "deprecated",
    "readOnly", "writeOnly", "$comment", "nullable",
})
_SCALAR_ENUM_KEYS = _SCHEMA_ANNOTATIONS | {"type", "enum", "const"}
_ARRAY_ENUM_KEYS = _SCHEMA_ANNOTATIONS | {
    "type", "items", "minItems", "maxItems", "uniqueItems",
}


def _enum_schema_can_hold_required(
    schema: dict[str, Any], required_values: set[str],
) -> bool:
    """Conservatively prove required string enums fit one simple JSON schema.

    This is not general JSON Schema validation. A schema using composition,
    pattern, references or other unhandled assertions cannot prove a match.
    """
    is_array = schema.get("type") == "array"
    # Bound defaults also make the array-only cardinality proof obvious
    # to static analyzers without changing scalar matching behavior.
    minimum = 0
    unique = False
    if any(type(key) is not str for key in schema):
        return False
    if not set(schema).issubset(
        _ARRAY_ENUM_KEYS if is_array else _SCALAR_ENUM_KEYS
    ):
        return False
    if is_array:
        items = schema.get("items")
        if (
            type(items) is not dict
            or not set(items).issubset(_SCALAR_ENUM_KEYS)
            or items.get("type") not in (None, "string")
            or "const" in items
        ):
            return False
        minimum = schema.get("minItems", 0)
        maximum = schema.get("maxItems", None)
        unique = schema.get("uniqueItems", False)
        if (
            type(minimum) is not int or minimum < 0
            or (maximum is not None and (
                type(maximum) is not int or maximum < 0 or minimum > maximum
            ))
            or type(unique) is not bool
            or (maximum is not None and maximum < len(required_values))
        ):
            return False
        enum = items.get("enum")
    else:
        if schema.get("type") not in (None, "string"):
            return False
        if len(required_values) != 1:
            return False
        enum = schema.get("enum")
        if "const" in schema and (
            type(schema["const"]) is not str
            or schema["const"] not in required_values
        ):
            return False
    if (
        type(enum) is not list
        or not all(type(value) is str for value in enum)
        or not required_values.issubset(enum)
    ):
        return False
    if is_array and unique and len(set(enum)) < max(minimum, len(required_values)):
        return False
    return True


def _candidate_matches(
    candidate: CapabilityCandidate, contract: HostFieldContract,
) -> bool:
    # Caller provides an internally attested, scope-limited candidate.
    # The final public retrieval result is never modified.

    if candidate.read_only is not True or candidate.destructive is True:
        return False

    # A host's conjunction describes values needed in *one* call, not
    # independent membership checks against the same scalar enum. Each
    # parameter's entire required value set must fit one declared schema.
    required_by_parameter: dict[str, set[str]] = {}
    for required in contract.required_enums:
        required_by_parameter.setdefault(required.parameter, set()).add(
            required.value,
        )

    for parameter_name, required_values in required_by_parameter.items():
        match = False
        for parameter in candidate.parameters:
            if (
                parameter.location != "query"
                or parameter.name != parameter_name
            ):
                continue
            if (
                type(parameter.json_schema) is not dict
                or not _enum_schema_can_hold_required(
                    parameter.json_schema, required_values,
                )
            ):
                continue
            match = True
            break
        if not match:
            return False

    available_fields = {
        name for field in candidate.output_fields
        for name in (field.name, field.semantic_id)
        if name is not None
    }
    return all(name in available_fields for name in contract.required_output_fields)


def _policy_contents_digest(policy: AuthorizationPolicy) -> str:
    """Private digest of same-object RBAC, data scopes and compiled indexes.

    Frozen policy dataclasses still have mutable nested rule/index objects.
    This digest is never exposed as a selection receipt or model input.
    """
    try:
        if type(policy) is not AuthorizationPolicy:
            raise ValueError("invalid policy class")

        def index_rows(index: Any) -> list[dict[str, Any]]:
            if type(index.partitions) is not dict or type(index.rules) is not tuple:
                raise ValueError("invalid compiled authority index")
            rows: list[dict[str, Any]] = []
            for key, positions in index.partitions.items():
                if (
                    type(key) is not tuple or len(key) != 3
                    or any(value is not None and type(value) is not str for value in key)
                    or type(positions) is not tuple
                    or any(type(value) is not int or value < 0 for value in positions)
                ):
                    raise ValueError("invalid compiled authority entry")
                rows.append({"key": list(key), "positions": list(positions)})
            rows.sort(key=lambda row: json.dumps(row["key"]))
            return rows

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
        encoded = json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError, ValueError, AttributeError,
        OverflowError, RecursionError, RuntimeError,
    ):
        raise PolicyViolationError(
            "cannot attest current authorization policy"
        ) from None
    return hashlib.sha256(encoded).hexdigest()


def select_authorized_field_contract(
    router: SchemaRouter,
    request: PlanRequest | str,
    *,
    principal: PrincipalContext,
    contract: HostFieldContract,
    k: int = 128,
) -> AuthorizedContractSelection:
    """Return a conservative, non-executable typed-match diagnostic.

    Invokes only the public principal-scoped retrieval API; NEVER plans,
    dispatches or runs a tool. A truncated Top-K cannot prove uniqueness
    across the entire authorized catalog, so it always abstains. The host
    must reauthorize and validate registry version before any later action.
    """
    if router.authorization_policy is None:
        raise PolicyViolationError(
            "host field contract requires an explicit authorization policy"
        )
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("trusted principal context is required")
    try:
        approved_principal = PrincipalContext.model_validate(
            principal.model_dump(mode="python", warnings=False),
            strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError("invalid principal context") from exc
    if not isinstance(contract, HostFieldContract):
        raise PolicyViolationError("trusted host field contract is required")
    try:
        approved_contract = HostFieldContract.model_validate(
            contract.model_dump(mode="python", warnings=False),
            strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError("invalid or forged host field contract") from exc
    if type(k) is not int or not 1 <= k <= 5000:
        raise ValueError("contract search k must be an integer in 1..5000")
    if isinstance(request, str):
        raw_query = request
    elif isinstance(request, PlanRequest):
        try:
            request = PlanRequest.model_validate(
                request.model_dump(mode="python", warnings=False),
                strict=True,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise PolicyViolationError("invalid request envelope") from exc
        raw_query = request.query
    else:
        raise PolicyViolationError("request must be text or a PlanRequest")
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise PolicyViolationError("nonempty user query required")
    # Bind source object identities before the public retrieval call. Without
    # this guard, a policy/availability/registry replacement *during* ranking
    # could be mistaken for a single internally consistent authorization view.
    policy = router.authorization_policy
    assert policy is not None
    policy_digest = _policy_contents_digest(policy)

    def check_current_policy() -> None:
        if (
            router.authorization_policy is not policy
            or _policy_contents_digest(policy) != policy_digest
        ):
            raise PolicyViolationError(
                "authorization policy changed during field contract selection"
            )

    availability = router.planner.availability_predicate
    registry = router.registry
    try:
        retrieved = router.retrieve_authorized(
            request, principal=approved_principal, k=k,
        )
    except Exception:
        # A provider-controlled availability predicate or unexpected adapter
        # error must not echo private exception text into a host receipt.
        raise PolicyViolationError(
            "cannot attest authorized retrieval"
        ) from None
    if (
        router.authorization_policy is not policy
        or router.planner.availability_predicate is not availability
        or router.registry is not registry
    ):
        raise PolicyViolationError(
            "retrieval scope changed during authorized retrieval"
        )
    check_current_policy()
    if not isinstance(retrieved, CapabilityRetrieval):
        raise PolicyViolationError("invalid authorized retrieval result")
    # A mutable registry can change mid-request. Never issue a receipt if
    # the result is from another registry version or another query.
    if (
        retrieved.query != raw_query
        or type(retrieved.registry_version) is not int
        or retrieved.registry_version != router.registry.version
        or retrieved.requested_k != k
        or type(retrieved.total_ranked) is not int
        or retrieved.total_ranked < 0
    ):
        raise PolicyViolationError("stale or inconsistent retrieval scope")

    try:
        verified = CapabilityRetrieval.model_validate(
            retrieved.model_dump(mode="python", warnings=False),
            strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError("untrusted authorized retrieval envelope") from exc
    ids = [item.route_id for item in verified.candidates]
    if (
        len(ids) != len(set(ids))
        or any(
            item.route_id != f"{item.tool}.{item.endpoint}"
            or not item.tool_fingerprint or not item.endpoint_fingerprint
            for item in verified.candidates
        )
        or verified.total_ranked < len(ids)
        or len(ids) > k
    ):
        raise PolicyViolationError("untrusted route identity or shortlist")

    def abstain(reason: Literal[
        "empty_authorized_catalog",
        "incomplete_authorized_catalog",
        "no_contract_match",
        "ambiguous_contract_match",
    ], matches: list[str] | None = None) -> AuthorizedContractSelection:
        check_current_policy()
        return AuthorizedContractSelection(
            disposition="abstained", reason=reason,
            query=raw_query, registry_version=verified.registry_version,
            requested_k=k, candidate_count=len(ids),
            matching_route_ids=matches or [],
        )

    # Principal-visible completeness is an INTERNAL, version-bound witness.
    # The public total_ranked can be rebuilt after Top-K data projection, so
    # neither that count nor k can prove the full permitted candidate set.
    # Mirror the retrieval path's RBAC, local availability and data-scope
    # endpoint projection without exposing excluded identities or counts.
    # This is a read-only full scan, not a cached or model-scored shortcut.
    try:
        scoped_route_ids: set[str] = set()
        returned_ids = set(ids)
        # This same authoritative, principal-scoped scan also attests the
        # metadata used by _candidate_matches. Checking route IDs alone
        # cannot detect a forged field/enum or a forged read-only flag on an
        # otherwise permitted route. Avoid copying schemas for nonreturned
        # routes; no unauthorized metadata is included in the receipt.
        returned_contracts: dict[str, tuple[object, ...]] = {}
        trusted_scoped_params: dict[str, tuple[ParameterSpec, ...]] = {}
        trusted_relationship_allowlists: dict[str, frozenset[str] | None] = {}
        returned_fingerprints: dict[str, tuple[str, str]] = {}
        tool_fingerprints: dict[str, str] = {}
        for tool in registry.tools():
            for endpoint in tool.endpoints:
                if not policy.visible(approved_principal, tool, endpoint):
                    continue
                if availability is not None and not availability(tool, endpoint):
                    continue
                visible = router._data_scope_endpoint_view(
                    approved_principal, tool, endpoint,
                )
                if visible is None:
                    continue
                route_id = f"{tool.key}.{endpoint.name}"
                scoped_route_ids.add(route_id)
                if route_id in returned_ids:
                    returned_contracts[route_id] = (
                        visible.read_only, visible.destructive,
                        visible.parameters, visible.output_fields,
                    )
                    # Public metadata is deliberately a privacy-safe
                    # projection. The trusted host can separately check
                    # the FULL original required enum constraints, but only
                    # for parameter identities still visible to this actor.
                    # Never serialize these raw contracts in the receipt.
                    visible_param_names = {
                        param.name for param in visible.parameters
                    }
                    trusted_scoped_params[route_id] = tuple(
                        param for param in endpoint.parameters
                        if param.name in visible_param_names
                    )
                    # The private source schema alone is NOT the full
                    # principal contract: relationship-type restrictions
                    # from this actor's current DataScopeRule still apply.
                    trusted_relationship_allowlists[route_id] = (
                        policy.data_scope(
                            approved_principal, tool, endpoint,
                        ).allowed_relationships
                    )
                    # Fingerprints bind the receipt to the ORIGINAL registered
                    # source, never a data-scope-projected endpoint. Compute
                    # a tool hash once even when it has many returned routes.
                    if tool.key not in tool_fingerprints:
                        tool_fingerprints[tool.key] = tool.fingerprint
                    returned_fingerprints[route_id] = (
                        tool_fingerprints[tool.key], endpoint.fingerprint,
                    )
    except Exception:
        # Full-scan predicates and projected-source adapters may raise
        # arbitrary exceptions containing hidden route/field details.
        raise PolicyViolationError(
            "cannot validate the complete authorized catalog"
        ) from None
    if (
        verified.registry_version != router.registry.version
        or router.registry is not registry
        or router.authorization_policy is not policy
        or router.planner.availability_predicate is not availability
    ):
        raise PolicyViolationError(
            "retrieval scope changed during authorized catalog enumeration"
        )
    check_current_policy()
    if not set(ids) <= scoped_route_ids:
        raise PolicyViolationError(
            "retrieval contains a route outside current host authorization"
        )
    for item in verified.candidates:
        # A structurally valid Pydantic retrieval can carry forged metadata
        # even when its route identity and fingerprint-shaped strings look
        # plausible. Authoritative per-principal typed data is the source of
        # truth for *every* candidate, including competing matches.
        expected = returned_contracts[item.route_id]
        observed = (
            item.read_only, item.destructive,
            item.parameters, item.output_fields,
        )
        if observed != expected:
            raise PolicyViolationError(
                "retrieval contract differs from current authorized schema"
            )
        if (
            item.tool_fingerprint, item.endpoint_fingerprint
        ) != returned_fingerprints[item.route_id]:
            raise PolicyViolationError(
                "retrieval fingerprints differ from current authorized source"
            )
    # A positive count excess indicates truncation even if it disagrees with
    # this internal witness; never use a public count to waive completeness.
    if (
        verified.total_ranked > len(ids)
        or len(scoped_route_ids) > len(ids)
    ):
        return abstain("incomplete_authorized_catalog")
    if not ids:
        return abstain("empty_authorized_catalog")

    def scoped_required_relationships_allowed(route_id: str) -> bool:
        allowed = trusted_relationship_allowlists[route_id]
        return allowed is None or all(
            requirement.parameter != "relationship_types"
            or requirement.value in allowed
            for requirement in approved_contract.required_enums
        )

    matched = [
        item for item in verified.candidates
        if scoped_required_relationships_allowed(item.route_id)
        and _candidate_matches(
            # The host alone evaluates ORIGINAL enum restrictions on only
            # currently scoped-visible parameter identities. The public
            # returned candidate and selector receipt never contain these.
            item.model_copy(
                deep=True,
                update={
                    "parameters": list(trusted_scoped_params[item.route_id]),
                },
            ),
            approved_contract,
        )
    ]
    if not matched:
        return abstain("no_contract_match")
    if len(matched) > 1:
        return abstain(
            "ambiguous_contract_match", [item.route_id for item in matched],
        )
    selected = matched[0]
    check_current_policy()
    if (
        verified.registry_version != router.registry.version
        or router.registry is not registry
        or router.authorization_policy is not policy
        or router.planner.availability_predicate is not availability
    ):
        raise PolicyViolationError("retrieval scope changed during contract validation")
    return AuthorizedContractSelection(
        disposition="selected", reason="unique_contract_match",
        query=raw_query, registry_version=verified.registry_version,
        requested_k=k, candidate_count=len(ids),
        matching_route_ids=[selected.route_id],
        selected_route_id=selected.route_id,
        selected_tool_fingerprint=selected.tool_fingerprint,
        selected_endpoint_fingerprint=selected.endpoint_fingerprint,
    )
