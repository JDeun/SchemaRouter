"""Bounded, host-owned Understand(q) callback for schema-only field routing.

Model output proposes query needs, or explicitly disclosed IDs in legacy mode;
only current authorized source contracts can produce a field plan. No tool
call, data read, or answer synthesis occurs.
"""
from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from .authorization import PrincipalContext
from .canonical_json import canonical_json_sha256
from .capability_contracts import CapabilityFieldContract
from .concept_retrieval import (
    MAX_QUERY_BYTES,
    MAX_QUERY_CHARS,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    _alias_mentions,
    _normalized,
)
from .errors import ModelAnalysisError, PolicyViolationError
from .field_group_retrieval import NativeDeclaredFieldGroup, _compatible_field
from .host_field_contract import _policy_contents_digest
from .models import PlanCoverage, SemanticFieldRequirement
from .paper_native_rank import PaperNativeRankPolicy
from .paper_query_conditions import _apply_query_input_conditions
from .paper_query_needs import (
    PaperQueryNeed,
    PaperQueryUnderstanding,
    _resolve_query_need,
)
from .paper_typed_tool_plan import PaperPlanFieldMeta, PaperTypedToolPlan
from .paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    _bounded_name,
)
from .validation import canonical_unit_value_schema

if TYPE_CHECKING:
    from .field_routing_session import SchemaFieldRoutingSession
    from .runtime import SchemaRouter


PaperFieldModel = Callable[
    [dict[str, Any]], dict[str, Any] | str | Awaitable[dict[str, Any] | str],
]
_Response = TypeVar("_Response", bound=BaseModel)


def _decode_bounded_response(raw: dict[str, Any] | str, limit: int) -> PaperUnderstanding:
    return _decode_model_response(raw, limit, PaperUnderstanding)


def _decode_model_response(
    raw: dict[str, Any] | str, limit: int, response_type: type[_Response],
) -> _Response:
    """Reject duplicate keys, nonfinite numbers, excess bytes and type coercion."""

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate model field")
            result[key] = value
        return result

    def reject_nonfinite(_value: str) -> None:
        raise ValueError("nonfinite model value")

    try:
        if type(raw) is str:
            if len(raw.encode("utf-8")) > limit:
                raise ModelAnalysisError("paper model output exceeds byte budget")
            payload = json.loads(
                raw, object_pairs_hook=unique_pairs, parse_constant=reject_nonfinite,
            )
        elif type(raw) is dict:
            payload = raw
        else:
            raise ValueError("invalid model output")
        if type(payload) is not dict:
            raise ValueError("model result must be an object")
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > limit:
            raise ModelAnalysisError("paper model output exceeds byte budget")
        return response_type.model_validate_json(encoded, strict=True)
    except ModelAnalysisError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ModelAnalysisError("invalid structured paper model response") from None


async def _understand_query(
    model: PaperFieldModel, payload: dict[str, Any], *, response_type: type[_Response],
    max_input_bytes: int, max_output_bytes: int, verify: Callable[[], None],
) -> _Response:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > max_input_bytes:
        raise ModelAnalysisError("paper model input exceeds byte budget")
    verify()
    try:
        response = model(json.loads(encoded))
        if inspect.isawaitable(response):
            response = await response
    except Exception:
        verify()
        raise ModelAnalysisError("paper model understanding failed") from None
    verify()
    return _decode_model_response(response, max_output_bytes, response_type)


def _may_be_excluded(meta: PaperPlanFieldMeta, requirement: CapabilityFieldContract) -> bool:
    if meta.semantic_id != requirement.semantic_id:
        return False
    actual = dict(meta.qualifiers)
    # A different declared role proves disjointness; a missing role does not.
    return not any(key in actual and actual[key] != value
                   for key, value in requirement.qualifiers.items())


def _owner_query_field_coverage(
    understood: PaperUnderstanding,
    *,
    concepts: dict[str, NativeDeclaredConcept],
    intents: dict[str, PaperIntentDeclaration],
    source_proven: bool,
) -> PlanCoverage:
    """Owner field ledger for query receipts whose core proof has no ledger.

    Query input conditions cannot stand in for the intent/concept output
    requirements. Only an already source-proven core receipt covers them.
    """
    concept_ids = list(understood.concept_ids)
    if understood.intent_id is not None:
        concept_ids = sorted(set(concept_ids) | set(
            intents[understood.intent_id].required_concept_ids,
        ))
    fields = [
        SemanticFieldRequirement(
            semantic_id=field.semantic_id,
            qualifiers=[
                f"concept_id={concept_id}",
                *([f"source_type={concept.source_type}"] if concept.source_type else []),
                *([f"license={concept.license}"] if concept.license else []),
                *(f"{key}={value}" for key, value in sorted(field.qualifiers.items())),
            ],
        )
        for concept_id in concept_ids
        for concept in [concepts[concept_id]]
        for field in concept.required_fields
    ]
    if not source_proven:
        # A failed current proof does not disclose owner field/source/license
        # metadata. These meaning IDs were already offered in the query payload.
        fields = [SemanticFieldRequirement(semantic_id=concept_id,
            qualifiers=[f"concept_id={concept_id}"],
        ) for concept_id in concept_ids]
    unresolved = [SemanticFieldRequirement(
        semantic_id="unresolved", qualifiers=[f"query_concept={proposal}"],
    ) for proposal in understood.unresolved_concepts]
    uncovered = [*([] if source_proven else fields), *unresolved]
    return PlanCoverage(
        required=[*fields, *unresolved], covered=fields if source_proven else [],
        uncovered=uncovered, complete=bool(fields) and not uncovered,
    )


def _named_query_contributors(
    router: SchemaRouter, plan: PaperTypedToolPlan,
    needs: tuple[tuple[PaperQueryNeed, NativeDeclaredConcept], ...],
    *, principal: PrincipalContext, global_source_type: str | None, verify: Callable[[], None],
) -> set[str]:
    """Attest selected current scoped fields, never SID-only recall or raw hidden metadata."""
    def collect() -> set[str]:
        contributors = set()
        permitted = router._authorization_predicate(principal)
        if permitted is None:
            raise PolicyViolationError("paper query named source authorization missing")
        for call in plan.calls:
            verify()
            tool = router.registry.get(call.call.tool)
            endpoint = tool.endpoint(call.call.endpoint)
            if (
                (tool.fingerprint, endpoint.fingerprint)
                != (call.call.tool_fingerprint, call.call.schema_fingerprint)
                or not permitted(tool.model_copy(deep=True), endpoint.model_copy(deep=True))
            ):
                raise PolicyViolationError("paper query named source changed")
            availability = router.planner.availability_predicate
            if availability is not None and not availability(
                tool.model_copy(deep=True), endpoint.model_copy(deep=True),
            ):
                raise PolicyViolationError("paper query named source unavailable")
            visible = router._data_scope_endpoint_view(principal, tool, endpoint)
            if visible is None:
                raise PolicyViolationError("paper query named source scope hidden")
            visible = visible.model_copy(deep=True)
            selected = [field for field in visible.output_fields if field.name in call.call.fields]
            metadata = tuple(PaperPlanFieldMeta(
                name=field.name, semantic_id=field.semantic_id, source_unit=field.unit,
                unit=(field.unit_normalization.canonical_unit
                      if field.unit_normalization else field.unit),
                source_type=field.source_type or tool.source_type,
                license=field.license or tool.license,
                qualifiers=tuple(sorted(field.qualifiers.items())),
                source_path=field.projection_path, result_path=field.result_projection_path,
                json_schema=canonical_unit_value_schema(
                    field.json_schema, field.unit_normalization,
                ),
            ) for field in selected)
            if canonical_json_sha256([asdict(item) for item in metadata]) != canonical_json_sha256(
                [asdict(item) for item in call.fields_meta],
            ):
                raise PolicyViolationError("paper query named source field scope changed")
            for need, owner in needs:
                for field, meta in zip(selected, metadata, strict=True):
                    if any(source is not None and (
                        meta.source_type != source or call.source_type != source
                    ) for source in (owner.source_type, need.source_type, global_source_type)):
                        continue
                    if owner.license is not None and (
                        meta.license != owner.license or call.license != owner.license
                    ):
                        continue
                    produced = CapabilityFieldContract.from_field(field)
                    if (
                        produced is not None
                        and (need.unit is None or produced.unit == need.unit)
                        and all(produced.qualifiers.get(key) == value
                                for key, value in need.qualifiers.items())
                        and any(_compatible_field(required, field)
                                for required in owner.required_fields)
                    ):
                        contributors.add(call.call.tool)
            current = router.registry.get(call.call.tool)
            if (current.fingerprint, current.endpoint(call.call.endpoint).fingerprint) != (
                call.call.tool_fingerprint, call.call.schema_fingerprint,
            ):
                raise PolicyViolationError("paper query named source fingerprint changed")
            verify()
        return contributors

    try:
        first = collect()
        if collect() != first:
            raise PolicyViolationError("paper query named source contribution changed")
        verify()
        return first
    except Exception:
        verify()
        raise PolicyViolationError(
            "paper query named source contribution verification failed"
        ) from None


def _compile_query_needs(
    raw: PaperQueryUnderstanding, *, query: str, catalog: NativeConceptCatalog,
    intent_ids: set[str],
    compile_hint: Callable[[PaperUnderstanding, tuple[tuple[str, str | None], ...]],
                           PaperTypedToolPlan],
    abstain: Callable[[], PaperTypedToolPlan], resolve_tool: Callable[[str], str | None],
    router: SchemaRouter, principal: PrincipalContext, verify: Callable[[], None],
) -> PaperTypedToolPlan:
    if raw.intent_id is not None and raw.intent_id not in intent_ids:
        raise ModelAnalysisError("model selected an unoffered paper intent")
    resolved = [_resolve_query_need(need, catalog, raw.source_type) for need in raw.needs]
    excluded = [_resolve_query_need(PaperQueryNeed(concept=name), catalog)
                for name in raw.excluded_concepts]
    named_tools = []
    named_requirements = []
    missing_tools = []
    for name in raw.named_tools:
        # A model can copy a user-named source, never choose a provider on its own.
        key = (resolve_tool(name) if _alias_mentions(_normalized(query), _normalized(name))
               else None)
        named_requirements.append((name, key))
        (named_tools if key is not None else missing_tools).append(key or name)
    known = tuple(dict.fromkeys(cid for cid, _ in resolved if cid is not None))
    ambiguous = any(flag for _, flag in (*resolved, *excluded))
    if raw.needs_truncated or raw.intent_id is None or not known or missing_tools or ambiguous:
        plan = abstain()
    else:
        plan = compile_hint(PaperUnderstanding(
            intent_id=raw.intent_id, concept_ids=known, source_type=raw.source_type,
            named_tools=tuple(dict.fromkeys(named_tools)),
            unresolved_concepts=tuple(dict.fromkeys(
                need.concept for need, (cid, _) in zip(raw.needs, resolved, strict=True)
                if cid is None
            )),
        ), tuple((cid, need.source_type or raw.source_type)
                 for need, (cid, _) in zip(raw.needs, resolved, strict=True)
                 if cid is not None))
    covered_ids = {
        qualifier.removeprefix("concept_id=")
        for requirement in (plan.coverage.covered if plan.coverage else [])
        for qualifier in requirement.qualifiers if qualifier.startswith("concept_id=")
    }
    if plan.coverage is None and plan.calls and plan.status in (
        "ready", "requires_arguments", "requires_observation",
    ):
        covered_ids.update(known)
    by_id = {concept.concept_id: concept for concept in catalog.concepts}
    forbidden = [
        field for cid, _ in excluded if cid is not None
        for field in by_id[cid].required_fields
    ]
    conflict = any(_may_be_excluded(meta, requirement)
                   for call in plan.calls for meta in call.fields_meta for requirement in forbidden)
    if conflict:
        covered_ids.clear()

    required, covered, uncovered = [], [], []

    def add(requirement: SemanticFieldRequirement, present: bool) -> None:
        required.append(requirement)
        (covered if present else uncovered).append(requirement)

    for need, (cid, _) in zip(raw.needs, resolved, strict=True):
        qualifiers = [f"{key}={value}" for key, value in sorted(need.qualifiers.items())]
        if need.unit is not None:
            qualifiers.append(f"unit={need.unit}")
        source_type = need.source_type or raw.source_type
        if source_type is not None:
            qualifiers.append(f"source_type={source_type}")
        if raw.source_type is not None and need.source_type not in (None, raw.source_type):
            qualifiers.append(f"global_source_type={raw.source_type}")
        add(SemanticFieldRequirement(semantic_id=need.concept, qualifiers=qualifiers),
            cid is not None and cid in covered_ids and (
                source_type is None or plan.coverage is None or any(
                    f"concept_id={cid}" in item.qualifiers
                    and f"source_type={source_type}" in item.qualifiers
                    for item in plan.coverage.covered
                )
            ))
    for name, (cid, _) in zip(raw.excluded_concepts, excluded, strict=True):
        add(SemanticFieldRequirement(semantic_id=name, qualifiers=["excluded=true"]),
            cid is not None and not conflict)
    contributing_tools = _named_query_contributors(
        router, plan, tuple((need, by_id[cid]) for need, (cid, _) in zip(
            raw.needs, resolved, strict=True,
        ) if cid is not None), principal=principal,
        global_source_type=raw.source_type, verify=verify,
    ) if named_requirements and not conflict else set()
    for name, key in named_requirements:
        add(SemanticFieldRequirement(semantic_id=name, qualifiers=["named_tool=true"]),
            key is not None and key in contributing_tools)
    if not raw.needs:
        add(SemanticFieldRequirement(semantic_id="query requirements"), False)
    if raw.needs_truncated:
        add(SemanticFieldRequirement(semantic_id="unrepresented query needs",
                                    qualifiers=["understanding_budget_exceeded=true"]), False)
    if plan.coverage is not None and not plan.coverage.complete and not uncovered:
        # Do not disclose an inaccessible intent group's field count or source metadata.
        add(SemanticFieldRequirement(semantic_id="intent requirements"), False)
    if raw.intent_id is None:
        covered, uncovered = [], list(required)
    status = plan.status
    if raw.needs_truncated:
        status = "budget_unsatisfied"
    elif conflict or ambiguous:
        status = "ambiguous_paths"
    elif uncovered and status in ("ready", "requires_arguments", "requires_observation"):
        status = "no_proven_hit"
    return replace(
        plan, status=status,
        calls=() if conflict else plan.calls, bindings=() if conflict else plan.bindings,
        coverage=PlanCoverage(required=required, covered=covered, uncovered=uncovered,
                              complete=not uncovered),
        understanding_hints=raw.model_dump(mode="json"),
    )


async def compile_model_query(
    session: SchemaFieldRoutingSession,
    query: str,
    *,
    principal: PrincipalContext,
    model: PaperFieldModel,
    intent_registry: PaperIntentRegistry,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...] | None = None,
    model_visible_tool_keys: tuple[str, ...] = (),
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
    max_hops: int = 2,
    max_model_input_bytes: int = 32768,
    max_model_output_bytes: int = 4096,
    rank_policy: PaperNativeRankPolicy | None = None,
    allow_unnamed_graph_discovery: bool = False,
) -> PaperTypedToolPlan:
    """Understand before source resolution, or use the earlier scoped-ID protocol.

    By default, only fixed intent names accompany the query and response
    contract. Explicit concept IDs select the earlier disclosure protocol.
    Live source checks constrain both; model hints never become host arguments.
    """
    independent = model_visible_concept_ids is None
    if (
        type(query) is not str
        or not 2 <= len(query) <= (4096 if independent else MAX_QUERY_CHARS)
        or len(query.encode("utf-8")) > (16384 if independent else MAX_QUERY_BYTES)
        or query != query.strip()
        or any((ord(char) < 32 and not (independent and char in "\n\r\t"))
               or ord(char) == 127 for char in query)
    ):
        raise ValueError("invalid bounded paper query")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("paper query requires trusted principal")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("host-approved intent registry required")
    if not callable(model):
        raise ValueError("explicit model callback required")
    if rank_policy is not None and not isinstance(rank_policy, PaperNativeRankPolicy):
        raise ValueError("reviewed paper rank policy required")
    if (
        type(allow_unnamed_graph_discovery) is not bool
        or allow_unnamed_graph_discovery and rank_policy is None
    ):
        # This authority comes only from the host call signature. Never
        # allow an LLM to activate graph-wide target discovery.
        raise ValueError(
            "unnamed graph discovery requires host approval and owner Rank"
        )
    if type(k) is not int or k != 5 or type(max_hops) is not int or max_hops not in (1, 2):
        raise ValueError("paper query requires K5 and one or two graph hops")
    if (
        type(max_model_input_bytes) is not int
        or not 1 <= max_model_input_bytes <= 32768
        or type(max_model_output_bytes) is not int
        or not 1 <= max_model_output_bytes <= 4096
    ):
        raise ValueError("invalid paper model byte budget")

    # Review-only sessions have no approved concept authority. The public
    # session entrypoint already enforces this; the standalone compiler must
    # enforce it too before producing any model-visible disclosure.
    catalog = session._require_catalog()
    try:
        reviewed = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
        intents = PaperIntentRegistry.model_validate(
            intent_registry.model_dump(mode="python"), strict=True,
        )
        before = (catalog.model_dump_json(), intent_registry.model_dump_json(),
                  principal.model_dump_json(), deepcopy(host_source_arguments),
                  rank_policy.model_dump_json() if rank_policy else None)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise PolicyViolationError("paper query owner declarations invalid") from None

    if rank_policy is not None:
        try:
            reviewed_rank = PaperNativeRankPolicy.model_validate(
                rank_policy.model_dump(mode="python"), strict=True,
            )
            annotated = (
                set(reviewed_rank.route_domains)
                | set(reviewed_rank.route_priorities)
                | set(reviewed_rank.web_route_ids)
            )
            if (
                reviewed_rank.snapshot_id != session.snapshot_id
                or not annotated <= session._index.field_index.route_locations.keys()
            ):
                raise ValueError("stale paper Rank source declaration")
        except Exception:
            # Fail before any external model disclosure; diagnostics must
            # never serialize provider/owner policy internals into errors.
            raise PolicyViolationError("paper query rank source preflight failed") from None

    approved_concepts = {c.concept_id: c for c in reviewed.concepts}
    approved_intents = {i.intent_id: i for i in intents.intents}
    if (
        not independent and (
            type(model_visible_concept_ids) is not tuple
            or not 1 <= len(model_visible_concept_ids) <= 8
            or any(type(cid) is not str for cid in model_visible_concept_ids)
            or len(set(model_visible_concept_ids)) != len(model_visible_concept_ids)
            or not set(model_visible_concept_ids) <= approved_concepts.keys()
        )
        or type(model_visible_intent_ids) is not tuple
        or not 1 <= len(model_visible_intent_ids) <= 16
        or any(type(iid) is not str for iid in model_visible_intent_ids)
        or len(set(model_visible_intent_ids)) != len(model_visible_intent_ids)
        or not set(model_visible_intent_ids) <= approved_intents.keys()
        or any(not set(approved_intents[iid].required_concept_ids) <= (
            approved_concepts.keys() if independent else set(model_visible_concept_ids or ())
        ) for iid in model_visible_intent_ids)
        or type(model_visible_tool_keys) is not tuple
        or len(model_visible_tool_keys) > 5
        or any(not _bounded_name(name) for name in model_visible_tool_keys)
        or len(set(model_visible_tool_keys)) != len(model_visible_tool_keys)
    ):
        raise ValueError("invalid host-approved model disclosure")

    router = session._router
    witness = router._retrieval_authority_witness()
    session._index.field_index._assert_source(router)
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper query requires explicit source policy")
    policy_digest = _policy_contents_digest(policy)
    availability = router.planner.availability_predicate

    def verify() -> None:
        session._index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        try:
            current_owner = (
                catalog.model_dump_json(), intent_registry.model_dump_json(),
                principal.model_dump_json(), host_source_arguments,
                rank_policy.model_dump_json() if rank_policy else None,
            )
            owner_changed = current_owner != before
        except Exception:
            # A model callback may mutate the caller's owned nested Pydantic
            # collection to an unserializable object. Never return that
            # object's type, repr or Pydantic diagnostic to a consumer.
            raise PolicyViolationError("paper query owner authority changed") from None
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or router.planner.availability_predicate is not availability
            or owner_changed
        ):
            raise PolicyViolationError("paper query source or owner authority changed")

    def abstain() -> PaperTypedToolPlan:
        verify()
        return PaperTypedToolPlan(
            status="no_proven_hit", snapshot_id=session.snapshot_id,
            registry_version=witness[1], requested_k=k,
        )

    def finalize(
        plan: PaperTypedToolPlan, parameter_hints: dict[str, Any],
    ) -> PaperTypedToolPlan:
        plan = _apply_query_input_conditions(
            router, plan, principal=principal, parameter_hints=parameter_hints,
        )
        # The condition helper also calls host callbacks. Recheck the caller's
        # complete catalog/intent/Rank/host-input witness after both protocols.
        verify()
        return plan

    def compile_hint(
        understood: PaperUnderstanding,
        required_sources: tuple[tuple[str, str | None], ...] = (),
    ) -> PaperTypedToolPlan:
        try:
            if any(source is not None and approved_concepts[cid].source_type is None
                   for cid, source in required_sources):
                plan = compile_source_needs(understood, required_sources)
            else:
                plan = session.compile_understood(
                    understood, principal=principal, intent_registry=intent_registry,
                    host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
                    rank_policy=rank_policy,
                    allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
                )
        except (ValueError, TypeError):
            verify()
            raise ModelAnalysisError("model understanding could not be compiled") from None
        verify()
        return plan

    def compile_source_needs(
        understood: PaperUnderstanding,
        required_sources: tuple[tuple[str, str | None], ...],
    ) -> PaperTypedToolPlan:
        from .paper_understood_concept_plan import _merge_understood_plans

        if host_source_arguments is not None and (
            type(host_source_arguments) is not dict or len(host_source_arguments) > k
            or any(
                not _bounded_name(route) or type(values) is not dict or not 1 <= len(values) <= 4
                for route, values in host_source_arguments.items()
            )
        ):
            raise ValueError("invalid explicit paper host root inputs")
        # One owner concept may be demanded from several sources; keep those proofs separate.
        groups = list(dict.fromkeys(required_sources))
        assert understood.intent_id is not None
        intent = approved_intents[understood.intent_id]
        groups.extend((cid, understood.source_type) for cid in intent.required_concept_ids
                      if not any(previous == cid for previous, _ in groups))
        groups = [(cid, source) for cid, source in groups if source is not None or not any(
            other == cid and constraint is not None for other, constraint in groups
        )]

        def narrow_scope(sources: tuple[tuple[str, str | None], ...]):
            narrowed = reviewed.model_dump(mode="python")
            constraints = {cid: source for cid, source in sources if source is not None}
            for concept in narrowed["concepts"]:
                if concept["concept_id"] in constraints and concept["source_type"] is None:
                    concept["source_type"] = constraints[concept["concept_id"]]
            return session.revise_catalog(catalog=NativeConceptCatalog.model_validate(
                narrowed, strict=True,
            ))

        if len({cid for cid, _ in groups}) == len(groups):
            # Preserve the existing whole-group-first Rank and independent-concept fallback.
            scoped = narrow_scope(tuple(groups))
            return scoped.compile_understood(
                understood, principal=principal, intent_registry=intent_registry,
                host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
                rank_policy=rank_policy,
                allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
            )

        scoped_proofs = []
        for cid, source in groups:
            scoped = narrow_scope(((cid, source),))
            single_intent = PaperIntentRegistry(intents=(PaperIntentDeclaration(
                intent_id=intent.intent_id, required_concept_ids=(cid,), domains=intent.domains,
            ),))
            single = understood.model_copy(update={
                "concept_ids": (cid,), "unresolved_concepts": (),
            })
            scoped_proofs.append((scoped, single, single_intent))

        def prove_groups() -> tuple[PaperTypedToolPlan, ...]:
            plans = []
            for scoped, single, single_intent in scoped_proofs:
                verify()
                options = dict(
                    principal=principal, intent_registry=single_intent, k=k, max_hops=max_hops,
                    rank_policy=rank_policy,
                    allow_unnamed_graph_discovery=allow_unnamed_graph_discovery,
                )
                plan = scoped.compile_understood(single, **options)
                routes = {call.route_id for call in plan.calls}
                inputs = {route: values for route, values in (host_source_arguments or {}).items()
                          if route in routes}
                if inputs:
                    plan = scoped.compile_understood(
                        single, host_source_arguments=inputs, **options,
                    )
                plans.append(plan)
                verify()
            return tuple(plans)

        def coverage(covered: set[int]) -> PlanCoverage:
            required, present, missing = [], [], []
            for position, (cid, source) in enumerate(groups):
                requirement = SemanticFieldRequirement(semantic_id=cid, qualifiers=[
                    f"concept_id={cid}", *([f"source_type={source}"] if source is not None else []),
                ])
                required.append(requirement)
                (present if position in covered else missing).append(requirement)
            return PlanCoverage(required=required, covered=present, uncovered=missing,
                                complete=not missing)

        return _merge_understood_plans(
            router, principal=principal, index=session._index, k=k,
            host_source_arguments=host_source_arguments,
            prove_groups=prove_groups, verify_current=verify, coverage=coverage,
        )

    if independent:
        response_schema = PaperQueryUnderstanding.model_json_schema()
        # Require explicit model channels without changing legacy DTO decode defaults.
        response_schema["required"] = list(response_schema["properties"])
        need_schema = response_schema["$defs"]["PaperQueryNeed"]
        need_schema["required"] = list(need_schema["properties"])
        payload = {
            "task": "Understand the question before looking up any tool or schema.",
            "query": query,
            "intents": list(model_visible_intent_ids),
            "response_schema": response_schema,
            "rules": [
                "Return one JSON object with every response_schema channel, "
                "even when empty or null.",
                "Use the narrowest applicable listed intent_id and preserve additional needs; "
                "do not choose an unrelated broad intent. Use null if no listed intent applies.",
                "Extract EVERY requested positive data, action or goal, "
                "including unsupported ones; "
                "retain the requested action and object even when intent_id is null.",
                "If more than eight needs are requested, set needs_truncated=true.",
                "Use short English need names, preserving semantic roles and requested actions.",
                "Keep explicit time, role and other positive conditions in needs.qualifiers.",
                "Put explicit source/result paths in qualifiers.source_path or "
                "qualifiers.result_path respectively; "
                "preserve their spelling and never invent schema paths.",
                "Keep requested units using canonical symbols; do not invent conditions.",
                "source_type is only an explicit provenance/source-kind restriction, "
                "not subject matter; otherwise use null.",
                "Put every negated concept or goal only in excluded_concepts, "
                "not in needs or qualifiers.",
                "Copy named_tools only from source names explicitly stated in the question.",
                "Keep explicit scalar values in parameter_hints with explicit parameter labels; "
                "otherwise use short English semantic role names, not generic substitutes. "
                "Retain these values even when intent_id is null; "
                "they are not permissions or tool calls.",
                "Do not guess schema fields, registered IDs, providers or execution authority.",
            ],
        }
        raw = await _understand_query(
            model, payload, response_type=PaperQueryUnderstanding,
            max_input_bytes=max_model_input_bytes, max_output_bytes=max_model_output_bytes,
            verify=verify,
        )

        def resolve_tool(name: str) -> str | None:
            from .planner import _normalize

            permitted = router._authorization_predicate(principal)
            if permitted is None:
                raise PolicyViolationError("paper query lacks source authorization")
            matches = []
            try:
                for tool in router.registry.tools():
                    if model_visible_tool_keys and tool.key not in model_visible_tool_keys:
                        continue
                    if _normalize(name) not in {_normalize(tool.key), _normalize(tool.name)}:
                        continue
                    if any(
                        endpoint.read_only is True and endpoint.destructive is not True
                        and permitted(tool, endpoint)
                        and (availability is None or availability(tool, endpoint))
                        and router._data_scope_endpoint_view(principal, tool, endpoint) is not None
                        for endpoint in tool.endpoints
                    ):
                        matches.append(tool.key)
            except Exception:
                verify()
                raise PolicyViolationError("paper query named source eligibility failed") from None
            verify()
            return matches[0] if len(matches) == 1 else None

        plan = _compile_query_needs(
            raw, query=query, catalog=reviewed, intent_ids=set(model_visible_intent_ids),
            compile_hint=compile_hint, abstain=abstain, resolve_tool=resolve_tool,
            router=router, principal=principal, verify=verify,
        )
        return finalize(plan, raw.parameter_hints)

    # These are owner-reviewed concepts that still have a current, accessible,
    # field-complete proof. Never disclose unreachable concepts to the model.
    offered_concepts = []
    for concept_id in model_visible_concept_ids or ():
        concept = approved_concepts[concept_id]
        try:
            coverage = session.discover(concept.aliases[0], principal=principal, k=k)
        except ValueError:
            # A catalog alias is not an independent proof of current fields.
            continue
        except Exception:
            raise PolicyViolationError("paper query source eligibility check failed") from None
        verify()
        qualified = coverage.status == "complete"
        if not qualified and coverage.status == "over_k_unranked" and rank_policy:
            # A reviewed concept with >K authorized candidates is still a
            # valid disclosure if the same current native source can rank its
            # complete field contract. No route IDs are offered to the model.
            group = NativeDeclaredFieldGroup(
                aliases=(concept.aliases[0],),
                required_fields=concept.required_fields,
                source_type=concept.source_type, license=concept.license,
            )
            ranked = session._index.field_index.lookup(
                router, concept.aliases[0], principal=principal, group=group,
                k=k, _paper_rank_policy=rank_policy,
                _paper_rank_aliases=(tuple(concept.aliases),),
            )
            qualified = ranked.status in ("complete", "ranked_unverified")
            verify()
        if qualified:
            offered_concepts.append(concept)
    offered_ids = {concept.concept_id for concept in offered_concepts}
    if allow_unnamed_graph_discovery:
        # The ordinary per-concept direct posting preflight deliberately
        # excludes outputs available ONLY through typed two-hop joins. A
        # host-approved unnamed G5 path is also a source-owned field proof,
        # provided the ENTIRE reviewed intent FieldGroup can be satisfied.
        # Reuse the current public plan compiler (including owner domain,
        # source ACL, K5, typed joins and live scope reattestation); do not
        # infer concept eligibility from model text or raw graph topology.
        graph_offered: set[str] = set()
        for intent_id in model_visible_intent_ids:
            required = set(approved_intents[intent_id].required_concept_ids)
            if required <= offered_ids:
                continue
            verify()
            try:
                proof = session.compile_understood(
                    PaperUnderstanding(intent_id=intent_id, named_tools=()),
                    principal=principal, intent_registry=intent_registry,
                    host_source_arguments=host_source_arguments,
                    k=k, max_hops=max_hops, rank_policy=rank_policy,
                    allow_unnamed_graph_discovery=True,
                )
            except Exception:
                raise PolicyViolationError(
                    "paper query G5 intent preflight failed"
                ) from None
            verify()
            if (
                proof.status == "requires_observation"
                and len(proof.calls) in (2, 3)
                and len(proof.bindings) == len(proof.calls) - 1
                and not proof.executable_authority
            ):
                graph_offered.update(required)
        for concept_id in model_visible_concept_ids or ():
            if concept_id in graph_offered and concept_id not in offered_ids:
                offered_concepts.append(approved_concepts[concept_id])
                offered_ids.add(concept_id)
    offered_intents = [
        approved_intents[iid] for iid in model_visible_intent_ids
        if set(approved_intents[iid].required_concept_ids) <= offered_ids
    ]
    if not offered_intents:
        return abstain()

    # Only host-approved, currently scoped, non-destructive tool identities
    # may reach the model. Schema bodies/hidden route IDs are not disclosed.
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("paper query lacks source authorization")
    offered_tools: list[str] = []
    for tool_key in model_visible_tool_keys:
        allowed = False
        try:
            tool = router.registry.get(tool_key)
            for endpoint in tool.endpoints:
                if (
                    endpoint.read_only is True and endpoint.destructive is not True
                    and permitted(tool, endpoint)
                    and (availability is None or availability(tool, endpoint))
                    and router._data_scope_endpoint_view(principal, tool, endpoint)
                    is not None
                ):
                    allowed = True
                    break
        except Exception:
            raise ValueError("invalid host-approved model disclosure") from None
        verify()
        if not allowed:
            raise ValueError("invalid host-approved model disclosure")
        offered_tools.append(tool_key)

    payload = {
        "task": "Extract all query information needs and constraints for schema field routing",
        "query": query,
        "offered_intents": [
            {"intent_id": i.intent_id, "required_concept_ids": list(i.required_concept_ids)}
            for i in offered_intents
        ],
        "offered_concepts": [
            {"concept_id": c.concept_id, "aliases": list(c.aliases)}
            for c in offered_concepts
        ],
        "offered_tool_keys": offered_tools,
        "response_fields": [
            "intent_id", "concept_ids", "unresolved_concepts", "source_type",
            "named_tools", "parameter_hints",
        ],
        "response_schema": PaperUnderstanding.model_json_schema(),
        "rules": [
            "Use only offered IDs and offered tool keys; return one JSON object.",
            "Return intent_id=null if no offered intent fits the query.",
            "Keep unmatched needs in unresolved_concepts; never drop a required concept.",
            "Preserve temporal and source constraints; partial matches remain incomplete.",
            "Exclude concepts the user negates; do not add unrelated concepts.",
            "Use named_tools only for tool names stated by the user; otherwise return [].",
            "Set source_type only for an explicit source-type constraint; otherwise use null.",
            "Extract parameter_hints from the query; they never authorize execution.",
            "Never invent fields, values, credentials or permissions, or invoke providers.",
        ],
    }
    understood = await _understand_query(
        model, payload, response_type=PaperUnderstanding,
        max_input_bytes=max_model_input_bytes, max_output_bytes=max_model_output_bytes,
        verify=verify,
    )
    if (
        understood.intent_id is not None
        and understood.intent_id not in {i.intent_id for i in offered_intents}
        or not set(understood.concept_ids) <= offered_ids
        or not set(understood.named_tools) <= set(offered_tools)
    ):
        raise ModelAnalysisError("model selected unoffered paper identities")
    if understood.intent_id is None:
        plan = abstain()
    else:
        plan = compile_hint(understood)
    if plan.coverage is None:
        plan = replace(plan, coverage=_owner_query_field_coverage(
            understood, concepts=approved_concepts, intents=approved_intents,
            source_proven=bool(plan.calls) and plan.status in {
                "ready", "requires_arguments", "requires_observation",
            },
        ))
    plan = replace(plan, understanding_hints=understood.model_dump(mode="json"))
    return finalize(plan, understood.parameter_hints)
