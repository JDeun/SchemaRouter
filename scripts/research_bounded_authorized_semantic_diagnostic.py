"""Explicit, read-only source-scoped semantic retrieval PROTOTYPE (#1473).

Never part of the default public retrieve() path. A model-backed result from
this function is unverified routing *diagnostic*, not a host authorization
receipt, action request, a calibrated unsupported/no-fit signal, or agent
success. No external model, HTTP request, credential or native tool is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schemarouter import PolicyViolationError, PrincipalContext, SchemaRouter
from schemarouter.decisions import (
    DecisionBackend,
    DecisionOption,
    DecisionRequest,
    choose_sync,
)

DEFAULT_NATIVE_CATALOG_CAP = 500
DEFAULT_MODEL_INPUT_BYTES_CAP = 131072
MAX_SHORTLIST = 16


@dataclass(frozen=True)
class DiagnosticSemanticShortlist:
    """Explicitly untrusted model suggestion; never an executable ToolCall."""

    status: str
    route_ids: tuple[str, ...]
    registered_candidate_count: int
    model_input_bytes: int
    selected_k_limit: int
    registry_version: int
    source_tool_fingerprints: tuple[str, ...]
    source_endpoint_fingerprints: tuple[str, ...]
    independent_quality_evidence: bool = False
    calibrated_no_fit: bool = False
    executable_authority: bool = False


def propose_bounded_semantic_shortlist(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    backend: DecisionBackend,
    k: int = 5,
    max_catalog_routes: int = DEFAULT_NATIVE_CATALOG_CAP,
    max_model_input_bytes: int = DEFAULT_MODEL_INPUT_BYTES_CAP,
) -> DiagnosticSemanticShortlist:
    """Only reorder existing currently authorized native candidates.

    Backend inference may be model-backed, but it cannot change authorization,
    add source-native tool IDs, exceed strict K, or trigger tool execution.
    All omissions, abstentions and budget violations are explicit rather than
    implicitly relabeled as unsupported/no-fit.
    """
    if type(query) is not str or not query.strip():
        raise ValueError("nonempty original query string required")
    if type(k) is not int or not 1 <= k <= MAX_SHORTLIST:
        raise ValueError("invalid fixed shortlist bound")
    if (
        type(max_catalog_routes) is not int
        or not 1 <= max_catalog_routes <= 500
        or type(max_model_input_bytes) is not int
        or not 1 <= max_model_input_bytes <= 1048576
    ):
        raise ValueError("invalid research resource bounds")

    # This is intentionally a strict physical *upper* bound, checked before
    # any model receives the catalog. It never becomes a public hidden count.
    registered_route_count = sum(
        len(tool.endpoints) for tool in router.registry.tools()
    )
    if registered_route_count > max_catalog_routes:
        raise ValueError("registered catalog exceeds bounded research limit")

    authority = router._retrieval_authority_witness()
    if registered_route_count:
        full = router.retrieve_authorized(
            query, principal=principal, k=registered_route_count,
        )
        router._check_retrieval_authority_witness(authority)
        if (
            full.registry_version != authority[1]
            or full.requested_k != registered_route_count
            or full.total_ranked != len(full.candidates)
            or len(full.candidates) > registered_route_count
            or len({c.route_id for c in full.candidates}) != len(full.candidates)
        ):
            raise PolicyViolationError("retrieval source catalog is incomplete")
        candidates = full.candidates
    else:
        # A configured authorization policy must still validate principal
        # even if the source registry is empty.
        if router.authorization_policy is not None:
            router.retrieve_authorized(query, principal=principal, k=1)
        candidates = []
    router._check_retrieval_authority_witness(authority)

    if not candidates:
        return DiagnosticSemanticShortlist(
            status="empty_visible_catalog_not_no_fit",
            route_ids=(),
            registered_candidate_count=0,
            model_input_bytes=0,
            selected_k_limit=k,
            registry_version=authority[1],
            source_tool_fingerprints=(),
            source_endpoint_fingerprints=(),
        )

    # Source tool/endpoint *free text* may mention field names that data
    # scope hides. Under any configured field-scope policy expose only the
    # actually projected visible field labels; do not trust free prose as
    # already redacted. This conservative fallback sacrifices semantic recall
    # evidence rather than leaking supposedly hidden descriptors.
    field_scoped = bool(
        router.authorization_policy is not None
        and router.authorization_policy.data_rules
    )
    options = []
    for idx, candidate in enumerate(candidates):
        visible_fields = ", ".join(
            field.semantic_id or field.name for field in candidate.output_fields
        )
        description = "\n".join(
            text for text in (
                "" if field_scoped else candidate.tool_description.strip(),
                "" if field_scoped else candidate.endpoint_description.strip(),
                ("Visible fields: " + visible_fields) if visible_fields else "",
            ) if text
        )
        options.append(DecisionOption(
            id=f"native:{idx}",
            label=candidate.route_id,
            description=description,
        ))
    decision = DecisionRequest(
        query=query,
        options=options,
        max_selections=min(k, len(options)),
        context={"surface": "research_only_bounded_native_retrieval"},
    )
    total_input_bytes = len(decision.model_dump_json().encode("utf-8"))
    if total_input_bytes > max_model_input_bytes:
        raise ValueError("authorized model input exceeds bounded research limit")

    # choose_sync verifies the backend response against an independent
    # host-owned snapshot of offered IDs: forged, duplicate and over-K fail.
    result = choose_sync(backend, decision)
    router._check_retrieval_authority_witness(authority)
    if result.abstained or not result.selections:
        status = "backend_abstained_not_calibrated_no_fit"
        picked: list[Any] = []
    else:
        indices = [int(s.option_id.split(":", 1)[1]) for s in result.selections]
        picked = [candidates[i] for i in indices]
        status = (
            "unverified_full_k_model_ranking"
            if len(picked) == min(k, len(candidates))
            else "unverified_partial_k_model_ranking"
        )

    return DiagnosticSemanticShortlist(
        status=status,
        route_ids=tuple(c.route_id for c in picked),
        registered_candidate_count=len(candidates),
        model_input_bytes=total_input_bytes,
        selected_k_limit=k,
        registry_version=authority[1],
        source_tool_fingerprints=tuple(c.tool_fingerprint for c in picked),
        source_endpoint_fingerprints=tuple(
            c.endpoint_fingerprint for c in picked
        ),
    )
