"""Owner-pinned deterministic original-paper Rank, never model authority.

This is strictly a sort of already authorized, typed source receipts. No
provider-authored free-text metadata, execution data or model callback is
read by the comparator.
"""
from __future__ import annotations

import heapq
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from pydantic import Field, StrictInt, model_validator

from .field_group_retrieval import _alias_key
from .models import StrictModel

if TYPE_CHECKING:
    from .native_semantic_index import IndexedNativeFieldCandidate


_DOMAIN_ID = re.compile(r"[a-zA-Z][a-zA-Z0-9._:-]{0,79}\Z")
_MAX_POLICY_BYTES = 1_500_000
_MAX_POLICY_ROUTES = 5_000


class PaperNativeRankPolicy(StrictModel):
    """Trusted host-reviewed route annotations pinned to a native snapshot.

    These annotations affect discovery priority only. They do not grant
    permission, assert vendor origin, bind arguments or enable execution.
    """

    snapshot_id: str
    route_domains: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    route_priorities: dict[str, StrictInt] = Field(default_factory=dict)
    web_route_ids: tuple[str, ...] = ()

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
    # Strict original-paper precedence: even two substring concept matches
    # cannot cancel out a single owner-declared exact concept match.
    return exact, partial


def rank_authorized_paper_direct(
    candidates: tuple[IndexedNativeFieldCandidate, ...],
    *,
    concept_aliases: tuple[tuple[str, ...], ...],
    visible_field_count: Mapping[str, int],
    policy: PaperNativeRankPolicy,
    k: int = 5,
) -> tuple[int, ...]:
    """Choose exact original candidate offsets in O(N log K) and O(K) memory.

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
    web = set(policy.web_route_ids)

    def rank_key(position: int) -> tuple[int, int, bool, int, int, str]:
        candidate = candidates[position]
        route_id = candidate.route_id
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

    return tuple(heapq.nsmallest(k, range(len(candidates)), key=rank_key))
