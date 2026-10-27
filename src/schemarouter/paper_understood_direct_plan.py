"""Research-only Algorithm 1 understanding → original direct ToolCall receipts.

`PaperUnderstanding` is an untrusted routing suggestion. The owner-reviewed
intent/concept contracts and current source authorization are the authority.
Model parameter hints never become executable or host-approved arguments.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from .authorization import PrincipalContext
from .concept_retrieval import _ID_PATTERN, NativeConceptCatalog
from .errors import PolicyViolationError
from .field_group_retrieval import NativeDeclaredFieldGroup
from .host_field_contract import _policy_contents_digest
from .models import StrictModel
from .native_graph_index import NativeSchemaGraphIndex
from .paper_field_retrieval import PaperFieldRoute
from .paper_native_rank import PaperNativeRankPolicy
from .paper_typed_tool_plan import (
    PaperTypedToolPlan,
    _check_current_call_scopes,
    _compile_one_route,
)

if TYPE_CHECKING:
    from .runtime import SchemaRouter


def _bounded_name(name: str) -> bool:
    return (
        type(name) is str and 1 <= len(name) <= 160
        and name == name.strip()
        and not any(ord(char) < 32 or ord(char) == 127 for char in name)
    )


class PaperIntentDeclaration(StrictModel):
    """Owner-approved intent → required concept IDs, not a second tool registry."""

    intent_id: str
    required_concept_ids: tuple[str, ...]
    domains: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_declaration(self) -> PaperIntentDeclaration:
        if (
            type(self.intent_id) is not str
            or not _ID_PATTERN.fullmatch(self.intent_id)
            or not 1 <= len(self.required_concept_ids) <= 8
            or any(
                type(cid) is not str or not _ID_PATTERN.fullmatch(cid)
                for cid in self.required_concept_ids
            )
            or len(set(self.required_concept_ids)) != len(self.required_concept_ids)
            or len(self.domains) > 8
            or len(set(self.domains)) != len(self.domains)
            or any(type(domain) is not str or not _ID_PATTERN.fullmatch(domain)
                   for domain in self.domains)
        ):
            raise ValueError("invalid owner-reviewed paper intent declaration")
        return self


class PaperIntentRegistry(StrictModel):
    intents: tuple[PaperIntentDeclaration, ...]

    @model_validator(mode="after")
    def validate_registry(self) -> PaperIntentRegistry:
        if (
            not 1 <= len(self.intents) <= 16
            or len({intent.intent_id for intent in self.intents}) != len(self.intents)
            or len(self.model_dump_json().encode("utf-8")) > 8192
        ):
            raise ValueError("invalid bounded paper intent registry")
        return self


class PaperUnderstanding(StrictModel):
    """Untrusted externally understood routing hints; never execution claims."""

    intent_id: str
    concept_ids: tuple[str, ...] = ()
    source_type: str | None = None
    named_tools: tuple[str, ...] = ()
    parameter_hints: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_understanding(self) -> PaperUnderstanding:
        if (
            type(self.intent_id) is not str
            or not _ID_PATTERN.fullmatch(self.intent_id)
            or len(self.concept_ids) > 8
            or any(
                type(cid) is not str or not _ID_PATTERN.fullmatch(cid)
                for cid in self.concept_ids
            )
            or len(set(self.concept_ids)) != len(self.concept_ids)
            or self.source_type is not None
            and not _bounded_name(self.source_type)
            or len(self.named_tools) > 5
            or any(not _bounded_name(tool) for tool in self.named_tools)
            or len(set(self.named_tools)) != len(self.named_tools)
            or len(self.parameter_hints) > 8
            or any(
                not _bounded_name(key)
                or type(value) not in (str, int, float, bool)
                or type(value) is str and len(value.encode("utf-8")) > 512
                or type(value) is float and not math.isfinite(value)
                or type(value) is int and not -(2**63) <= value < 2**63
                for key, value in self.parameter_hints.items()
            )
            or len(self.model_dump_json().encode("utf-8")) > 4096
        ):
            raise ValueError("invalid bounded paper understanding hints")
        return self


def _source_owned_understood_group(
    understanding: PaperUnderstanding,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
) -> tuple[PaperUnderstanding, NativeDeclaredFieldGroup]:
    """Build a bounded original-paper required field AND from owner declarations.

    Shared by direct and explicitly named typed-graph planning; model strings
    never become aliases, field contracts or executable input values.
    """
    try:
        approved_hints = PaperUnderstanding.model_validate(
            understanding.model_dump(mode="python"), strict=True,
        )
        approved_intents = PaperIntentRegistry.model_validate(
            intent_registry.model_dump(mode="python"), strict=True,
        )
        approved_catalog = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ValueError("paper understood declarations changed or invalid") from exc

    intent = next((i for i in approved_intents.intents
                   if i.intent_id == approved_hints.intent_id), None)
    if intent is None:
        raise ValueError("unregistered original paper intent")
    concept_by_id = {c.concept_id: c for c in approved_catalog.concepts}
    concept_ids = set(intent.required_concept_ids) | set(approved_hints.concept_ids)
    if not concept_ids <= concept_by_id.keys():
        raise ValueError("unregistered original paper concept")
    concepts = [concept_by_id[cid] for cid in sorted(concept_ids)]
    sources = {(concept.source_type, concept.license) for concept in concepts}
    if len(sources) != 1:
        raise ValueError("incompatible source-owned intent concept contracts")
    source_type, license_id = next(iter(sources))

    demanded = {}
    for concept in concepts:
        for field in concept.required_fields:
            previous = demanded.get(field.semantic_id)
            if previous is not None and previous != field:
                raise ValueError("conflicting original paper typed field contracts")
            demanded[field.semantic_id] = field
    if not 1 <= len(demanded) <= 8:
        raise ValueError("original paper intent field group exceeds bound")
    canonical_query = " ".join(concept.aliases[0] for concept in concepts)
    if (
        len(canonical_query) > 256
        or len(canonical_query.encode("utf-8")) > 512
    ):
        raise ValueError("source-owned paper canonical lookup key exceeds bound")
    return approved_hints, NativeDeclaredFieldGroup(
        aliases=(canonical_query,),
        required_fields=tuple(demanded[key] for key in sorted(demanded)),
        source_type=source_type, license=license_id,
    )


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
            or host_source_arguments is not None
            and host_source_arguments != host_inputs
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
    first = index.field_index.lookup(
        router, group.aliases[0], principal=principal, group=group,
        k=k, allowed_tool_keys=keys,
        _paper_rank_policy=rank_policy, _paper_rank_aliases=rank_aliases,
        _paper_rank_domains=intent.domains,
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
            names = tuple(field.name for field in visible.output_fields if (
                field.name in required_names or field.identifier
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
            ) for i, route in enumerate(routes)
        ]
        if edges:
            raise PolicyViolationError("paper direct plan unexpectedly added a join")
        _check_current_call_scopes(router, principal, calls)
        return tuple(calls)

    try:
        initial_calls = materialize(first.candidates)
        second = index.field_index.lookup(
            router, group.aliases[0], principal=principal, group=group,
            k=k, allowed_tool_keys=keys,
            _paper_rank_policy=rank_policy, _paper_rank_aliases=rank_aliases,
            _paper_rank_domains=intent.domains,
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
