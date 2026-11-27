"""Historical authorized posting-ranker experiment, source-checkout only.

Preserve the pre-retirement lookup and its before/after callback validation.
Use the canonical registered index and shared source-pass infrastructure;
never import this module from the installed package.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from schemarouter.authorization import PrincipalContext
from schemarouter.concept_retrieval import NativeConceptCatalog, resolve_native_concepts
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _root_envelope_empty,
)
from schemarouter.native_semantic_index import (
    STRICT_K,
    IndexedNativeFieldCandidate,
    IndexedNativeFieldResult,
    NativeSchemaPostingIndex,
    _NativeSourcePass,
)
from schemarouter.paper_native_rank import PaperNativeRankPolicy, rank_authorized_paper_direct

if TYPE_CHECKING:
    from schemarouter.runtime import SchemaRouter

MAX_RESEARCH_RANKABLE_POSTINGS = 32


def research_lookup_postings(
    self: NativeSchemaPostingIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    k: int = STRICT_K,
    input_free_only: bool = False,
    allowed_tool_keys: tuple[str, ...] | None = None,
    _research_ranker: Callable[
        [str, tuple[IndexedNativeFieldCandidate, ...], int], tuple[int, ...],
    ] | None = None,
    _paper_rank_policy: PaperNativeRankPolicy | None = None,
    _paper_rank_aliases: tuple[tuple[str, ...], ...] = (),
    _paper_rank_domains: tuple[str, ...] = (),
    _paper_group_members: Mapping[str, frozenset[str]] | None = None,
    _paper_target_tools: tuple[str, ...] = (),
    _paper_raw_rank_concepts: tuple[str, ...] | None = None,
) -> IndexedNativeFieldResult:
    """Conjunctive source-owned lookup with optional bounded E0 ranking.

    The default >K result abstains. An explicit research callback can
    choose *offsets* among at most 32 fully authorized, visible candidates.
    Such a choice is tagged unverified and confers no execution authority.
    An optional direct-only filter runs BEFORE candidate budgeting.
    """
    if type(input_free_only) is not bool:
        raise ValueError("indexed direct-only flag must be boolean")
    if allowed_tool_keys is not None and (
        type(allowed_tool_keys) is not tuple
        or not 1 <= len(allowed_tool_keys) <= k
        or any(
            type(key) is not str or not 1 <= len(key) <= 160
            or key != key.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in key)
            for key in allowed_tool_keys
        )
        or len(set(allowed_tool_keys)) != len(allowed_tool_keys)
    ):
        raise ValueError("invalid bounded named tool override")
    if _research_ranker is not None and not callable(_research_ranker):
        raise ValueError("indexed research ranker must be callable")
    if _paper_rank_policy is not None and not isinstance(
        _paper_rank_policy, PaperNativeRankPolicy,
    ):
        raise ValueError("original paper Rank needs a reviewed policy")
    if _paper_rank_policy is not None and _research_ranker is not None:
        raise ValueError("original paper Rank cannot share a model ranker")
    if _paper_rank_domains and _paper_rank_policy is None:
        raise ValueError("paper intent domains need a reviewed rank policy")
    if (
        type(_paper_rank_aliases) is not tuple
        or len(_paper_rank_aliases) > 8
        or any(type(group) is not tuple or not 1 <= len(group) <= 16
               or any(type(alias) is not str or not alias or len(alias) > 160
                      for alias in group) for group in _paper_rank_aliases)
        or type(_paper_rank_domains) is not tuple
        or len(_paper_rank_domains) > 8
        or any(type(domain) is not str for domain in _paper_rank_domains)
    ):
        raise ValueError("invalid bounded original paper Rank declarations")
    if type(k) is not int or k != STRICT_K:
        raise ValueError("native indexed lookup requires exact K5")
    if type(query) is not str or len(query.encode("utf-8")) > 512:
        raise ValueError("invalid bounded indexed native query")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("trusted principal required")
    if not isinstance(group, NativeDeclaredFieldGroup):
        raise ValueError("host-declared typed FieldGroup required")
    try:
        declaration = NativeDeclaredFieldGroup.model_validate(
            group.model_dump(mode="python"), strict=True,
        )
        approved_principal = PrincipalContext.model_validate(
            principal.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid current indexed declarations") from exc
    try:
        principal_claims = principal.model_dump_json()
        group_claims = group.model_dump_json()
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise PolicyViolationError("cannot attest indexed lookup declarations") from exc
    if _alias_key(query) not in {_alias_key(a) for a in declaration.aliases}:
        raise ValueError("no host-approved query-to-FieldGroup edge")
    if router.authorization_policy is None:
        raise PolicyViolationError("explicit authorization policy required")
    self._assert_source(router)
    original_paper_policy: str | None = None
    rank_policy = _paper_rank_policy
    if rank_policy is not None:
        original_paper_policy = rank_policy.model_dump_json()
        rank_policy = PaperNativeRankPolicy.model_validate(
            rank_policy.model_dump(mode="python"), strict=True,
        )
        if rank_policy.snapshot_id != self.snapshot_id:
            raise PolicyViolationError("paper Rank source snapshot mismatch")
        annotated = (
            set(rank_policy.route_domains) | set(rank_policy.route_priorities)
            | set(rank_policy.web_route_ids)
        )
        if not annotated <= self.route_locations.keys():
            raise PolicyViolationError("paper Rank contains unregistered routes")
    # Private, detached inputs from the owner-pinned intent registry.
    # None means no group constraint; an empty mapping means no eligible
    # unnamed group. Explicit user-named tools bypass discovery only.
    group_members = (
        dict(_paper_group_members)
        if _paper_group_members is not None and allowed_tool_keys is None else None
    )
    target_tools = frozenset(_paper_target_tools) if allowed_tool_keys is None else frozenset()
    if group_members is not None and (
        not group_members.keys() <= self.route_locations.keys()
        or any(type(names) is not frozenset or not names for names in group_members.values())
    ):
        raise PolicyViolationError("invalid paper candidate group declaration")
    witness = router._retrieval_authority_witness()
    original_policy = (
        router.authorization_policy.default_effect,
        repr(router.authorization_policy.rules),
        repr(router.authorization_policy.data_rules),
    )
    # The inverted index is ONLY a conservative candidate prefilter.
    # It never bypasses live access checks or the canonical typed compare.
    ids = [set(self.postings.get(field.semantic_id, ()))
           for field in declaration.required_fields]
    matched = set.intersection(*ids) if ids else set()
    source = _NativeSourcePass(self, router)
    permitted = router._authorization_predicate(approved_principal)
    if permitted is None:
        raise PolicyViolationError("explicit authorization required")
    availability = router._source_availability_predicate()
    qualified: list[IndexedNativeFieldCandidate] = []
    visible_field_counts: dict[str, int] = {}
    use_paper_domains = rank_policy is not None and allowed_tool_keys is None
    # An intent-defined target list is not a user named-tool override:
    # domain/group constraints still apply, but retain all eligible targets
    # rather than allowing the focus ranker to collapse a comparison.
    use_paper_rank = use_paper_domains and not target_tools
    use_paper_v1 = (
        use_paper_rank and rank_policy is not None
        and rank_policy.direct_score_mode == "paper_v1"
    )
    # Only the opt-in historical comparator needs the complete visible
    # field names. Keep those internal; never disclose hidden schema names.
    visible_rank_fields: dict[str, tuple[str, ...]] = {}
    for route in sorted(matched):
        # Key is an opaque exact registered route; never parse a route ID
        # with split because tool namespaces may contain separators.
        revisions = self.route_fingerprints.get(route)
        if revisions is None:
            raise PolicyViolationError("indexed route missing original fingerprint")
        location = self.route_locations.get(route)
        if location is None:
            raise PolicyViolationError("indexed registered route missing")
        tool_key, endpoint_name = location
        if allowed_tool_keys is not None and tool_key not in allowed_tool_keys:
            continue
        if target_tools and tool_key not in target_tools:
            continue
        if group_members is not None and route not in group_members:
            continue
        if (use_paper_domains and rank_policy is not None
                and not rank_policy.permits_domain(route, _paper_rank_domains)):
            continue
        tool, endpoint, fingerprint = source.get(tool_key, endpoint_name)
        if (fingerprint, endpoint.fingerprint) != revisions:
            raise PolicyViolationError("indexed source fingerprint drift")
        if (tool.source_type is None or tool.license is None
                or declaration.source_type is not None
                and tool.source_type != declaration.source_type
                or declaration.license is not None
                and tool.license != declaration.license):
            continue
        if endpoint.read_only is not True or endpoint.destructive is True:
            continue
        if input_free_only and not _root_envelope_empty(endpoint):
            continue
        if not permitted(tool, endpoint):
            continue
        # Host health callbacks are not a trusted error surface. A provider
        # exception (including __bool__) must never escape with private
        # endpoint details before the later final eligibility pass.
        if availability is not None:
            try:
                available_now = bool(source.available(tool, endpoint, availability))
            except Exception:
                raise PolicyViolationError(
                    "indexed availability check failed during lookup"
                ) from None
            if not available_now:
                continue
        visible = router._data_scope_endpoint_view(
            approved_principal, tool, endpoint,
        )
        if (visible is None or not _complete_fields(
                visible.output_fields, declaration.required_fields)):
            continue
        if group_members is not None:
            members = group_members[route]
            if not members <= {field.name for field in endpoint.output_fields}:
                raise PolicyViolationError("paper candidate group source fields changed")
            if not members.intersection(field.name for field in visible.output_fields):
                continue
        matched_names: list[str] = []
        for required in declaration.required_fields:
            matched_names.extend(
                field.name for field in visible.output_fields
                if field.semantic_id == required.semantic_id
                and _complete_fields([field], (required,))
            )
        qualified.append(IndexedNativeFieldCandidate(
            route_id=route,
            tool_fingerprint=source.fingerprint(tool),
            endpoint_fingerprint=endpoint.fingerprint,
            required_output_fields=tuple(sorted(set(matched_names))),
        ))
        if use_paper_rank:
            visible_field_counts[route] = len(visible.output_fields)
        if use_paper_v1:
            visible_rank_fields[route] = tuple(sorted(
                field.name for field in visible.output_fields
            ))
    count = len(qualified)
    ranked_offsets: tuple[int, ...] | None = None
    if use_paper_rank and rank_policy is not None:
        ranked_offsets = rank_authorized_paper_direct(
            tuple(qualified), concept_aliases=_paper_rank_aliases,
            visible_field_count=visible_field_counts,
            policy=rank_policy, k=k,
            raw_concepts=_paper_raw_rank_concepts,
            visible_field_names=visible_rank_fields if use_paper_v1 else None,
        )
    elif (
        count > k and _research_ranker is not None
        and count <= MAX_RESEARCH_RANKABLE_POSTINGS
    ):
        # Pass detached read-only-shaped records to an UNTRUSTED ranker.
        # Never trust returned candidate objects, route names or arbitrary
        # ranking values: only unique indices into our verified snapshot.
        offered = tuple(replace(candidate) for candidate in qualified)
        try:
            proposed = _research_ranker(query, offered, k)
        except Exception:
            raise PolicyViolationError("indexed research ranking failed") from None
        if (
            type(proposed) is not tuple
            or len(proposed) not in (0, k)
            or any(
                type(offset) is not int or not 0 <= offset < count
                for offset in proposed
            )
            or len(set(proposed)) != len(proposed)
        ):
            raise PolicyViolationError(
                "indexed ranker returned forged, partial or duplicate offsets"
            )
        ranked_offsets = proposed
    # A live availability callable may keep its identity while a
    # later candidate's health probe revokes an earlier candidate.
    # Recheck every already-qualified route, even when >K ultimately
    # abstains: qualified_count is still disclosed to the caller.
    source.reset()
    try:
        for candidate in qualified:
            where = self.route_locations[candidate.route_id]
            pinned = self.route_fingerprints[candidate.route_id]
            tool, endpoint, fingerprint = source.get(*where)
            if (fingerprint, endpoint.fingerprint) != pinned:
                raise PolicyViolationError("indexed candidate source changed")
            if (
                tool.source_type is None or tool.license is None
                or declaration.source_type is not None
                and tool.source_type != declaration.source_type
                or declaration.license is not None
                and tool.license != declaration.license
                or endpoint.read_only is not True
                or endpoint.destructive is True
                or input_free_only and not _root_envelope_empty(endpoint)
                or not permitted(tool, endpoint)
                or availability is not None
                and not source.available(tool, endpoint, availability)
            ):
                raise PolicyViolationError("indexed candidate no longer available")
            scoped = router._data_scope_endpoint_view(
                approved_principal, tool, endpoint,
            )
            if (
                scoped is None or not _complete_fields(
                    scoped.output_fields, declaration.required_fields,
                )
            ):
                raise PolicyViolationError("indexed candidate scope changed")
            if group_members is not None and not group_members[candidate.route_id].intersection(
                field.name for field in scoped.output_fields
            ):
                raise PolicyViolationError("paper candidate group scope changed")
            current_names = tuple(sorted({
                field.name for required in declaration.required_fields
                for field in scoped.output_fields
                if field.semantic_id == required.semantic_id
                and _complete_fields([field], (required,))
            }))
            if current_names != candidate.required_output_fields:
                raise PolicyViolationError("indexed candidate projection changed")
            if (use_paper_rank and
                    len(scoped.output_fields) != visible_field_counts[candidate.route_id]):
                raise PolicyViolationError("paper Rank visible field count changed")
            if use_paper_v1 and tuple(sorted(
                field.name for field in scoped.output_fields
            )) != visible_rank_fields[candidate.route_id]:
                raise PolicyViolationError("paper v1 Rank visible field names changed")
    except Exception:
        # Avoid leaking provider/private schema details in callback errors.
        raise PolicyViolationError(
            "indexed candidate eligibility changed during lookup"
        ) from None
    self._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    if original_paper_policy is not None:
        try:
            if _paper_rank_policy is None or (
                _paper_rank_policy.model_dump_json() != original_paper_policy
            ):
                raise PolicyViolationError("paper Rank owner declaration changed")
        except Exception:
            raise PolicyViolationError(
                "paper Rank owner declaration changed"
            ) from None
    current_policy = router.authorization_policy
    if (
        current_policy.default_effect,
        repr(current_policy.rules),
        repr(current_policy.data_rules),
    ) != original_policy:
        raise PolicyViolationError("authorization policy changed during indexed lookup")
    try:
        if (
            principal.model_dump_json() != principal_claims
            or group.model_dump_json() != group_claims
        ):
            raise PolicyViolationError("indexed lookup declarations changed")
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise PolicyViolationError(
            "cannot attest current indexed lookup declarations"
        ) from exc
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified", "ranker_abstained_unverified",
    ]
    if count > k:
        status = (
            "over_k_unranked" if ranked_offsets is None else
            "ranked_unverified" if ranked_offsets else
            "ranker_abstained_unverified"
        )
    else:
        status = "complete" if count else "no_proven_hit"
    return IndexedNativeFieldResult(
        status=status,
        registry_version=self.registry_version,
        index_snapshot_id=self.snapshot_id,
        requested_k=k,
        qualified_count=count,
        candidates=(
            tuple(qualified[offset] for offset in ranked_offsets)
            if ranked_offsets is not None else
            tuple(qualified) if count <= k else ()
        ),
        experimental_ranked=ranked_offsets is not None,
        deterministic_paper_ranked=use_paper_rank,
    )

def research_lookup_posting_concepts(
    self: NativeSchemaPostingIndex,
    router: SchemaRouter,
    query: str,
    *,
    catalog: NativeConceptCatalog,
    principal: PrincipalContext,
    k: int = STRICT_K,
    input_free_only: bool = False,
    _research_ranker: Callable[
        [str, tuple[IndexedNativeFieldCandidate, ...], int], tuple[int, ...],
    ] | None = None,
) -> IndexedNativeFieldResult:
    """Original query → declared concepts → typed field intersection."""
    resolved = resolve_native_concepts(query, catalog=catalog)
    return research_lookup_postings(
        self, router, query, group=resolved.field_group, principal=principal,
        k=k, input_free_only=input_free_only, _research_ranker=_research_ranker,
    )
