"""Contracts for the #510 successor screen surface.

The successor exists because #506's screen produced no signal. Its whole value
depends on being a genuinely different surface, so disjointness is pinned here
rather than assumed.
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


def _rows(envelope: int, tool_calls: int, grounded: int, total: int = 10) -> list[dict]:
    rows = []
    for index in range(total):
        rows.append(
            {
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

    rates = qualification_rates(_rows(envelope=8, tool_calls=9, grounded=7))
    assert rates == {
        "envelope_valid_rate": 0.8,
        "tool_call_rate": 0.9,
        "grounded_fact_rate": 0.7,
    }


def test_all_three_must_pass():
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    assert qualifies(qualification_rates(_rows(8, 9, 7)))
    # The #506 failure mode: envelopes produced, nothing grounded.
    assert not qualifies(qualification_rates(_rows(10, 0, 0)))
    # One short on each axis in turn.
    assert not qualifies(qualification_rates(_rows(7, 9, 7)))
    assert not qualifies(qualification_rates(_rows(8, 8, 7)))
    assert not qualifies(qualification_rates(_rows(8, 9, 6)))


def test_an_empty_run_does_not_qualify():
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    assert not qualifies(qualification_rates([]))


def test_a_runtime_that_calls_tools_but_grounds_nothing_is_refused():
    # The criterion that exists for this case must be able to refuse on its own.
    # _rows(10, 0, 0) cannot prove that: no tool calls means tool_call_rate
    # refuses it regardless, so weakening grounded_fact_rate leaves it refused
    # for the wrong reason. This shape isolates the criterion.
    from scripts.qualify_agent_utility_runtime import qualification_rates, qualifies

    rates = qualification_rates(_rows(envelope=10, tool_calls=10, grounded=0))
    assert rates["envelope_valid_rate"] == 1.0
    assert rates["tool_call_rate"] == 1.0
    assert not qualifies(rates)
