"""Research-only authorized fixed-K5 lexical+semantic RRF candidate selector.

This is a closed-world bounded ranking experiment, not calibrated no-fit,
executable authority, a product default or independent E2 task success.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from schemarouter import PolicyViolationError
from schemarouter.decisions import DecisionBackend
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
    _visible_fingerprints,
)

STRICT_K = 5
FIXED_RRF_CONSTANT = 60


@dataclass
class AuthorizedHybridFixed5Selector:
    """Fixed reciprocal-rank fusion on a single principal-scoped source.

    The source-native lexical rank comes from retrieve_authorized(), not
    a model-generated tool inventory. Semantic candidates come from the
    existing non-executable DecisionBackend bridge. Both are checked against
    one captured authority witness; gold and fixture executor are unavailable.
    """

    view: AuthorizedAgentToolSurface
    backend: DecisionBackend = field(repr=False)
    _semantic: AuthorizedFixed5DecisionSelector = field(init=False, repr=False)
    _source_fingerprints: dict[str, tuple[str, str]] = field(init=False, repr=False)
    last_status: str | None = field(default=None, init=False)
    last_semantic_status: str | None = field(default=None, init=False)
    last_model_input_bytes: int | None = field(default=None, init=False)
    calibrated_no_fit: bool = field(default=False, init=False)
    executable_authority: bool = field(default=False, init=False)
    independent_quality_evidence: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.view.assert_source_unchanged()
        self._semantic = AuthorizedFixed5DecisionSelector(self.view, self.backend)
        self._source_fingerprints = _visible_fingerprints(self.view)

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        if (
            type(query) is not str or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(source_ids) != len(set(source_ids))
            or _visible_fingerprints(self.view) != self._source_fingerprints
        ):
            raise PolicyViolationError("hybrid fixed5 source/view query mismatch")
        if not source_ids:
            # No visible source tools is NOT a calibrated task-no-fit claim.
            self.last_status = "no_visible_authorized_routes_not_no_fit"
            self.last_semantic_status = "not_called_empty_source"
            self.last_model_input_bytes = 0
            return []

        original = self.view.router.retrieve_authorized(
            query, principal=self.view._principal, k=len(source_ids),
        )
        self.view.assert_source_unchanged()
        lexical = [candidate.route_id for candidate in original.candidates]
        if (
            original.registry_version != self.view.witness[1]
            or len(lexical) != len(source_ids)
            or len(set(lexical)) != len(lexical)
            or set(lexical) != set(source_ids)
            or any(
                (
                    candidate.tool_fingerprint,
                    candidate.endpoint_fingerprint,
                ) != self._source_fingerprints[candidate.route_id]
                for candidate in original.candidates
            )
        ):
            raise PolicyViolationError("hybrid fixed5 lexical source identity drift")

        semantic = self._semantic(query, source_ids)
        self.view.assert_source_unchanged()
        if _visible_fingerprints(self.view) != self._source_fingerprints:
            raise PolicyViolationError("hybrid fixed5 source fingerprint drift")
        self.last_semantic_status = self._semantic.last_status
        self.last_model_input_bytes = self._semantic.last_model_input_bytes

        lexical_rank = {route: rank for rank, route in enumerate(lexical, 1)}
        semantic_rank = {route: rank for rank, route in enumerate(semantic, 1)}
        scores = {
            route: (
                1.0 / (FIXED_RRF_CONSTANT + lexical_rank[route])
                + (
                    1.0 / (FIXED_RRF_CONSTANT + semantic_rank[route])
                    if route in semantic_rank else 0.0
                )
            )
            for route in source_ids
        }
        ranked = sorted(
            source_ids,
            key=lambda route: (-scores[route], lexical_rank[route], route),
        )
        selected = list(ranked[:STRICT_K])
        # Explicit lexical backfill is deterministic and NEVER consults gold.
        # A model abstention is not treated as calibrated unsupported/no-fit.
        if not semantic:
            self.last_status = "semantic_abstained_lexical_fallback_not_no_fit"
        elif len(semantic) < min(STRICT_K, len(source_ids)):
            self.last_status = "partial_semantic_lexical_rrf_fill_unverified"
        else:
            self.last_status = "fixed_lexical_semantic_rrf_unverified"
        return selected
