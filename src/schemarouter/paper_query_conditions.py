"""Current scoped source evidence for untrusted query conditions; never bind values."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .canonical_json import canonical_json_text
from .capability_contracts import CapabilityFieldContract
from .concept_retrieval import NativeDeclaredConcept
from .errors import PolicyViolationError
from .field_group_retrieval import _compatible_field, _scalar_contract
from .host_field_contract import _policy_contents_digest
from .models import FieldSpec, ParameterSpec, PlanCoverage, SemanticFieldRequirement
from .paper_query_needs import PaperQueryNeed
from .paper_typed_tool_plan import (
    PaperPlanFieldMeta,
    PaperTypedToolPlan,
    _check_current_call_scopes,
)
from .validation import canonical_unit_value_schema, validate_json_schema_value

if TYPE_CHECKING:
    from .runtime import SchemaRouter


def _same_json_scalar(left: Any, right: Any) -> bool:
    """Exact JSON equality without bool/number conflation or float coercion."""
    if type(left) not in (str, int, float, bool) or type(right) not in (str, int, float, bool):
        return False
    if type(left) is float and not math.isfinite(left):
        return False
    if type(right) is float and not math.isfinite(right):
        return False
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    return left == right


@dataclass(frozen=True)
class _ScopedQueryCall:
    position: int
    fields: tuple[FieldSpec, ...]
    all_fields: tuple[FieldSpec, ...]
    metadata: tuple[PaperPlanFieldMeta, ...]
    parameters: tuple[tuple[ParameterSpec, bool], ...]


def _query_source_observer(
    router: SchemaRouter,
    plan: PaperTypedToolPlan,
    principal: PrincipalContext,
) -> tuple[Callable[[], tuple[_ScopedQueryCall, ...]], Callable[[], None]]:
    """Detached public descriptors, reobserved after every host callback."""
    witness = router._retrieval_authority_witness()
    policy = router.authorization_policy
    if policy is None or router.registry.version != plan.registry_version:
        raise PolicyViolationError("query input source eligibility changed")
    try:
        claims = principal.model_dump_json()
        policy_digest = _policy_contents_digest(policy)
        original_calls = tuple(item.call.model_dump_json() for item in plan.calls)
        availability = router.planner.availability_predicate
    except Exception:
        raise PolicyViolationError("query input source eligibility changed") from None

    def verify() -> None:
        router._check_retrieval_authority_witness(witness)
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or principal.model_dump_json() != claims
            or tuple(item.call.model_dump_json() for item in plan.calls) != original_calls
            or router.planner.availability_predicate is not availability
        ):
            raise PolicyViolationError("query input source eligibility changed")

    def collect() -> tuple[_ScopedQueryCall, ...]:
        _check_current_call_scopes(router, principal, list(plan.calls))
        permitted = router._authorization_predicate(principal)
        if permitted is None:
            raise PolicyViolationError("query input source eligibility changed")
        result = []
        for position, item in enumerate(plan.calls):
            tool = router.registry.get(item.call.tool)
            endpoint = tool.endpoint(item.call.endpoint)
            if (
                tool.fingerprint != item.call.tool_fingerprint
                or endpoint.fingerprint != item.call.schema_fingerprint
                or not permitted(tool.model_copy(deep=True), endpoint.model_copy(deep=True))
                or availability is not None
                and not availability(
                    tool.model_copy(deep=True),
                    endpoint.model_copy(deep=True),
                )
            ):
                raise PolicyViolationError("query input source eligibility changed")
            scoped = router._data_scope_endpoint_view(principal, tool, endpoint)
            if scoped is None:
                raise PolicyViolationError("query input source eligibility changed")
            scoped = scoped.model_copy(deep=True)
            selected = tuple(
                field for field in scoped.output_fields if field.name in item.call.fields
            )
            metadata = tuple(
                PaperPlanFieldMeta(
                    name=field.name,
                    semantic_id=field.semantic_id,
                    source_unit=field.unit,
                    unit=field.unit_normalization.canonical_unit
                    if field.unit_normalization
                    else field.unit,
                    source_type=field.source_type or tool.source_type,
                    license=field.license or tool.license,
                    qualifiers=tuple(sorted(field.qualifiers.items())),
                    source_path=field.projection_path,
                    result_path=field.result_projection_path,
                    json_schema=canonical_unit_value_schema(
                        field.json_schema, field.unit_normalization
                    ),
                )
                for field in selected
            )
            if canonical_json_text([asdict(meta) for meta in metadata]) != canonical_json_text(
                [asdict(meta) for meta in item.fields_meta],
            ):
                raise PolicyViolationError("query input source eligibility changed")
            original = {parameter.name: parameter for parameter in endpoint.parameters}
            result.append(
                _ScopedQueryCall(
                    position,
                    selected,
                    tuple(scoped.output_fields),
                    metadata,
                    tuple(
                        (
                            parameter,
                            canonical_json_text(parameter.json_schema)
                            == canonical_json_text(original[parameter.name].json_schema),
                        )
                        for parameter in scoped.parameters
                    ),
                )
            )
        verify()
        return tuple(result)

    return collect, verify


def _input_matches(
    key: str, scopes: tuple[_ScopedQueryCall, ...]
) -> list[tuple[int, ParameterSpec, bool]]:
    return [
        (scope.position, parameter, exposed)
        for scope in scopes
        for parameter, exposed in scope.parameters
        if key == parameter.name or key in parameter.aliases or key == parameter.semantic_id
    ]


def _input_proof(
    plan: PaperTypedToolPlan,
    matches: list[tuple[int, ParameterSpec, bool]],
    proposed: Any,
) -> tuple[bool, bool, str]:
    if len(matches) != 1:
        return False, False, "ambiguous_source_input" if matches else "unproven_source_relation"
    position, parameter, exposed = matches[0]
    call = plan.calls[position].call
    if parameter.name in call.arguments:
        present = _same_json_scalar(proposed, call.arguments[parameter.name])
        return present, False, "matching_host_input" if present else "conflicting_host_input"
    if not exposed:
        return False, False, "unproven_scoped_input_fit"
    try:
        if _scalar_contract(parameter.json_schema):
            validate_json_schema_value(
                proposed, parameter.json_schema, context="query proposed input"
            )
            return True, True, "pending_host_input"
    except Exception:
        pass  # Never expose private validator diagnostics or proposed values.
    return False, False, "invalid_proposed_input"


def _input_requirement(
    plan: PaperTypedToolPlan,
    key: str,
    matches: list[tuple[int, ParameterSpec, bool]],
    proof: str,
    need_index: int | None = None,
) -> SemanticFieldRequirement:
    qualifiers = ["query_input_condition=true", f"proof={proof}"]
    if need_index is not None:
        qualifiers.append(f"need_index={need_index}")
    if len(matches) == 1:
        position, parameter, _ = matches[0]
        qualifiers.extend((f"route={plan.calls[position].route_id}", f"parameter={parameter.name}"))
    return SemanticFieldRequirement(semantic_id=key, qualifiers=qualifiers)


def _path_condition(key: str, value: str, field: FieldSpec, fields: tuple[FieldSpec, ...]) -> bool:
    """Exact RFC6901 segments or dotted notation without visible dot collisions."""

    def path(item: FieldSpec) -> tuple[str, ...]:
        return item.projection_path if key == "source_path" else item.result_projection_path

    if value.startswith("/"):
        if re.search(r"~(?![01])", value):
            return False
        return tuple(
            part.replace("~1", "/").replace("~0", "~") for part in value[1:].split("/")
        ) == path(field)
    parts = tuple(value.split("."))
    return (
        bool(all(parts))
        and parts == path(field)
        and all(path(item) == parts for item in fields if ".".join(path(item)) == value)
    )


@dataclass(frozen=True)
class _NeedConditionProof:
    present: bool = False
    pending: bool = False
    tools: frozenset[str] = frozenset()
    inputs: tuple[tuple[SemanticFieldRequirement, bool], ...] = ()


def _failed_input_evidence(
    requirement: SemanticFieldRequirement,
    proof: str,
) -> tuple[SemanticFieldRequirement, bool]:
    return requirement.model_copy(
        update={
            "qualifiers": [
                f"proof={proof}" if item.startswith("proof=") else item
                for item in requirement.qualifiers
            ]
        }
    ), False


def _prove_query_need_conditions(
    router: SchemaRouter,
    plan: PaperTypedToolPlan,
    needs: tuple[tuple[PaperQueryNeed, NativeDeclaredConcept | None], ...],
    *,
    principal: PrincipalContext,
    global_source_type: str | None,
    parameter_hints: dict[str, Any],
    verify: Callable[[], None],
) -> tuple[_NeedConditionProof, ...]:
    """Each need's output and input conditions share one current selected field."""
    collect, check = _query_source_observer(router, plan, principal)
    before = canonical_json_text(
        [
            [need.model_dump(mode="json"), owner.model_dump(mode="json") if owner else None]
            for need, owner in needs
        ]
    )
    hints_before = canonical_json_text(parameter_hints)
    try:
        scopes = collect()
        proofs = []
        assignments: dict[tuple[int, str], list[tuple[int, Any]]] = {}
        for index, (need, owner) in enumerate(needs):
            candidates = []
            evidence: list[tuple[SemanticFieldRequirement, bool]] = []
            if owner is None:
                proofs.append(_NeedConditionProof())
                continue
            for scope in scopes:
                call = plan.calls[scope.position]
                for field, meta in zip(scope.fields, scope.metadata, strict=True):
                    produced = CapabilityFieldContract.from_field(field)
                    if (
                        produced is None
                        or need.unit is not None
                        and produced.unit != need.unit
                        or any(
                            source is not None
                            and (meta.source_type != source or call.source_type != source)
                            for source in (owner.source_type, need.source_type, global_source_type)
                        )
                        or owner.license is not None
                        and (meta.license != owner.license or call.license != owner.license)
                        or not any(
                            _compatible_field(required, field) for required in owner.required_fields
                        )
                    ):
                        continue
                    present, pending = True, False
                    targets = []
                    for key, value in need.qualifiers.items():
                        matches = _input_matches(key, (scope,))
                        if key in ("source_path", "result_path"):
                            present &= not matches and _path_condition(
                                key, value, field, scope.all_fields
                            )
                        elif key in produced.qualifiers and matches:
                            present = False  # The raw condition has two declared interpretations.
                        elif matches:
                            fits, waits, proof = _input_proof(plan, matches, value)
                            evidence.append(
                                (_input_requirement(plan, key, matches, proof, index), fits)
                            )
                            present &= fits
                            pending |= waits
                            if len(matches) == 1:
                                position, parameter, _ = matches[0]
                                targets.append((position, parameter.name, value))
                        else:
                            present &= produced.qualifiers.get(key) == value
                    if present:
                        candidates.append((scope.position, pending, tuple(targets)))
            # A raw need never broadcasts one proposed input to multiple selected routes.
            signatures = {targets for _, _, targets in candidates}
            valid = bool(candidates) and len(signatures) == 1
            if valid:
                for position, name, value in candidates[0][2]:
                    assignments.setdefault((position, name), []).append((index, value))
                # Evidence belongs to the full-field witness, not a rejected alternative.
                evidence = [
                    (item, fits)
                    for item, fits in evidence
                    if any(
                        f"route={plan.calls[position].route_id}" in item.qualifiers
                        and f"parameter={name}" in item.qualifiers
                        for position, name, _ in candidates[0][2]
                    )
                ]
            unique = {
                canonical_json_text(item.model_dump(mode="json")): (item, fits)
                for item, fits in evidence
            }
            inputs = tuple(unique.values())
            if len(signatures) > 1:
                inputs = tuple(
                    _failed_input_evidence(item, "ambiguous_source_input") for item, _ in inputs
                )
            proofs.append(
                _NeedConditionProof(
                    valid,
                    valid and any(wait for _, wait, _ in candidates),
                    frozenset(plan.calls[position].call.tool for position, _, _ in candidates)
                    if valid
                    else frozenset(),
                    inputs,
                )
            )
        for key, value in parameter_hints.items():
            matches = _input_matches(key, scopes)
            if len(matches) == 1:
                position, parameter, _ = matches[0]
                assignments.setdefault((position, parameter.name), []).append((-1, value))
        for (position, name), values in assignments.items():
            if any(not _same_json_scalar(value, values[0][1]) for _, value in values):
                for index, _ in values:
                    if index >= 0:
                        inputs = tuple(
                            _failed_input_evidence(item, "conflicting_query_input")
                            if (
                                f"route={plan.calls[position].route_id}" in item.qualifiers
                                and f"parameter={name}" in item.qualifiers
                            )
                            else (item, fits)
                            for item, fits in proofs[index].inputs
                        )
                        proofs[index] = replace(
                            proofs[index],
                            present=False,
                            pending=False,
                            tools=frozenset(),
                            inputs=inputs,
                        )
        if (
            collect() != scopes
            or before
            != canonical_json_text(
                [
                    [need.model_dump(mode="json"), owner.model_dump(mode="json") if owner else None]
                    for need, owner in needs
                ]
            )
            or canonical_json_text(parameter_hints) != hints_before
        ):
            raise PolicyViolationError("query need source eligibility changed")
        check()
        verify()
        return tuple(proofs)
    except Exception:
        verify()
        raise PolicyViolationError("query need source eligibility changed") from None


def _apply_query_input_conditions(
    router: SchemaRouter,
    plan: PaperTypedToolPlan,
    *,
    principal: PrincipalContext,
    parameter_hints: dict[str, Any],
) -> PaperTypedToolPlan:
    """Global hints retain their unique-target rule and never supply arguments."""
    if not parameter_hints:
        return plan
    if plan.coverage is None or plan.executable_authority:
        raise PolicyViolationError("query conditions require original nonexecuting coverage")
    collect, verify = _query_source_observer(router, plan, principal)
    try:
        hint_contents = canonical_json_text(parameter_hints)
        scopes = collect()
        required, covered, uncovered = (
            list(plan.coverage.required),
            list(plan.coverage.covered),
            list(plan.coverage.uncovered),
        )
        pending = False
        for key, proposed in parameter_hints.items():
            matches = _input_matches(key, scopes)
            present, waits, proof = _input_proof(plan, matches, proposed)
            pending |= waits
            requirement = _input_requirement(plan, key, matches, proof)
            required.append(requirement)
            (covered if present else uncovered).append(requirement)
        if collect() != scopes or canonical_json_text(parameter_hints) != hint_contents:
            raise PolicyViolationError("query input source eligibility changed")
        verify()
    except Exception:
        raise PolicyViolationError("query input source eligibility changed") from None
    complete = plan.coverage.complete and not uncovered
    status = plan.status
    if status == "ready":
        status = "no_proven_hit" if not complete else "requires_arguments" if pending else "ready"
    return replace(
        plan,
        status=status,
        coverage=PlanCoverage(
            required=required, covered=covered, uncovered=uncovered, complete=complete
        ),
    )
