"""Checkout-only historical direct compilation with typed/unfocused Rank.

Retain the original source witnesses, field projection, and typed contracts.
"""
from __future__ import annotations

from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

from schemarouter._authorization_witness import _policy_contents_digest
from schemarouter.authorization import PrincipalContext
from schemarouter.canonical_json import canonical_json_text
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_typed_tool_plan import (
    PaperFieldRoute,
    PaperTypedToolPlan,
    _check_current_call_scopes,
    _compile_one_route,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    _bounded_name,
    _source_owned_understood_concepts,
    _source_owned_understood_group,
)
from scripts.research_legacy_direct_rank import PaperNativeRankPolicy, lookup_research_postings

if TYPE_CHECKING:
    from schemarouter.field_routing_session import SchemaFieldRoutingSession
    from schemarouter.runtime import SchemaRouter


def compile_paper_understood_direct_plan(
    router: SchemaRouter,
    understanding: PaperUnderstanding,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    k: int = 5,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    rank_policy: PaperNativeRankPolicy | None = None,
) -> PaperTypedToolPlan:
    """Plan original direct fields from reviewed concepts, without execution authority."""
    return _compile_paper_understood_direct_plan(
        router, understanding, principal=principal, catalog=catalog,
        intent_registry=intent_registry, index=index, k=k,
        host_source_arguments=host_source_arguments, rank_policy=rank_policy,
    )


def _compile_paper_understood_direct_plan(
    router: SchemaRouter,
    understanding: PaperUnderstanding,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    k: int = 5,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    rank_policy: PaperNativeRankPolicy | None = None,
    _compose_concepts: bool = True,
) -> PaperTypedToolPlan:
    """Plan field-complete original *direct* tools from structured hints.

    The structured understanding need not lexically mention an owner alias:
    the host-approved intent/concept declarations supply the field semantics.
    No semantic-fit, provider-result or execution quality is certified.
    """
    if type(k) is not int or k != 5:
        raise ValueError("paper understood plan requires exact K5")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("paper understood plan requires original graph index")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("paper understood plan requires trusted principal")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("owner-reviewed concept catalog required")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("host-approved intent registry required")
    if not isinstance(understanding, PaperUnderstanding):
        raise ValueError("structured paper understanding required")
    if rank_policy is not None and not isinstance(rank_policy, PaperNativeRankPolicy):
        raise ValueError("reviewed paper rank policy required")
    if host_source_arguments is not None and (
        type(host_source_arguments) is not dict
        or len(host_source_arguments) > k
        or any(
            type(route) is not str or not _bounded_name(route)
            or type(values) is not dict or not 1 <= len(values) <= 4
            for route, values in host_source_arguments.items()
        )
    ):
        raise ValueError("invalid explicit paper host direct arguments")
    # Values are supplied by the trusted host, never from model hints. Their
    # types, source-root eligibility and current principal-scoped schema are
    # checked by the original typed compiler for every materialization.
    host_inputs = deepcopy(host_source_arguments or {})
    try:
        original_hints = understanding.model_dump_json()
        original_intents = intent_registry.model_dump_json()
        original_catalog = catalog.model_dump_json()
        original_principal = principal.model_dump_json()
        original_rank_policy = rank_policy.model_dump_json() if rank_policy else None
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ValueError("paper understood declarations changed or invalid") from exc

    approved_hints, approved_intent, concepts = _source_owned_understood_concepts(
        understanding, catalog, intent_registry,
    )
    projection_groups = deepcopy(intent_registry.route_field_groups)
    annotated = intent_registry.annotated_routes()
    approved_direct_parameter_routes = frozenset(
        intent_registry.approved_direct_parameter_routes,
    )
    if intent_registry.projection_snapshot_id is not None and (
        intent_registry.projection_snapshot_id != index.field_index.snapshot_id
        or not annotated <= index.field_index.route_locations.keys()
    ):
        raise PolicyViolationError("paper intent source snapshot mismatch")
    if _compose_concepts and (len(concepts) > 1 or approved_hints.unresolved_concepts):
        from schemarouter.paper_understood_concept_plan import _compile_understood_concept_plan

        return _compile_understood_concept_plan(
            router, understanding, principal=principal, catalog=catalog,
            intent_registry=intent_registry, index=index, k=k,
            host_source_arguments=host_source_arguments, rank_policy=rank_policy,
            approved=approved_hints, intent=approved_intent, concepts=concepts,
            compile_one=compile_paper_understood_direct_plan,
            compile_group=partial(_compile_paper_understood_direct_plan, _compose_concepts=False),
        )
    approved_hints, group = _source_owned_understood_group(
        understanding, catalog, intent_registry,
    )
    intent = next(i for i in intent_registry.intents
                  if i.intent_id == approved_hints.intent_id)
    concept_ids = set(intent.required_concept_ids) | set(approved_hints.concept_ids)
    approved_concepts = {c.concept_id: c for c in catalog.concepts}
    rank_aliases = tuple(tuple(approved_concepts[cid].aliases)
                         for cid in sorted(concept_ids))

    witness = router._retrieval_authority_witness()
    index.field_index._assert_source(router)
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper understood plan requires source policy")
    original_policy = _policy_contents_digest(policy)

    def verify_owner_and_source() -> None:
        index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        try:
            current_rank_policy = rank_policy.model_dump_json() if rank_policy else None
        except Exception:
            raise PolicyViolationError("paper understood owner or authority changed") from None
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != original_policy
            or principal.model_dump_json() != original_principal
            or catalog.model_dump_json() != original_catalog
            or intent_registry.model_dump_json() != original_intents
            or understanding.model_dump_json() != original_hints
            or current_rank_policy != original_rank_policy
            or host_source_arguments is not None and (
                host_source_arguments != host_inputs
                or canonical_json_text(host_source_arguments) != canonical_json_text(host_inputs)
            )
        ):
            raise PolicyViolationError("paper understood owner or authority changed")

    def empty(
        status: Literal["no_proven_hit", "over_k_unranked", "budget_unsatisfied"],
    ) -> PaperTypedToolPlan:
        verify_owner_and_source()
        return PaperTypedToolPlan(
            status=status, snapshot_id=index.field_index.snapshot_id,
            registry_version=witness[1], requested_k=k,
        )

    # Source constraints can only remove candidates. Their absence does not
    # loosen catalog source/licence requirements already embedded in `group`.
    if approved_hints.source_type is not None and (
        approved_hints.source_type != group.source_type
    ):
        return empty("no_proven_hit")

    keys = approved_hints.named_tools or None
    # The original unnamed Filter uses any overlap with required group IDs,
    # not an intersection of all groups' fields. The typed mandatory proof
    # remains a separate gate. An empty overlap must not become unrestricted.
    candidate_groups = None
    if intent.recall_group_ids and keys is None:
        candidate_groups = {
            route: frozenset(
                name for group_id, members in groups.items()
                if group_id in intent.recall_group_ids for name in members
            )
            for route, groups in projection_groups.items()
            if any(group_id in groups for group_id in intent.recall_group_ids)
        }
    first = lookup_research_postings(
        index.field_index, router, group.aliases[0], principal=principal, group=group,
        k=k, allowed_tool_keys=keys,
        _paper_rank_policy=rank_policy, _paper_rank_aliases=rank_aliases,
        _paper_rank_domains=intent.domains,
        _paper_group_members=candidate_groups,
        _paper_target_tools=intent.target_tool_keys,
        _paper_raw_rank_concepts=approved_hints.raw_rank_concepts,
    )
    ranked = first.status == "ranked_unverified" and first.deterministic_paper_ranked
    if first.status != "complete" and not ranked:
        if host_inputs:
            raise ValueError("host direct arguments require a proved source route")
        if first.status not in ("no_proven_hit", "over_k_unranked"):
            raise PolicyViolationError("unverified paper selection status")
        return empty(first.status)
    if not host_inputs.keys() <= {candidate.route_id for candidate in first.candidates}:
        raise ValueError("host direct arguments name an unproved source route")

    def materialize(candidates):
        permitted = router._authorization_predicate(principal)
        if permitted is None:
            raise PolicyViolationError("paper understood plan lacks source policy")
        routes: list[PaperFieldRoute] = []
        for candidate in candidates:
            location = index.field_index.route_locations.get(candidate.route_id)
            if location is None:
                raise PolicyViolationError("paper understood source route vanished")
            tool = router.registry.get(location[0])
            endpoint = tool.endpoint(location[1])
            visible = router._data_scope_endpoint_view(principal, tool, endpoint)
            if visible is None:
                raise PolicyViolationError("paper understood route no longer visible")
            required_names = set(candidate.required_output_fields)
            # Algorithm 1 recall safety net: a matched concept activates its
            # source-local groups; the intent may activate other local groups.
            # Only visible registered fields are returned. A hidden adjunct
            # cannot grant coverage or disclose its name. Do not recursively
            # expand groups via adjunct fields, or share groups across routes.
            selected_names = set(required_names)
            original_names = {field.name for field in endpoint.output_fields}
            for group_id, members in projection_groups.get(candidate.route_id, {}).items():
                if not set(members) <= original_names:
                    raise PolicyViolationError("paper recall group source fields changed")
                if group_id in intent.recall_group_ids or required_names.intersection(members):
                    selected_names.update(members)
            names = tuple(field.name for field in visible.output_fields if (
                field.name in selected_names or field.identifier
            ))
            if not required_names.issubset(names):
                raise PolicyViolationError("paper understood required fields hidden")
            routes.append(PaperFieldRoute(
                route_id=candidate.route_id,
                tool_fingerprint=candidate.tool_fingerprint,
                endpoint_fingerprint=candidate.endpoint_fingerprint,
                output_fields=names,
                covered_semantic_ids=tuple(sorted(
                    field.semantic_id for field in group.required_fields
                )),
            ))
        positions = {route.route_id: i for i, route in enumerate(routes)}
        originals = {route.route_id: route for route in routes}
        edges = []
        calls = [
            _compile_one_route(
                router, principal, index, route, i, positions, originals,
                edges, permitted, host_inputs.get(route.route_id),
                allow_direct_host_inputs=route.route_id in approved_direct_parameter_routes,
            ) for i, route in enumerate(routes)
        ]
        if edges:
            raise PolicyViolationError("paper direct plan unexpectedly added a join")
        _check_current_call_scopes(router, principal, calls)
        return tuple(calls)

    try:
        initial_calls = materialize(first.candidates)
        second = lookup_research_postings(
            index.field_index, router, group.aliases[0], principal=principal, group=group,
            k=k, allowed_tool_keys=keys,
            _paper_rank_policy=rank_policy, _paper_rank_aliases=rank_aliases,
            _paper_rank_domains=intent.domains,
            _paper_group_members=candidate_groups,
            _paper_target_tools=intent.target_tool_keys,
            _paper_raw_rank_concepts=approved_hints.raw_rank_concepts,
        )
        if first != second or materialize(second.candidates) != initial_calls:
            raise PolicyViolationError("paper understood source proof changed")
    except Exception:
        # Source callbacks may include private names in their diagnostics.
        raise PolicyViolationError("paper understood source eligibility changed") from None
    verify_owner_and_source()
    return PaperTypedToolPlan(
        status=("requires_arguments" if any(
            call.call.missing_required_arguments for call in initial_calls
        ) else "ready"),
        snapshot_id=first.index_snapshot_id,
        registry_version=first.registry_version,
        requested_k=k,
        calls=initial_calls,
        ranked_unverified=first.deterministic_paper_ranked,
    )


def compile_research_direct(
    session: SchemaFieldRoutingSession,
    understanding: PaperUnderstanding,
    *,
    principal: PrincipalContext,
    intent_registry: PaperIntentRegistry,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
    rank_policy: PaperNativeRankPolicy | None = None,
) -> PaperTypedToolPlan:
    """Historical prepared direct compiler; not installed or used by product."""
    return compile_paper_understood_direct_plan(
        session._router, understanding, principal=principal,
        catalog=session._require_catalog(), intent_registry=intent_registry,
        index=session._index, k=k, host_source_arguments=host_source_arguments,
        rank_policy=rank_policy,
    )
