"""Historical lexical FieldGroup and concept retrieval, source-only comparator.

Not part of the installed SDK. Preserve the old pre-K lexical ranking,
CapabilityRetrieval receipts and test semantics for historical experiments.
"""
from __future__ import annotations

from schemarouter.authorization import PrincipalContext
from schemarouter.concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import (
    FIXED_FIELD_GROUP_K,
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _root_envelope_empty,
)
from schemarouter.models import CapabilityRetrieval, EndpointSpec, PlanRequest, ToolSpec
from scripts.research_legacy_planning.planner import KeywordAnalyzer
from schemarouter.runtime import SchemaRouter


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


def retrieve_authorized_concepts(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    k: int = 5,
) -> CapabilityRetrieval:
    """Compose existing opt-in principal-scoped pre-K FieldGroup retrieval."""
    resolved = resolve_native_concepts(query, catalog=catalog)
    return retrieve_authorized_field_group(
        router, query, principal=principal, group=resolved.field_group, k=k,
    )
