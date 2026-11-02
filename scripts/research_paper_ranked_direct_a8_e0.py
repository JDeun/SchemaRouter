"""Opt-in A8 paper Understood FieldGroup -> authorized ranked K5 E0 only.

No new ranker, second field lookup, ToolCall materialization, agent loop or
execution permission. Existing original direct planning remains fail-closed at
>K; this returns a separately labelled unverified *research* shortlist.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import IndexedNativeFieldCandidate
from schemarouter.paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    _source_owned_understood_group,
)
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_scoped_understand_e0 import _validated_owner_snapshot

PaperRanker = Callable[
    [str, tuple[IndexedNativeFieldCandidate, ...], int], tuple[int, ...],
]


@dataclass(frozen=True, slots=True)
class PaperRankedDirectE0:
    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked",
        "ranked_unverified", "ranker_abstained_unverified",
    ]
    qualified_count: int
    ranked_route_ids: tuple[str, ...]
    requested_k: int = 5
    independent_quality_evidence: bool = False
    executable_authority: bool = False


def research_rank_paper_understood_direct_e0(
    ranker: PaperRanker,
    *,
    view: AuthorizedAgentToolSurface,
    understanding: PaperUnderstanding,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
) -> PaperRankedDirectE0:
    """Expose only source-authorized alternatives for experimental Top-K5.

    The original natural-language query reaches the optional ranker, whereas
    the trusted FieldGroup lookup uses its host-approved canonical alias.
    Private gold, executor fixtures and model parameter hints never reach it.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("ranked paper E0 requires original scoped source view")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("ranked paper E0 requires original native index")
    if not isinstance(understanding, PaperUnderstanding):
        raise ValueError("ranked paper E0 requires structured understanding")
    if not callable(ranker):
        raise ValueError("ranked paper E0 requires a callable research ranker")
    query = view.original_query
    if type(query) is not str or not 1 <= len(query.encode("utf-8")) <= 512:
        raise ValueError("ranked paper E0 requires bounded original query")

    view.assert_source_unchanged()
    pinned_owner = _validated_owner_snapshot(intent_registry, catalog)
    try:
        pinned_hints = understanding.model_dump_json()
        approved_hints, group = _source_owned_understood_group(
            understanding, catalog, intent_registry,
        )
    except (TypeError, ValueError, AttributeError, OverflowError):
        raise ValueError("invalid ranked paper E0 understanding") from None
    visible = frozenset(view.visible_route_ids)

    def assert_original_sources() -> None:
        view.assert_source_unchanged()
        if (
            _validated_owner_snapshot(intent_registry, catalog) != pinned_owner
            or understanding.model_dump_json() != pinned_hints
        ):
            raise PolicyViolationError("ranked paper E0 owner declarations changed")

    def empty_no_proof() -> PaperRankedDirectE0:
        assert_original_sources()
        return PaperRankedDirectE0("no_proven_hit", 0, ())

    if (
        approved_hints.source_type is not None
        and approved_hints.source_type != group.source_type
    ):
        return empty_no_proof()

    def original_query_ranker(
        _host_alias: str,
        candidates: tuple[IndexedNativeFieldCandidate, ...],
        k: int,
    ) -> tuple[int, ...]:
        # Reject any out-of-view source identity BEFORE model disclosure.
        assert_original_sources()
        if any(candidate.route_id not in visible for candidate in candidates):
            raise PolicyViolationError("ranked paper E0 candidate outside captured view")
        chosen = ranker(query, candidates, k)
        assert_original_sources()
        return chosen

    result = index.field_index.lookup(
        view.router, group.aliases[0], group=group,
        principal=view._principal, k=5,
        allowed_tool_keys=approved_hints.named_tools or None,
        _research_ranker=original_query_ranker,
    )
    assert_original_sources()
    if (
        result.status not in (
            "complete", "no_proven_hit", "over_k_unranked",
            "ranked_unverified", "ranker_abstained_unverified",
        )
        or any(candidate.route_id not in visible for candidate in result.candidates)
    ):
        raise PolicyViolationError("ranked paper E0 unproved source disclosure")
    return PaperRankedDirectE0(
        status=result.status,
        qualified_count=result.qualified_count,
        ranked_route_ids=tuple(candidate.route_id for candidate in result.candidates),
    )
