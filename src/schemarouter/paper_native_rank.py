"""Owner-pinned deterministic original-paper Rank, never model authority.

This is strictly a sort of already authorized, typed source receipts. No
provider-authored free-text metadata, execution data or model callback is
read by the comparator.
"""
from __future__ import annotations

import heapq
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

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
    # Retain the configuration names for existing paper_v1 callers, but
    # only the original paper comparator is an installed policy.
    direct_score_mode: Literal["paper_v1"] = "paper_v1"
    route_domains: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    route_priorities: dict[str, StrictInt] = Field(default_factory=dict)
    web_route_ids: tuple[str, ...] = ()
    # The frozen experiment selects one unnamed source; named overrides
    # and reviewed multi-target comparisons are filtered outside Rank.
    focus_direct: StrictBool = Field(default=True, json_schema_extra={"const": True})

    @model_validator(mode="after")
    def validate_owner_policy(self) -> PaperNativeRankPolicy:
        if self.direct_score_mode != "paper_v1" or self.focus_direct is not True:
            raise ValueError("installed paper Rank requires paper_v1 with focus_direct=True")
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
    visible_field_count: Mapping[str, int],
    policy: PaperNativeRankPolicy,
    k: int = 5,
    raw_concepts: tuple[str, ...] | None = None,
    visible_field_names: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[int, ...]:
    """Rank already authorized direct receipts; focus on one unnamed source.

    Never call this on an authorization-neutral posting list: `candidates`
    must already be checked against the original current principal, field
    scope, typed comparator, health and source fingerprint by the index.
    """
    if (
        type(k) is not int or k != 5 or not isinstance(policy, PaperNativeRankPolicy)
        or policy.direct_score_mode != "paper_v1" or policy.focus_direct is not True
    ):
        raise ValueError("native paper Rank requires K5 and reviewed policy")
    route_ids = [candidate.route_id for candidate in candidates]
    if (
        len(set(route_ids)) != len(route_ids)
        or set(route_ids) != set(visible_field_count)
        or any(type(value) is not int or value < 1
               for value in visible_field_count.values())
    ):
        raise ValueError("paper Rank requires exact authorized visible routes")
    if (
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

    def rank_key(position: int) -> tuple[int, bool, int, int, str]:
        candidate = candidates[position]
        route_id = candidate.route_id
        assert raw_concepts is not None and visible_field_names is not None
        # Raw labels may affect ordering ONLY after native typed/ACL proof.
        return (
            -_paper_v1_concept_score(visible_field_names[route_id], raw_concepts),
            route_id in web, -policy.route_priorities.get(route_id, 1),
            visible_field_count[route_id], route_id,
        )

    return tuple(heapq.nsmallest(1, range(len(candidates)), key=rank_key))
