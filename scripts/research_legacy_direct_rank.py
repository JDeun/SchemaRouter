"""Checkout-only historical typed and unfocused direct Rank comparator.

This is strictly a sort of already authorized, typed source receipts. No
provider-authored free-text metadata, execution data or model callback is
read by the comparator.
"""
from __future__ import annotations

import heapq
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

from schemarouter.authorization import PrincipalContext
from schemarouter.errors import PolicyViolationError
from schemarouter.field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _alias_key,
    _complete_fields,
    _root_envelope_empty,
)
from schemarouter.models import StrictModel
from schemarouter.native_semantic_index import (
    STRICT_K,
    IndexedNativeFieldCandidate,
    NativeSchemaPostingIndex,
    _NativeSourcePass,
)

if TYPE_CHECKING:
    from schemarouter.runtime import SchemaRouter


_DOMAIN_ID = re.compile(r"[a-zA-Z][a-zA-Z0-9._:-]{0,79}\Z")
_MAX_POLICY_BYTES = 1_500_000
_MAX_POLICY_ROUTES = 5_000


class PaperNativeRankPolicy(StrictModel):
    """Trusted host-reviewed route annotations pinned to a native snapshot.

    These annotations affect discovery priority only. They do not grant
    permission, assert vendor origin, bind arguments or enable execution.
    """

    snapshot_id: str
    # Opt-in comparator parity with the paper's frozen experimental router.
    # The existing focus_direct option controls cardinality independently.
    direct_score_mode: Literal["typed", "paper_v1"] = "typed"
    route_domains: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    route_priorities: dict[str, StrictInt] = Field(default_factory=dict)
    web_route_ids: tuple[str, ...] = ()
    # The original experimental router focuses on one unnamed source. Keep
    # the existing Top-K5 mode as the default for compatibility. This option
    # affects direct discovery only, never named overrides or dependency paths.
    focus_direct: StrictBool = False

    @model_validator(mode="after")
    def validate_owner_policy(self) -> PaperNativeRankPolicy:
        if (
            type(self.snapshot_id) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id)
            or len(self.route_domains) > _MAX_POLICY_ROUTES
            or len(self.route_priorities) > _MAX_POLICY_ROUTES
            or len(self.web_route_ids) > _MAX_POLICY_ROUTES
            or len(set(self.web_route_ids)) != len(self.web_route_ids)
        ):
            raise ValueError("invalid native rank source or cardinality")
        annotated = (
            set(self.route_domains) | set(self.route_priorities)
            | set(self.web_route_ids)
        )
        if any(type(route) is not str or not route or len(route) > 512
               for route in annotated):
            raise ValueError("invalid native rank route annotation")
        if any(
            type(value) is not int or not -100 <= value <= 100
            for value in self.route_priorities.values()
        ):
            raise ValueError("invalid native rank route priority")
        if any(
            type(domains) is not tuple or not 1 <= len(domains) <= 8
            or len(set(domains)) != len(domains)
            or any(type(domain) is not str or not _DOMAIN_ID.fullmatch(domain)
                   for domain in domains)
            for domains in self.route_domains.values()
        ):
            raise ValueError("invalid native rank domains")
        if len(self.model_dump_json().encode("utf-8")) > _MAX_POLICY_BYTES:
            raise ValueError("native rank policy exceeds byte budget")
        return self

    def permits_domain(self, route_id: str, intent_domains: tuple[str, ...]) -> bool:
        """An intent domain filters BEFORE K; absent intent domains do not."""
        return not intent_domains or bool(
            set(self.route_domains.get(route_id, ())) & set(intent_domains)
        )


def _concept_match_strength(
    visible_names: tuple[str, ...], concept_aliases: tuple[tuple[str, ...], ...],
) -> tuple[int, int]:
    names = tuple(_alias_key(name) for name in visible_names)
    exact = 0
    partial = 0
    for aliases in concept_aliases:
        best = 0
        for alias in aliases:
            normalized = _alias_key(alias)
            if not normalized:
                continue
            for name in names:
                if name == normalized:
                    best = 2
                    break
                if name in normalized or normalized in name:
                    best = max(best, 1)
            if best == 2:
                break
        exact += best == 2
        partial += best == 1
    # Strengthened typed comparator: exact matches dominate any partial count.
    # The historical paper comparator instead adds 2*exact + partial.
    return exact, partial


def _paper_v1_concept_score(
    visible_names: tuple[str, ...], raw_concepts: tuple[str, ...],
) -> int:
    """Frozen paper harness score: raw field names, no alias normalization."""
    names = {name.lower() for name in visible_names}
    score = 0
    for concept in raw_concepts:
        label = concept.strip().lower()
        if label in names:
            score += 2
        elif any(label in name or name in label for name in names):
            score += 1
    return score


def rank_authorized_paper_direct(
    candidates: tuple[IndexedNativeFieldCandidate, ...],
    *,
    concept_aliases: tuple[tuple[str, ...], ...],
    visible_field_count: Mapping[str, int],
    policy: PaperNativeRankPolicy,
    k: int = 5,
    raw_concepts: tuple[str, ...] | None = None,
    visible_field_names: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[int, ...]:
    """Rank already authorized direct receipts; retain bounded K5 output.

    Never call this on an authorization-neutral posting list: `candidates`
    must already be checked against the original current principal, field
    scope, typed comparator, health and source fingerprint by the index.
    """
    if type(k) is not int or k != 5 or not isinstance(policy, PaperNativeRankPolicy):
        raise ValueError("native paper Rank requires K5 and reviewed policy")
    route_ids = [candidate.route_id for candidate in candidates]
    if (
        len(set(route_ids)) != len(route_ids)
        or set(route_ids) != set(visible_field_count)
        or any(type(value) is not int or value < 1
               for value in visible_field_count.values())
    ):
        raise ValueError("paper Rank requires exact authorized visible routes")
    paper_v1 = policy.direct_score_mode == "paper_v1"
    if paper_v1 and (
        raw_concepts is None
        or type(raw_concepts) is not tuple
        or len(raw_concepts) > 8
        or any(
            type(label) is not str or not 1 <= len(label) <= 160
            or label != label.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in label)
            for label in raw_concepts
        )
        or visible_field_names is None
        or set(visible_field_names) != set(route_ids)
        or any(
            type(names) is not tuple
            or len(names) != len(set(names))
            or len(names) != visible_field_count[route]
            or any(type(name) is not str or not name for name in names)
            for route, names in visible_field_names.items()
        )
        or any(not set(candidate.required_output_fields) <= set(
            visible_field_names[candidate.route_id],
        ) for candidate in candidates)
    ):
        raise ValueError("paper v1 Rank requires bounded raw concepts and exact visible fields")
    web = set(policy.web_route_ids)

    def rank_key(position: int) -> tuple[int, int, bool, int, int, str]:
        candidate = candidates[position]
        route_id = candidate.route_id
        if paper_v1:
            assert raw_concepts is not None and visible_field_names is not None
            # Raw labels may affect ordering ONLY after native typed/ACL proof.
            return (
                -_paper_v1_concept_score(visible_field_names[route_id], raw_concepts),
                0, route_id in web, -policy.route_priorities.get(route_id, 1),
                visible_field_count[route_id], route_id,
            )
        exact, partial = _concept_match_strength(
            candidate.required_output_fields, concept_aliases,
        )
        return (
            -exact,
            -partial,
            route_id in web,
            -policy.route_priorities.get(route_id, 0),
            visible_field_count[route_id],
            route_id,
        )

    limit = 1 if policy.focus_direct else k
    return tuple(heapq.nsmallest(limit, range(len(candidates)), key=rank_key))


@dataclass(frozen=True, slots=True)
class IndexedNativeFieldResult:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified",
    ]
    registry_version: int
    index_snapshot_id: str
    requested_k: int
    qualified_count: int
    candidates: tuple[IndexedNativeFieldCandidate, ...]
    deterministic_paper_ranked: bool = False


def lookup_research_postings(
    self: NativeSchemaPostingIndex,
    router: SchemaRouter,
    query: str,
    *,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    k: int = STRICT_K,
    input_free_only: bool = False,
    allowed_tool_keys: tuple[str, ...] | None = None,
    _paper_rank_policy: PaperNativeRankPolicy | None = None,
    _paper_rank_aliases: tuple[tuple[str, ...], ...] = (),
    _paper_rank_domains: tuple[str, ...] = (),
    _paper_group_members: Mapping[str, frozenset[str]] | None = None,
    _paper_target_tools: tuple[str, ...] = (),
    _paper_raw_rank_concepts: tuple[str, ...] | None = None,
) -> IndexedNativeFieldResult:
    """Conjunctive source-owned lookup with reviewed paper Rank.

    Without owner Rank, the >K result abstains. An optional direct-only
    filter runs BEFORE candidate budgeting. No research ranker runs here.
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
    if _paper_rank_policy is not None and not isinstance(
        _paper_rank_policy, PaperNativeRankPolicy,
    ):
        raise ValueError("original paper Rank needs a reviewed policy")
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
        "ranked_unverified",
    ]
    if count > k:
        # Reviewed Rank always returns at least one position for a
        # nonempty cohort. Empty offsets, if encountered, still abstain.
        status = "ranked_unverified" if ranked_offsets else "over_k_unranked"
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
        deterministic_paper_ranked=use_paper_rank,
    )
