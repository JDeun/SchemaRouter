"""Opt-in native typed FieldGroup retrieval over the authorized capability catalog.

A trusted host declares query aliases and complete required output semantics.
This is not natural-language semantic inference, an agent, or execution.
"""
from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from pydantic import model_validator

from .authorization import PrincipalContext
from .capability_contracts import CapabilityFieldContract, compare_capability_fields
from .errors import PolicyViolationError
from .models import CapabilityRetrieval, EndpointSpec, FieldSpec, PlanRequest, StrictModel, ToolSpec
from .planner import KeywordAnalyzer

if TYPE_CHECKING:
    from .runtime import SchemaRouter

FIXED_FIELD_GROUP_K = 5


def _alias_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


def _scalar_contract(schema: dict) -> bool:
    # Typed comparator does not prove arbitrary enum/pattern/oneOf constraints.
    if (
        type(schema) is dict
        and set(schema) == {"type"}
        and type(schema["type"]) is str
        and schema["type"] in {"string", "integer", "number", "boolean"}
    ):
        return True
    # OPTIMADE GET IDs use one narrow string constraint; do not admit arbitrary
    # enum/pattern/composition schemas into the native typed graph.
    return (
        type(schema) is dict
        and set(schema) == {"type", "minLength"}
        and schema.get("type") == "string"
        and type(schema.get("minLength")) is int
        and schema["minLength"] == 1
    )


def _root_envelope_empty(endpoint: EndpointSpec) -> bool:
    """Proof of an input-free native endpoint, shared by FieldGroup and G5."""
    if endpoint.parameters or endpoint.auth_requirements:
        return False
    return not endpoint.input_schema or endpoint.input_schema in (
        {"type": "object", "properties": {}, "additionalProperties": False},
        {"type": "object", "properties": {}, "required": [],
         "additionalProperties": False},
    )


class NativeDeclaredFieldGroup(StrictModel):
    """Source-owner approved concept→conjunctive typed output requirements.

    These aliases are *not* discovered or translated by the router. The host
    decides the exact text forms and attests the trusted semantic contracts.
    """

    aliases: tuple[str, ...]
    required_fields: tuple[CapabilityFieldContract, ...]
    source_type: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def validate_bounded_group(self) -> NativeDeclaredFieldGroup:
        if (
            not 1 <= len(self.aliases) <= 16
            or any(
                type(value) is not str
                or not 1 <= len(value) <= 256
                or value != value.strip()
                or not _alias_key(value)
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
                for value in self.aliases
            )
            or len({_alias_key(value) for value in self.aliases}) != len(self.aliases)
            or not 1 <= len(self.required_fields) <= 8
            or len({field.semantic_id for field in self.required_fields})
            != len(self.required_fields)
            or any(
                not _scalar_contract(field.json_schema)
                or any(not key or not val for key, val in field.qualifiers.items())
                for field in self.required_fields
            )
            or any(
                value is not None
                and (
                    type(value) is not str
                    or not 1 <= len(value) <= 160
                    or value != value.strip()
                )
                for value in (self.source_type, self.license)
            )
        ):
            raise ValueError("invalid bounded native FieldGroup declaration")
        return self


def _compatible_field(required: CapabilityFieldContract, field: FieldSpec) -> bool:
    if (
        field.semantic_id is None
        or not _scalar_contract(field.json_schema)
    ):
        return False
    produced = CapabilityFieldContract.from_field(field)
    if produced is None:
        return False
    # No inferred conversions or equivalences. Missing required dimensions
    # remain UNKNOWN in the canonical typed comparator, never a positive hit.
    if required.unit is not None and produced.unit != required.unit:
        return False
    return compare_capability_fields(required, produced).status in {"exact", "compatible"}


def _complete_fields(
    fields: list[FieldSpec], required_fields: tuple[CapabilityFieldContract, ...],
) -> bool:
    return all(
        any(_compatible_field(required, field) for field in fields)
        for required in required_fields
    )


def retrieve_authorized_field_group(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    group: NativeDeclaredFieldGroup,
    k: int = FIXED_FIELD_GROUP_K,
    input_free_only: bool = False,
) -> CapabilityRetrieval:
    """Rank complete, visible, source-matched native endpoints BEFORE K5.

    Uses the existing KeywordAnalyzer/SchemaPlanner and current
    principal-scoped data-source view. It does not create a second router.
    The host must reauthorize any later execution.
    """
    if type(k) is not int or k != FIXED_FIELD_GROUP_K:
        raise ValueError("native FieldGroup E0 requires exactly K5")
    if type(input_free_only) is not bool:
        raise ValueError("input-free FieldGroup option must be boolean")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("invalid bounded native FieldGroup query")
    if not isinstance(group, NativeDeclaredFieldGroup):
        raise ValueError("trusted native FieldGroup required")
    try:
        # Revalidate a fresh snapshot: nested Pydantic values may have been
        # mutated after source-owner approval, even inside a frozen caller.
        declared = NativeDeclaredFieldGroup.model_validate(
            group.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid current native FieldGroup declaration") from exc
    if _alias_key(query) not in {_alias_key(a) for a in declared.aliases}:
        raise ValueError("query has no host-declared FieldGroup edge")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("trusted principal required for FieldGroup retrieval")
    try:
        approved_principal = PrincipalContext.model_validate(
            principal.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError("invalid trusted principal for FieldGroup") from exc
    if router.authorization_policy is None:
        raise PolicyViolationError("FieldGroup requires explicit authorization policy")
    if type(router.planner.analyzer) is not KeywordAnalyzer:
        raise ValueError("native FieldGroup E0 only qualifies deterministic keyword analysis")

    witness = router._retrieval_authority_witness()
    permitted = router._authorization_predicate(approved_principal)
    if permitted is None:
        raise PolicyViolationError("no explicit FieldGroup authorization")
    scoped = router._scoped_analysis_registry(approved_principal, permitted)

    def eligible(tool: ToolSpec, endpoint: EndpointSpec) -> EndpointSpec | None:
        if not permitted(tool, endpoint):
            return None
        if endpoint.read_only is not True or endpoint.destructive is True:
            return None
        if input_free_only and not _root_envelope_empty(endpoint):
            return None
        if declared.source_type is not None and tool.source_type != declared.source_type:
            return None
        if declared.license is not None and tool.license != declared.license:
            return None
        visible = router._data_scope_endpoint_view(approved_principal, tool, endpoint)
        if visible is None or not _complete_fields(
            visible.output_fields, declared.required_fields,
        ):
            return None
        return visible

    # The declared field IDs only enrich the existing analysis; source,
    # permission, visibility, type and license remain independently verified.
    request = PlanRequest(
        query=query,
        concepts=[field.semantic_id for field in declared.required_fields],
    )
    retrieved = router.planner.retrieve_with_scoped_schema(
        request, permitted, eligible, k=k, analysis_registry=scoped,
    )
    projected = router._project_retrieval_data_scope(retrieved, approved_principal)
    if any(
        not _complete_fields(candidate.output_fields, declared.required_fields)
        for candidate in projected.candidates
    ):
        raise PolicyViolationError("FieldGroup result lost a required visible field")
    router._check_retrieval_authority_witness(witness)
    return projected
