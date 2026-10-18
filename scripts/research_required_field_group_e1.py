"""Research E1: source-visible required FieldGroup eligibility before native Top-K.

Explicit host-declared concept/field group -> fields -> eligible endpoint edges.
This reuses the existing SchemaPlanner, its typed retrieval and the host's
principal-scoped source views. It neither creates an agent nor grants authority.
The single-endpoint requirement is deliberate: cross-tool joins/chains are
NOT proven by unioning route fields here.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from schemarouter import (
    CapabilityRetrieval, PlanRequest, PrincipalContext, QueryIntent, SchemaRouter,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.models import EndpointSpec, FieldSpec, ToolSpec
from schemarouter.planner import KeywordAnalyzer
from schemarouter.validation import json_schemas_compatible

STRICT_K = 5


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


@dataclass(frozen=True)
class DeclaredRequiredFieldGroup:
    """Trusted *conjunctive* requirements, not inferred synonyms or permissions."""

    aliases: tuple[str, ...]
    required_fields: tuple[CapabilityFieldContract, ...]
    source_type: str | None = None
    license: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.aliases) is not tuple
            or not 1 <= len(self.aliases) <= 16
            or any(type(a) is not str or not _normalize(a) for a in self.aliases)
            or len({_normalize(a) for a in self.aliases}) != len(self.aliases)
            or type(self.required_fields) is not tuple
            or not 1 <= len(self.required_fields) <= 8
            or any(type(f) is not CapabilityFieldContract for f in self.required_fields)
            or len({f.semantic_id for f in self.required_fields})
            != len(self.required_fields)
            or any(
                v is not None and (type(v) is not str or not v.strip())
                for v in (self.source_type, self.license)
            )
        ):
            raise ValueError("invalid bounded declared FieldGroup contract")

    def matches(self, query: str) -> bool:
        return type(query) is str and _normalize(query) in {
            _normalize(alias) for alias in self.aliases
        }


@dataclass(frozen=True)
class DeclaredFieldGroupAnalyzer:
    group: DeclaredRequiredFieldGroup

    def analyze(self, request: PlanRequest, registry: object) -> QueryIntent:
        # Analyzer only enriches query semantics, never grants field existence
        # or access. The retrieval gate checks all currently visible fields.
        intent = KeywordAnalyzer().analyze(request, registry)
        if not self.group.matches(request.query):
            return intent
        return intent.model_copy(update={
            "concepts": list(dict.fromkeys([
                *intent.concepts,
                *(field.semantic_id for field in self.group.required_fields),
            ])),
        })


def _satisfies(required: CapabilityFieldContract, field: FieldSpec) -> bool:
    if field.semantic_id != required.semantic_id:
        return False
    if required.json_schema and not json_schemas_compatible(
        required.json_schema, field.json_schema,
    ):
        return False
    # Unit conversion is only safe when separately verified by a trusted
    # contract. E1 does NOT infer unit equivalence or follow implicit edges.
    if required.unit is not None and field.unit != required.unit:
        return False
    if required.dimension is not None and (
        field.unit_normalization is None
        or field.unit_normalization.dimension != required.dimension
    ):
        return False
    return all(
        field.qualifiers.get(key) == value
        for key, value in required.qualifiers.items()
    )


def retrieve_required_field_group_e1(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    group: DeclaredRequiredFieldGroup,
    k: int = STRICT_K,
) -> CapabilityRetrieval:
    """One explicit hosted E1 condition: pre-K full group coverage.

    No public router defaults changed. Return only fully eligible route
    candidates (if any) and no execution authority. Empty results do not
    constitute an independently calibrated no-fit judgment.
    """
    if type(k) is not int or k != STRICT_K:
        raise ValueError("E1 requires exactly fixed K5")
    if not group.matches(query):
        raise ValueError("query has no declared FieldGroup edge")
    if router.authorization_policy is None:
        raise ValueError("E1 requires explicit principal authorization")
    if not isinstance(router.planner.analyzer, DeclaredFieldGroupAnalyzer):
        raise ValueError("E1 requires a matching declared graph analyzer")
    if router.planner.analyzer.group != group:
        raise ValueError("declared group differs from active query analyzer")

    witness = router._retrieval_authority_witness()
    authorized = router._authorization_predicate(principal)
    assert authorized is not None
    scoped_registry = router._scoped_analysis_registry(principal, authorized)

    def fully_visible_view(
        tool: ToolSpec, endpoint: EndpointSpec,
    ) -> EndpointSpec | None:
        if not authorized(tool, endpoint):
            return None
        view = router._data_scope_endpoint_view(principal, tool, endpoint)
        if view is None:
            return None
        if group.source_type is not None and tool.source_type != group.source_type:
            return None
        if group.license is not None and tool.license != group.license:
            return None
        if not all(
            any(_satisfies(required, field) for field in view.output_fields)
            for required in group.required_fields
        ):
            return None
        return view

    result = router.planner.retrieve_with_scoped_schema(
        query,
        authorized,
        fully_visible_view,
        k=k,
        analysis_registry=scoped_registry,
    )
    # Same native data-scope and source-version witness as the public route.
    projected = router._project_retrieval_data_scope(result, principal)
    router._check_retrieval_authority_witness(witness)
    return projected
