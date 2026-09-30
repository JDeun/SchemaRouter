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


def test_the_roster_model_revisions_are_frozen():
    from scripts.qualify_agent_utility_runtime import ROSTER_REVISIONS

    assert ROSTER_REVISIONS == {
        "HuggingFaceTB/SmolLM3-3B": "a07cc9a04f16550a088caea529712d1d335b0ac1",
        "Qwen/Qwen3-4B": "1cfa9a7208912126459214e8b04321603b3df60c",
        "Qwen/Qwen3-8B": "b968826d9c46dd6066d109eabc6255188de91218",
    }


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


def test_an_empty_run_is_refused_rather_than_treated_as_zero_rates():
    # A zero-rate dict for zero episodes would be byte-identical to a real
    # 24+-episode run in which every episode failed. Those two must not be
    # able to masquerade as each other, so this raises rather than returning
    # `{name: 0.0 ...}` (which would make an unexecuted run "not qualify"
    # the same way a genuine total failure does).
    from scripts.qualify_agent_utility_runtime import qualification_rates

    with pytest.raises(ValueError, match="MINIMUM_EPISODES"):
        qualification_rates([])


def test_a_fact_recall_without_any_tool_call_is_not_grounded():
    from scripts.qualify_agent_utility_runtime import qualification_rates

    rows = _rows(envelope=40, tool_calls=0, grounded=40, total=40)
    rates = qualification_rates(rows)
    assert rates["envelope_valid_rate"] == 1.0
    assert rates["tool_call_rate"] == 0.0
    assert rates["grounded_fact_rate"] == 0.0


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


def test_the_first_qualifier_wins_when_evaluated_alone():
    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    assert _select_runtime_from_rates({ROSTER[0]: passing}) == ROSTER[0]


def test_a_later_candidates_results_after_a_qualifier_are_refused():
    # The preregistration says "later candidates are not run" — an act, not
    # just an answer. Holding a later candidate's results once an earlier
    # one qualified is the forbidden state even though _select_runtime_from_rates would
    # still return the right (first) answer despite them; #510's own
    # recorded risk is temptation, which has already materialised the
    # moment those later numbers exist.
    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    better = {"envelope_valid_rate": 1.0, "tool_call_rate": 1.0, "grounded_fact_rate": 1.0}
    with pytest.raises(ValueError, match="later candidates"):
        _select_runtime_from_rates({ROSTER[0]: passing, ROSTER[1]: better})


def test_a_failing_candidate_falls_through_to_the_next():
    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    failing = {"envelope_valid_rate": 1.0, "tool_call_rate": 1.0, "grounded_fact_rate": 0.0}
    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    assert _select_runtime_from_rates({ROSTER[0]: failing, ROSTER[1]: passing}) == ROSTER[1]


def test_no_qualifier_returns_none():
    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}
    assert _select_runtime_from_rates({name: failing for name in ROSTER}) is None


def test_evaluating_out_of_order_is_refused():
    # Skipping ahead is how cherry-picking looks in practice.
    import pytest

    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    passing = {"envelope_valid_rate": 0.85, "tool_call_rate": 0.95, "grounded_fact_rate": 0.75}
    with pytest.raises(ValueError, match="in order"):
        _select_runtime_from_rates({ROSTER[1]: passing})


def test_an_unknown_candidate_is_refused():
    import pytest

    from scripts.qualify_agent_utility_runtime import _select_runtime_from_rates

    with pytest.raises(ValueError, match="frozen roster"):
        _select_runtime_from_rates({"some/other-model": {}})


def test_an_incomplete_roster_is_not_a_verdict():
    # Only the first candidate ran and it failed. _select_runtime_from_rates returns None
    # here for the same reason it returns None once every candidate has
    # failed: None alone does not distinguish "keep going" from "no
    # qualifier". roster_exhausted is what pins that distinction, so both
    # halves must be asserted together, not _select_runtime_from_rates's return value
    # alone.
    from scripts.qualify_agent_utility_runtime import (
        ROSTER,
        _select_runtime_from_rates,
        roster_exhausted,
    )

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}
    partial = {ROSTER[0]: failing}
    assert _select_runtime_from_rates(partial) is None
    assert not roster_exhausted(partial)


def test_none_is_only_a_verdict_once_the_roster_is_exhausted():
    from scripts.qualify_agent_utility_runtime import (
        ROSTER,
        _select_runtime_from_rates,
        roster_exhausted,
    )

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}

    partial = {ROSTER[0]: failing}
    assert _select_runtime_from_rates(partial) is None
    assert not roster_exhausted(partial), "a prefix is not a verdict"

    complete = {name: failing for name in ROSTER}
    assert _select_runtime_from_rates(complete) is None
    assert roster_exhausted(complete), "only this pair may be reported as 'none qualified'"


def test_roster_exhausted_ignores_qualification_and_only_asks_about_coverage():
    # Deliberately a genuine total-failure shape, not an all-qualifying one:
    # _select_runtime_from_rates now refuses a results dict in which a later candidate
    # has results after an earlier one qualified (see
    # test_a_later_candidates_results_after_a_qualifier_are_refused), so a
    # test pinning coverage semantics must not depict three simultaneously
    # qualifying candidates as a normal input.
    from scripts.qualify_agent_utility_runtime import ROSTER, roster_exhausted

    failing = {"envelope_valid_rate": 0.0, "tool_call_rate": 0.0, "grounded_fact_rate": 0.0}
    assert roster_exhausted({name: failing for name in ROSTER})
    assert not roster_exhausted({})


# --- unmeasured rates must not masquerade as a measured failure ------------
#
# roster_exhausted is pure key coverage: set(results) == set(ROSTER). It does
# not look at the values. Left alone, that means a results dict whose values
# were never really measured — empty, built from zero episodes, or missing
# the criteria entirely — would still read as the roster's terminal "no
# candidate qualified" state, identical to a genuine run in which every
# candidate failed. The four cases below are the adversarial states a
# reviewer constructed to show that; qualification_rates and qualifies must
# refuse the first three, and the fourth (a real run that really failed)
# must still work exactly as before.


def test_a_roster_of_empty_rate_dicts_is_refused():
    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    with pytest.raises(ValueError, match="missing required criteria"):
        _select_runtime_from_rates({name: {} for name in ROSTER})


def test_a_roster_built_from_zero_episode_runs_is_refused():
    from scripts.qualify_agent_utility_runtime import ROSTER, qualification_rates

    with pytest.raises(ValueError, match="MINIMUM_EPISODES"):
        {name: qualification_rates([]) for name in ROSTER}  # noqa: F841


def test_a_roster_of_rates_missing_the_measured_criteria_is_refused():
    from scripts.qualify_agent_utility_runtime import ROSTER, _select_runtime_from_rates

    unmeasured = {"foo": 1.0}
    with pytest.raises(ValueError, match="missing required criteria"):
        _select_runtime_from_rates({name: unmeasured for name in ROSTER})


def test_a_genuine_full_roster_failure_still_reports_as_a_verdict():
    # The one state of the four that must keep working: real rows, run
    # through qualification_rates, for every roster candidate, all of them
    # failing every criterion.
    from scripts.qualify_agent_utility_runtime import (
        ROSTER,
        _select_runtime_from_rates,
        qualification_rates,
        roster_exhausted,
    )

    failing_rows = _rows(envelope=0, tool_calls=0, grounded=0, total=40)
    results = {name: qualification_rates(failing_rows) for name in ROSTER}
    assert _select_runtime_from_rates(results) is None
    assert roster_exhausted(results)


def test_a_none_rate_value_is_refused_rather_than_crashing():
    # None >= threshold raises TypeError in plain Python; qualifies must
    # fail closed with the same ValueError as any other unmeasured rate,
    # not crash with a type error.
    from scripts.qualify_agent_utility_runtime import qualifies

    rates = {
        "envelope_valid_rate": None,
        "tool_call_rate": 0.95,
        "grounded_fact_rate": 0.75,
    }
    with pytest.raises(ValueError, match="non-numeric"):
        qualifies(rates)


# --- qualification provenance -----------------------------------------------


def _qualification_rows(corpus, *, envelope=36, tool_calls=36, grounded=36):
    rows = []
    for index, task in enumerate(corpus["tasks"]):
        rows.append(
            {
                "semantic_task_id": task["semantic_task_id"],
                "final_envelope_valid": index < envelope,
                "tool_call_count": 1 if index < tool_calls else 0,
                "required_fact_recall": 1.0 if index < grounded else 0.0,
            }
        )
    return rows


def _qualification_evidence(candidate, corpus, rows=None):
    from scripts.generate_agent_utility_v8_qualification_corpus import (
        QUALIFICATION_EVIDENCE_CLASS,
        QUALIFICATION_SURFACE,
    )
    from scripts.qualify_agent_utility_runtime import ROSTER_REVISIONS

    return {
        "candidate_model": candidate,
        "model_revision": ROSTER_REVISIONS[candidate],
        "source_revision": corpus["source_revision"],
        "harness_revision": corpus["source_revision"],
        "corpus_tasks_sha256": corpus["tasks_sha256"],
        "evidence_class": QUALIFICATION_EVIDENCE_CLASS,
        "surface": QUALIFICATION_SURFACE,
        "rows": list(rows if rows is not None else _qualification_rows(corpus)),
    }


def test_qualification_surface_is_balanced_and_separate():
    from scripts.generate_agent_utility_v8_qualification_corpus import (
        build_qualification_corpus,
    )
    from scripts.validate_agent_utility_v8_qualification_corpus import (
        validate_qualification_corpus,
    )

    corpus = build_qualification_corpus("a" * 40)
    summary = validate_qualification_corpus(corpus)
    assert summary["tasks"] == 36
    assert corpus["expected_episode_count"] == 36
    assert len(
        {
            (task["projection_stratum"], task["language"])
            for task in corpus["tasks"]
        }
    ) == 36


def test_public_runtime_selection_requires_verified_provenance():
    from scripts.generate_agent_utility_v8_qualification_corpus import (
        build_qualification_corpus,
    )
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    corpus = build_qualification_corpus("a" * 40)
    evidence = _qualification_evidence(ROSTER[0], corpus)
    assert (
        select_runtime({ROSTER[0]: evidence}, qualification_corpus=corpus)
        == ROSTER[0]
    )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("corpus_tasks_sha256", "wrong", "corpus_tasks_sha256"),
        ("source_revision", "wrong", "source_revision"),
        ("harness_revision", "wrong", "harness_revision"),
        ("model_revision", "", "model_revision"),
        ("evidence_class", "experiment", "evidence_class"),
        ("surface", "successor", "surface"),
    ],
)
def test_runtime_selection_refuses_wrong_qualification_provenance(field, value, match):
    from scripts.generate_agent_utility_v8_qualification_corpus import (
        build_qualification_corpus,
    )
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    corpus = build_qualification_corpus("a" * 40)
    evidence = _qualification_evidence(ROSTER[0], corpus)
    evidence[field] = value
    with pytest.raises(ValueError, match=match):
        select_runtime({ROSTER[0]: evidence}, qualification_corpus=corpus)


def test_runtime_selection_refuses_a_partial_surface_even_above_minimum_n():
    from scripts.generate_agent_utility_v8_qualification_corpus import (
        build_qualification_corpus,
    )
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    corpus = build_qualification_corpus("a" * 40)
    rows = _qualification_rows(corpus)[:24]
    evidence = _qualification_evidence(ROSTER[0], corpus, rows)
    with pytest.raises(ValueError, match="episode_count"):
        select_runtime({ROSTER[0]: evidence}, qualification_corpus=corpus)


def test_runtime_selection_refuses_rows_from_another_surface():
    from scripts.generate_agent_utility_v8_qualification_corpus import (
        build_qualification_corpus,
    )
    from scripts.qualify_agent_utility_runtime import ROSTER, select_runtime

    corpus = build_qualification_corpus("a" * 40)
    rows = _qualification_rows(corpus)
    rows[0] = dict(rows[0], semantic_task_id="P0000")
    evidence = _qualification_evidence(ROSTER[0], corpus, rows)
    with pytest.raises(ValueError, match="task-id set mismatch"):
        select_runtime({ROSTER[0]: evidence}, qualification_corpus=corpus)
