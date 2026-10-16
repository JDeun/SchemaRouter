"""Opt-in, host-supplied exact field-contract selection over authorized tools.

This is a *read-only capability diagnostic*, NEVER an execution authorization.
The caller must independently authenticate its PrincipalContext and validate
the structured request contract. Predicted/model-supplied fields are not
trusted requirements, and no inference or tool execution happens here.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from .authorization import PrincipalContext
from .errors import PolicyViolationError
from .models import (
    CapabilityCandidate,
    CapabilityRetrieval,
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


def _candidate_matches(
    candidate: CapabilityCandidate, contract: HostFieldContract,
) -> bool:
    # Only positive, explicitly read-only public metadata is trusted.
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
            schema = parameter.json_schema
            if not isinstance(schema, dict):
                continue
            if schema.get("type") == "array":
                items = schema.get("items")
                if (
                    not isinstance(items, dict)
                    or items.get("type") not in (None, "string")
                ):
                    continue
                # A declared one-element array cannot satisfy two distinct
                # required values, even if both occur in items.enum.
                if "maxItems" in schema and (
                    type(schema["maxItems"]) is not int
                    or schema["maxItems"] < len(required_values)
                ):
                    continue
                enum = items.get("enum")
            else:
                # A scalar can satisfy at most one distinct required value.
                # Untyped single-value enums remain compatible with the
                # original exact-string contract behavior.
                if (
                    schema.get("type") not in (None, "string")
                    or len(required_values) != 1
                ):
                    continue
                enum = schema.get("enum")
            if (
                isinstance(enum, list)
                and all(type(v) is str for v in enum)
                and required_values.issubset(enum)
            ):
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
    availability = router.planner.availability_predicate
    registry = router.registry
    retrieved = router.retrieve_authorized(
        request, principal=approved_principal, k=k,
    )
    if (
        router.authorization_policy is not policy
        or router.planner.availability_predicate is not availability
        or router.registry is not registry
    ):
        raise PolicyViolationError(
            "retrieval scope changed during authorized retrieval"
        )
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
                    # Fingerprints bind the receipt to the ORIGINAL registered
                    # source, never a data-scope-projected endpoint. Compute
                    # a tool hash once even when it has many returned routes.
                    if tool.key not in tool_fingerprints:
                        tool_fingerprints[tool.key] = tool.fingerprint
                    returned_fingerprints[route_id] = (
                        tool_fingerprints[tool.key], endpoint.fingerprint,
                    )
    except (TypeError, ValueError, AttributeError) as exc:
        raise PolicyViolationError(
            "cannot validate the complete authorized catalog"
        ) from exc
    if (
        verified.registry_version != router.registry.version
        or router.registry is not registry
        or router.authorization_policy is not policy
        or router.planner.availability_predicate is not availability
    ):
        raise PolicyViolationError(
            "retrieval scope changed during authorized catalog enumeration"
        )
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

    matched = [
        item for item in verified.candidates
        if _candidate_matches(item, approved_contract)
    ]
    if not matched:
        return abstain("no_contract_match")
    if len(matched) > 1:
        return abstain(
            "ambiguous_contract_match", [item.route_id for item in matched],
        )
    selected = matched[0]
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
