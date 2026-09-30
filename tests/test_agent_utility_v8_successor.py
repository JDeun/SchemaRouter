"""Contracts for the #510 successor screen surface.

The successor exists because #506's screen produced no signal. Its surface is
the #506 corpus under a distinct identifier space (`S####` instead of
`P####`): every task is byte-identical to its #506 counterpart apart from that
prefix (see test_the_default_prefix_leaves_the_506_corpus_byte_identical).
"Disjoint" here means no shared *query string* with any prior surface, pinned
below — it is not a content-independent surface. That is acceptable because
#506's screen never called a tool, so no observation content from that corpus
ever reached a model, and nothing in this pipeline trains on prior runs; see
docs/research/successor-screen.md for the recorded reasoning.
"""
from __future__ import annotations

import pytest

from scripts.agent_utility_prior_query_guard import normalize_query
from scripts.agent_utility_v7_projection import (
    PROJECTION_STRATA,
    build_projection_task,
    projection_authoring_slots,
)
from scripts.generate_agent_utility_v8_successor_corpus import (
    build_corpus,
    successor_authoring_slots,
)
from scripts.validate_agent_utility_v8_successor_corpus import validate


def test_the_guard_manifest_is_unchanged_by_this_branch():
    # known_prior_query_manifest()["union_sha256"] is stamped into generated
    # v3/v4/v6 corpora as prior_query_manifest_sha256 and hard-checked by
    # their validators. A stored corpus artifact created before this branch
    # must still validate against main, so this branch must not register a
    # new surface in the guard (see generate_agent_utility_v8_successor_corpus
    # for how #506 disjointness is checked without doing that). This pins the
    # literal value from commit 10d3a0b, the last commit before this branch
    # touched the guard; it must not drift.
    from scripts.agent_utility_prior_query_guard import known_prior_query_manifest

    manifest = known_prior_query_manifest()
    assert manifest["union_sha256"] == (
        "729124dd6e746d342085b368e76ef5697379259733be595bf660d9bc369951b7"
    )
    assert manifest["union_count"] == 1106


def test_the_default_prefix_leaves_the_506_corpus_byte_identical():
    # The successor must not perturb #506's frozen surface.
    slots = projection_authoring_slots()
    for index, slot in enumerate(slots):
        assert build_projection_task(slot, index) == build_projection_task(
            slot, index, prefix="P"
        )


def test_the_successor_shares_no_query_with_506():
    prior = {
        normalize_query(str(build_projection_task(slot, index)["query"]))
        for index, slot in enumerate(projection_authoring_slots())
    }
    successor = {
        normalize_query(str(task["query"])) for task in build_corpus("a" * 40)["tasks"]
    }
    assert prior, "the #506 surface must be non-empty for this test to mean anything"
    assert successor
    assert not (prior & successor), sorted(prior & successor)[:5]


def test_the_successor_keeps_the_506_shape():
    corpus = build_corpus("a" * 40)
    tasks = corpus["tasks"]
    assert len(tasks) == 144
    assert {task["projection_stratum"] for task in tasks} == set(PROJECTION_STRATA)
    assert corpus["condition_manifest"]["conditions"] == [
        "RAW-FULL",
        "PROJECTED",
        "PROJECTED+CONTRACT",
        "ORACLE-MINIMAL",
    ]
    assert corpus["catalog_sizes"] == [100, 250]


def test_the_successor_uses_its_own_identifier_space():
    slots = successor_authoring_slots()
    assert all(str(slot["semantic_task_id"]).startswith("S") for slot in slots)
    tasks = build_corpus("a" * 40)["tasks"]
    assert all(str(task["semantic_task_id"]).startswith("S") for task in tasks)


def test_generation_refuses_a_surface_that_overlaps_a_prior_one(monkeypatch):
    # The disjointness check must be enforced at generation, not left to a test.
    from scripts import generate_agent_utility_v8_successor_corpus as generator

    monkeypatch.setattr(generator, "SUCCESSOR_PREFIX", "P")
    with pytest.raises(SystemExit):
        generator.build_corpus("a" * 40)


def test_validation_accepts_the_generated_corpus():
    summary = validate(build_corpus("a" * 40))
    assert summary["tasks"] == 144
    assert summary["cells"] == 36


# --- instrument qualification ----------------------------------------------


def _rows(envelope: int, tool_calls: int, grounded: int, total: int = 40) -> list[dict]:
    # `total` defaults above MINIMUM_EPISODES so these rates exercise
    # qualification_rates without tripping the minimum-N floor. The counts
    # below are all out of a denominator of 10, scaled by 4 here, to keep
    # the same rates (0.8, 0.9, 0.7, ...) the tests were written against.
    rows = []
    for index in range(total):
        rows.append(
            {
                "semantic_task_id": f"Q{index:04d}",
                "final_envelope_valid": index < envelope,
                "tool_call_count": 1 if index < tool_calls else 0,
                "required_fact_recall": 1.0 if index < grounded else 0.0,
            }
        )
    return rows


def test_the_thresholds_are_the_preregistered_ones():
    # Frozen by issue #510. A plan may not tune them.
    from scripts.qualify_agent_utility_runtime import ELIGIBILITY

    assert ELIGIBILITY == {
        "envelope_valid_rate": 0.80,
        "tool_call_rate": 0.90,
        "grounded_fact_rate": 0.70,
    }


def test_the_roster_is_frozen_and_ordered():
    from scripts.qualify_agent_utility_runtime import ROSTER

    assert ROSTER == (
        "HuggingFaceTB/SmolLM3-3B",
        "Qwen/Qwen3-4B",
        "Qwen/Qwen3-8B",
    )


def test_rates_are_computed_per_episode():
    from scripts.qualify_agent_utility_runtime import qualification_rates

    rates = qualification_rates(_rows(envelope=32, tool_calls=36, grounded=28))
    assert rates == {
        "envelope_valid_rate": 0.8,
        "tool_call_rate": 0.9,
        "grounded_fact_rate": 0.7,
    }


def test_all_three_must_pass():
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    assert qualifies(qualification_rates(_rows(32, 36, 28)))
    # The #506 failure mode: envelopes produced, nothing grounded.
    assert not qualifies(qualification_rates(_rows(40, 0, 0)))
    # One short on each axis in turn.
    assert not qualifies(qualification_rates(_rows(28, 36, 28)))
    assert not qualifies(qualification_rates(_rows(32, 32, 28)))
    assert not qualifies(qualification_rates(_rows(32, 36, 24)))


def test_an_empty_run_does_not_qualify():
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    assert not qualifies(qualification_rates([]))


def test_a_runtime_that_calls_tools_but_grounds_nothing_is_refused():
    # The criterion that exists for this case must be able to refuse on its own.
    # _rows(40, 0, 0) cannot prove that: no tool calls means tool_call_rate
    # refuses it regardless, so weakening grounded_fact_rate leaves it refused
    # for the wrong reason. This shape isolates the criterion.
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    rates = qualification_rates(_rows(envelope=40, tool_calls=40, grounded=0))
    assert rates["envelope_valid_rate"] == 1.0
    assert rates["tool_call_rate"] == 1.0
    assert not qualifies(rates)


def test_a_duplicate_episode_is_refused_rather_than_inflating_a_rate():
    # 7 good + 3 bad refuses (0.7 grounded rate). Appending 20 copies of an
    # already-counted good row must not be a way to qualify: there is no
    # episode identity without semantic_task_id, and no dedup without
    # refusing a repeat outright.
    from scripts.qualify_agent_utility_runtime import qualification_rates

    rows = _rows(envelope=24, tool_calls=24, grounded=17, total=24)
    duplicated = rows + [dict(rows[0]) for _ in range(20)]
    with pytest.raises(ValueError, match="duplicate episode"):
        qualification_rates(duplicated)


def test_a_run_below_the_minimum_episode_floor_is_refused():
    # A single episode qualifying at 1.0/1.0/1.0 is not evidence about a
    # runtime.
    from scripts.qualify_agent_utility_runtime import (
        MINIMUM_EPISODES,
        qualification_rates,
    )

    single = [
        {
            "semantic_task_id": "Q0000",
            "final_envelope_valid": True,
            "tool_call_count": 1,
            "required_fact_recall": 1.0,
        }
    ]
    with pytest.raises(ValueError, match="MINIMUM_EPISODES"):
        qualification_rates(single)
    assert MINIMUM_EPISODES > len(single)


def test_final_envelope_valid_must_be_a_strict_bool():
    # The string "false" is truthy in Python; reading final_envelope_valid
    # for truthiness would count it as a valid envelope.
    from scripts.qualify_agent_utility_runtime import qualification_rates

    rows = _rows(envelope=24, tool_calls=24, grounded=17, total=24)
    rows[0] = dict(rows[0], final_envelope_valid="false")
    with pytest.raises(ValueError, match="final_envelope_valid"):
        qualification_rates(rows)


def test_a_well_formed_run_still_qualifies():
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    rows = _rows(envelope=24, tool_calls=24, grounded=17, total=24)
    assert qualifies(qualification_rates(rows))


def test_the_first_qualifier_wins_even_if_a_later_one_scores_higher():
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    better = {"envelope_valid_rate": 1.0, "tool_call_rate": 1.0, "grounded_fact_rate": 1.0}
    assert select_runtime({ROSTER[0]: passing, ROSTER[1]: better}) == ROSTER[0]


def test_a_failing_candidate_falls_through_to_the_next():
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    failing = {"envelope_valid_rate": 1.0, "tool_call_rate": 1.0, "grounded_fact_rate": 0.0}
    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    assert select_runtime({ROSTER[0]: failing, ROSTER[1]: passing}) == ROSTER[1]


def test_no_qualifier_returns_none():
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}
    assert select_runtime({name: failing for name in ROSTER}) is None


def test_evaluating_out_of_order_is_refused():
    # Skipping ahead is how cherry-picking looks in practice.
    import pytest

    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    with pytest.raises(ValueError, match="in order"):
        select_runtime({ROSTER[1]: passing})


def test_an_unknown_candidate_is_refused():
    import pytest

    from scripts.qualify_agent_utility_runtime import select_runtime

    with pytest.raises(ValueError, match="frozen roster"):
        select_runtime({"some/other-model": {}})


def test_an_incomplete_roster_is_not_a_verdict():
    # Only the first candidate ran and it failed. select_runtime returns None
    # here for the same reason it returns None once every candidate has
    # failed: None alone does not distinguish "keep going" from "no
    # qualifier". roster_exhausted is what pins that distinction, so both
    # halves must be asserted together, not select_runtime's return value
    # alone.
    from scripts.qualify_agent_utility_runtime import (
        ROSTER,
        roster_exhausted,
        select_runtime,
    )

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}
    partial = {ROSTER[0]: failing}
    assert select_runtime(partial) is None
    assert not roster_exhausted(partial)


def test_none_is_only_a_verdict_once_the_roster_is_exhausted():
    from scripts.qualify_agent_utility_runtime import (
        ROSTER,
        roster_exhausted,
        select_runtime,
    )

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}

    partial = {ROSTER[0]: failing}
    assert select_runtime(partial) is None
    assert not roster_exhausted(partial), "a prefix is not a verdict"

    complete = {name: failing for name in ROSTER}
    assert select_runtime(complete) is None
    assert roster_exhausted(complete), "only this pair may be reported as 'none qualified'"


def test_roster_exhausted_ignores_qualification_and_only_asks_about_coverage():
    from scripts.qualify_agent_utility_runtime import ROSTER, roster_exhausted

    passing = {"envelope_valid_rate": 1.0, "tool_call_rate": 1.0, "grounded_fact_rate": 1.0}
    assert roster_exhausted({name: passing for name in ROSTER})
    assert not roster_exhausted({})
