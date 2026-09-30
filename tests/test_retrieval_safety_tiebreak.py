"""Equally-scored candidates must not surface a destructive route first.

`retrieve` is the side-effect-free discovery surface an agent uses to choose what to
call. When no candidate matches the query, every score is 0.0 and the sort key falls
through `-score`, `-specificity` (0.0 outside the structural profile), and the
projection flag to `tool.key` -- plain alphabetical order. A destructive capability
whose tool key happens to sort early is then rank 1 for any unmatched query.

Execution still refuses it: the policy layer raises PolicyViolationError without
allow_destructive. So this is not a way to run something dangerous. It is a ranking
defect: the safest thing to hand an agent that asked for something we do not have is
not the most destructive route in the catalog.

The structural profile sometimes escapes it, because specificity can break the tie
before the alphabetical fallback -- but only when the catalog happens to produce
different specificity values, so it is incidental rather than a guarantee. Both
profiles are pinned here.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)


def _router(structural: bool = False) -> SchemaRouter:
    router = SchemaRouter(registry=InMemoryRegistry(), structural_retrieval=structural)
    # "aa_" sorts before "zz_" so the alphabetical fallback puts the destructive
    # route first; the names make the ordering visible rather than incidental.
    router.add_tool(
        ToolSpec(
            name="aa_admin",
            description="Administrative maintenance",
            provider="internal",
            access_mode="python",
            source_type="calculated",
            endpoints=[
                EndpointSpec(
                    name="drop_database",
                    description="Permanently drop a database",
                    read_only=False,
                    destructive=True,
                    parameters=[ParameterSpec(name="name", required=True, json_schema={"type": "string"})],
                )
            ],
        )
    )
    router.add_tool(
        ToolSpec(
            name="zz_reports",
            description="Reporting",
            provider="internal",
            access_mode="python",
            source_type="calculated",
            endpoints=[
                EndpointSpec(
                    name="read_logs",
                    description="Read application logs",
                    read_only=True,
                    destructive=False,
                    parameters=[ParameterSpec(name="query", required=True, json_schema={"type": "string"})],
                )
            ],
        )
    )
    return router


UNMATCHED = "xyzzy plugh nothing in this catalog matches"


def _route_ids(router: SchemaRouter, query: str) -> list[str]:
    return [c.route_id for c in router.retrieve(PlanRequest(query=query), k=5).candidates]


def test_scores_really_are_tied_for_an_unmatched_query():
    # Guards the premise. If scoring ever starts separating these, the ordering
    # assertions below would pass for a reason that has nothing to do with safety.
    scores = [c.score for c in _router().retrieve(PlanRequest(query=UNMATCHED), k=5).candidates]
    assert scores and all(s == 0.0 for s in scores), scores


def test_a_tied_destructive_route_does_not_rank_first():
    assert _route_ids(_router(), UNMATCHED)[0] == "zz_reports.read_logs"


def test_the_destructive_route_is_still_offered_just_lower():
    # Demoting is not hiding. The catalog is complete; only the order changes.
    assert "aa_admin.drop_database" in _route_ids(_router(), UNMATCHED)


def test_a_better_scoring_destructive_route_still_wins():
    # The safety term is a TIE-break. A query that genuinely asks to drop a database
    # must still get that route first, or retrieval would be lying about relevance.
    ids = _route_ids(_router(), "permanently drop a database")
    assert ids[0] == "aa_admin.drop_database"


@pytest.mark.parametrize("structural", [False, True])
def test_both_profiles_agree_on_this(structural):
    assert _route_ids(_router(structural), UNMATCHED)[0] == "zz_reports.read_logs"
