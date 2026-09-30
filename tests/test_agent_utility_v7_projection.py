"""Contracts for the #506 output-field projection experiment.

The experiment holds the query, the candidate exposure, the route, and the raw
tool response fixed across every condition, and varies only the observation that
is handed back to the agent. These tests pin the properties that make that
comparison honest: projection may only ever *remove* declared fields, control
keys survive in every condition, and the stated difference between conditions is
real rather than an artifact of the corpus.
"""
from __future__ import annotations

import json

import pytest

from scripts.agent_utility_v7_projection import (
    CONTROL_KEYS,
    PROJECTION_CONDITIONS,
    build_projection_task,
    project_observation,
    projection_authoring_slots,
)

RAW = {
    "status": "ok",
    "youngs_modulus": 131.0,
    "unit": "GPa",
    "source_id": "SRC-P0001-A",
    "youngs_modulus_at_900k": 96.4,
    "youngs_modulus_mpa": 131000.0,
    "legacy_youngs_modulus": 118.0,
    "operator_note": "Superseded record retained for audit.",
}
PLANNED = ("youngs_modulus", "unit", "source_id")
GOLD = ("youngs_modulus", "unit", "source_id")
CONTRACTS = {
    "youngs_modulus": {
        "semantic_id": "materials.youngs_modulus",
        "unit": "GPa",
        "qualifiers": {"temperature_k": 300},
    }
}


def _project(condition: str, observation: dict | None = None) -> dict:
    return project_observation(
        observation if observation is not None else RAW,
        condition=condition,
        planned_fields=PLANNED,
        gold_fields=GOLD,
        field_contracts=CONTRACTS,
    )


def test_raw_full_hands_back_the_whole_record():
    assert _project("RAW-FULL") == RAW


def test_projected_drops_the_undeclared_fields():
    projected = _project("PROJECTED")
    assert set(projected) == {"status", *PLANNED}
    assert "youngs_modulus_at_900k" not in projected
    assert "legacy_youngs_modulus" not in projected


def test_projection_never_invents_a_field():
    # The point of the experiment is that projection only ever removes. A
    # condition that added a key would be measuring something else.
    for condition in PROJECTION_CONDITIONS:
        assert set(_project(condition)).issubset(set(RAW) | {"field_contracts"})


def test_projected_values_are_identical_to_the_raw_values():
    projected = _project("PROJECTED")
    for key, value in projected.items():
        assert value == RAW[key], key


def test_contract_condition_adds_only_the_contract_block():
    projected = _project("PROJECTED")
    with_contract = _project("PROJECTED+CONTRACT")
    assert set(with_contract) - set(projected) == {"field_contracts"}
    assert with_contract["field_contracts"] == {"youngs_modulus": CONTRACTS["youngs_modulus"]}


def test_contract_block_covers_only_fields_that_survived_projection():
    contracts = dict(CONTRACTS)
    contracts["youngs_modulus_at_900k"] = {"unit": "GPa"}
    result = project_observation(
        RAW,
        condition="PROJECTED+CONTRACT",
        planned_fields=PLANNED,
        gold_fields=GOLD,
        field_contracts=contracts,
    )
    assert "youngs_modulus_at_900k" not in result["field_contracts"]


def test_oracle_minimal_keeps_only_the_gold_fields():
    result = project_observation(
        RAW,
        condition="ORACLE-MINIMAL",
        planned_fields=PLANNED,
        gold_fields=("youngs_modulus",),
        field_contracts=CONTRACTS,
    )
    assert set(result) == {"status", "youngs_modulus"}


@pytest.mark.parametrize("condition", PROJECTION_CONDITIONS)
def test_control_keys_survive_every_condition(condition):
    # An agent that cannot see `status`/`error` cannot tell a failed call from an
    # empty one, which would confound the answer-quality comparison.
    failed = {"status": "error", "error": "unavailable_tool", "youngs_modulus": 131.0}
    result = project_observation(
        failed,
        condition=condition,
        planned_fields=PLANNED,
        gold_fields=GOLD,
        field_contracts=CONTRACTS,
    )
    assert set(result) & CONTROL_KEYS == {"status", "error"}
    assert result["error"] == "unavailable_tool"


def test_an_unknown_condition_fails_closed():
    with pytest.raises(ValueError):
        _project("SR-5")


def test_projection_does_not_mutate_the_frozen_record():
    before = json.dumps(RAW, sort_keys=True)
    for condition in PROJECTION_CONDITIONS:
        _project(condition)
    assert json.dumps(RAW, sort_keys=True) == before


# --- corpus contracts -------------------------------------------------------


def _tasks() -> list[dict]:
    return [
        build_projection_task(slot, index)
        for index, slot in enumerate(projection_authoring_slots())
    ]


def test_every_task_declares_gold_within_planned_within_raw():
    for task in _tasks():
        for step in task["executor_fixture"]["steps"]:
            raw = set(step["observation"])
            planned = set(step["planned_fields"])
            gold = set(step["gold_fields"])
            assert gold <= planned, (task["semantic_task_id"], step["route_id"])
            assert planned <= raw, (task["semantic_task_id"], step["route_id"])


def test_raw_records_actually_carry_more_than_the_plan():
    # Without competing content in the raw record, RAW-FULL and PROJECTED are the
    # same observation and the experiment would measure nothing. This is the
    # single assumption the whole comparison rests on, so it is pinned per step.
    for task in _tasks():
        for step in task["executor_fixture"]["steps"]:
            extra = set(step["observation"]) - set(step["planned_fields"]) - CONTROL_KEYS
            assert extra, (task["semantic_task_id"], step["route_id"])


def test_required_facts_are_answerable_from_the_projected_observation():
    # If a required fact only exists in a field that projection removes, then
    # PROJECTED is being scored against evidence it was never shown.
    for task in _tasks():
        available: dict[str, object] = {}
        for step in task["executor_fixture"]["steps"]:
            projected = project_observation(
                step["observation"],
                condition="PROJECTED",
                planned_fields=step["planned_fields"],
                gold_fields=step["gold_fields"],
                field_contracts=step.get("field_contracts", {}),
            )
            available.update(projected)
        for fact in task["required_facts"]:
            assert fact["key"] in available, (task["semantic_task_id"], fact["key"])
            assert available[fact["key"]] == fact["value"], fact["key"]


def test_distractor_strata_are_all_represented():
    strata = {task["projection_stratum"] for task in _tasks()}
    assert strata == {
        "qualifier_sibling",
        "unit_variant",
        "superseded_duplicate",
        "nested_record",
        "cross_provider_name_collision",
        "multi_step_provenance",
    }


def test_slot_plan_is_balanced_and_unique():
    slots = projection_authoring_slots()
    ids = [slot["semantic_task_id"] for slot in slots]
    assert len(ids) == len(set(ids))
    per_cell: dict[tuple[str, str], int] = {}
    for slot in slots:
        key = (slot["projection_stratum"], slot["language"])
        per_cell[key] = per_cell.get(key, 0) + 1
    assert len(set(per_cell.values())) == 1, per_cell


def test_queries_are_unique_across_tasks():
    queries = [task["query"] for task in _tasks()]
    assert len(queries) == len(set(queries))


# --- harness hook contracts -------------------------------------------------


class _ScriptedAgent:
    """Replays a fixed transcript so the episode runs without a model."""

    def __init__(self, turns: list[str]) -> None:
        self.turns = list(turns)
        self.seen_messages: list[list[dict[str, str]]] = []

    def generate(self, messages, tools):
        del tools
        self.seen_messages.append([dict(message) for message in messages])
        text = self.turns[min(len(self.seen_messages) - 1, len(self.turns) - 1)]
        return {
            "text": text,
            "input_tokens": 10,
            "tool_tokens": 5,
            "output_tokens": 3,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def _single_step_task() -> dict:
    slots = projection_authoring_slots()
    stratum_slot = next(
        slot for slot in slots if slot["projection_stratum"] == "qualifier_sibling"
    )
    return build_projection_task(stratum_slot, 0)


def _call_then_answer(task: dict) -> list[str]:
    step = task["executor_fixture"]["steps"][0]
    name = str(step["route_id"]).replace(".", "__", 1)
    arguments = {"material_id": step["argument_rules"]["material_id"]["eq"]}
    call = (
        "<tool_call>"
        + json.dumps({"name": name, "arguments": arguments})
        + "</tool_call>"
    )
    return [call, '{"answer":"done","facts":[],"sources":[]}']


def _tool_messages(agent: _ScriptedAgent) -> list[str]:
    return [
        message["content"]
        for transcript in agent.seen_messages
        for message in transcript
        if message["role"] == "tool"
    ]


def _run(condition: str) -> tuple[dict, _ScriptedAgent]:
    from scripts.agent_utility_generated_common import (
        FINAL_SYSTEM_PROMPT,
        build_extended_registry,
        run_generated_episode,
    )

    task = _single_step_task()
    agent = _ScriptedAgent(_call_then_answer(task))
    row = run_generated_episode(
        agent,
        build_extended_registry(100),
        task,
        condition,
        system_prompt=FINAL_SYSTEM_PROMPT,
        candidate_condition="ORACLE",
        observation_transform=lambda observation, step: project_observation(
            observation,
            condition=condition,
            planned_fields=step.get("planned_fields", ()),
            gold_fields=step.get("gold_fields", ()),
            field_contracts=step.get("field_contracts", {}),
        ),
    )
    return row, agent


def test_the_hook_actually_changes_what_the_agent_sees():
    _, raw_agent = _run("RAW-FULL")
    _, projected_agent = _run("PROJECTED")
    raw_text = "".join(_tool_messages(raw_agent))
    projected_text = "".join(_tool_messages(projected_agent))
    assert raw_text and projected_text
    assert "youngs_modulus_at_900k" in raw_text
    assert "youngs_modulus_at_900k" not in projected_text


def test_presentation_cannot_change_ground_truth():
    # The executor, task completion and route coverage must be identical across
    # conditions. If projection could change them, the answer-quality comparison
    # would be confounded by task success.
    rows = {condition: _run(condition)[0] for condition in PROJECTION_CONDITIONS}
    assert {row["task_complete"] for row in rows.values()} == {True}
    assert {row["required_route_call_coverage"] for row in rows.values()} == {1.0}
    assert {row["unauthorized_destructive_executions"] for row in rows.values()} == {0}
    attempts = {
        condition: json.dumps(row["attempts"], sort_keys=True)
        for condition, row in rows.items()
    }
    assert len(set(attempts.values())) == 1, "executor records diverged across conditions"


def test_candidate_exposure_is_identical_across_conditions():
    rows = {condition: _run(condition)[0] for condition in PROJECTION_CONDITIONS}
    histories = {json.dumps(row["candidate_history"]) for row in rows.values()}
    assert len(histories) == 1
    assert {row["candidate_condition"] for row in rows.values()} == {"ORACLE"}


def test_observation_chars_track_what_was_really_sent():
    rows = {condition: _run(condition)[0] for condition in PROJECTION_CONDITIONS}
    chars = {
        condition: sum(turn.get("observation_chars", 0) for turn in row["turn_rows"])
        for condition, row in rows.items()
    }
    assert chars["PROJECTED"] < chars["RAW-FULL"]
    assert chars["ORACLE-MINIMAL"] <= chars["PROJECTED"]
    assert chars["PROJECTED"] < chars["PROJECTED+CONTRACT"]


# --- aggregation contracts --------------------------------------------------


def _row(task: str, condition: str, catalog: int, recall: float, chars: int) -> dict:
    return {
        "semantic_task_id": task,
        "condition": condition,
        "catalog_size": catalog,
        "projection_stratum": "qualifier_sibling",
        "language": "en",
        "passed": True,
        "unauthorized_destructive_executions": 0,
        "contradiction_count": 0,
        "required_fact_recall": recall,
        "numeric_value_accuracy": recall,
        "unit_accuracy": recall,
        "provenance_accuracy": recall,
        "unsupported_fact_rate": 0.0,
        "final_envelope_valid": True,
        "exact_field_completion": True,
        "observation_chars": chars,
        "input_tokens": 100,
        "output_tokens": 10,
        "turns": 2,
    }


def _shard(rows: list[dict]) -> dict:
    return {
        "experiment": "0.14-output-field-projection",
        "tasks_sha256": "abc",
        "source_identity_sha256": "def",
        "candidate_condition": "SR-5",
        "runtime": {"runtime": "dev", "evidence_class": "development"},
        "rows": rows,
    }


def test_aggregate_pairs_conditions_within_a_task():
    from scripts.aggregate_agent_utility_v7_projection import aggregate

    rows = []
    for index in range(8):
        task = f"P{index:04d}"
        for catalog in (100, 250):
            rows.append(_row(task, "RAW-FULL", catalog, 0.5, 400))
            rows.append(_row(task, "PROJECTED", catalog, 0.9, 120))
            rows.append(_row(task, "PROJECTED+CONTRACT", catalog, 0.9, 160))
            rows.append(_row(task, "ORACLE-MINIMAL", catalog, 0.8, 90))

    result = aggregate([_shard(rows)])
    projected = result["conditions"]["PROJECTED"]
    delta = projected["paired_vs_raw_full"]["required_fact_recall"]
    assert delta["paired_tasks"] == 8, "catalog repeats must not inflate the sample"
    assert delta["mean_delta"] == pytest.approx(0.4)
    assert delta["ci_low"] <= delta["mean_delta"] <= delta["ci_high"]
    assert result["conditions"]["RAW-FULL"].get("paired_vs_raw_full") is None


def test_aggregate_rejects_a_duplicate_episode():
    from scripts.aggregate_agent_utility_v7_projection import aggregate

    duplicated = _row("P0000", "RAW-FULL", 100, 0.5, 400)
    with pytest.raises(SystemExit):
        aggregate([_shard([duplicated, dict(duplicated)])])


def test_aggregate_rejects_shards_from_different_corpora():
    from scripts.aggregate_agent_utility_v7_projection import aggregate

    left = _shard([_row("P0000", "RAW-FULL", 100, 0.5, 400)])
    right = _shard([_row("P0001", "RAW-FULL", 100, 0.5, 400)])
    right["tasks_sha256"] = "different"
    with pytest.raises(SystemExit):
        aggregate([left, right])


def test_aggregate_refuses_to_mix_development_and_confirmation_runtimes():
    from scripts.aggregate_agent_utility_v7_projection import aggregate

    dev = _shard([_row("P0000", "RAW-FULL", 100, 0.5, 400)])
    confirmation = _shard([_row("P0001", "RAW-FULL", 100, 0.5, 400)])
    confirmation["runtime"] = {"runtime": "confirmation", "evidence_class": "confirmation"}
    with pytest.raises(SystemExit):
        aggregate([dev, confirmation])


def test_aggregate_requires_every_condition():
    from scripts.aggregate_agent_utility_v7_projection import aggregate

    with pytest.raises(SystemExit):
        aggregate([_shard([_row("P0000", "RAW-FULL", 100, 0.5, 400)])])


# --- conveyor wiring --------------------------------------------------------


MAIN_SHA = "b" * 40


class _ConveyorAPI:
    """Minimal stub of the conveyor's GitHub surface.

    `present_paths` models a real checkout: the controller must not dispatch a
    stage against a revision whose tree lacks the experiment's own scripts.
    """

    def __init__(self, runs=None, b2_status=("queued", None), present_paths=None):
        from scripts.research_014_conveyor import PROJECTION_REQUIRED_PATHS

        self.runs_by_workflow = dict(runs or {})
        self.dispatched: list[tuple[str, dict]] = []
        self._b2_status = b2_status
        self._present = (
            set(PROJECTION_REQUIRED_PATHS) if present_paths is None else set(present_paths)
        )

    def workflow_runs(self, workflow_file):
        return self.runs_by_workflow.get(workflow_file, [])

    def dispatch(self, workflow_file, *, ref, inputs=None):
        del ref
        self.dispatched.append((workflow_file, dict(inputs or {})))

    def run(self, run_id):
        del run_id
        status, conclusion = self._b2_status
        return {
            "id": 1,
            "status": status,
            "conclusion": conclusion,
            "display_title": "b2",
            "created_at": "2026-09-30T00:00:00Z",
            "html_url": "",
            "run_attempt": 1,
            "head_sha": "a" * 40,
        }

    def ref_sha(self, ref):
        del ref
        return MAIN_SHA

    def path_exists(self, path, *, ref):
        del ref
        return path in self._present


def _run_row(run_id: int, title: str, conclusion: str | None) -> dict:
    return {
        "id": run_id,
        "status": "completed" if conclusion else "in_progress",
        "conclusion": conclusion,
        "display_title": title,
        "created_at": "2026-09-30T00:00:00Z",
        "html_url": "",
        "run_attempt": 1,
        "head_sha": "c" * 40,
    }


def test_the_dev_screen_is_dispatched_even_while_the_chain_waits_on_b2():
    # The development screen consumes no upstream artifact. If it were advanced
    # after the B2 gate, every early return would starve it indefinitely.
    from scripts.research_014_conveyor import (
        PROJECTION_DEV_WORKFLOW,
        run_controller,
    )

    api = _ConveyorAPI(b2_status=("queued", None))
    result = run_controller(api, ref="main", execute=True)

    assert result["state"] == "waiting_b2"
    assert [name for name, _ in api.dispatched] == [PROJECTION_DEV_WORKFLOW]
    assert any(
        action.startswith("dispatch_projection_dev:") for action in result["actions"]
    )


def test_the_dev_screen_is_dispatched_once_per_source_revision():
    from scripts.research_014_conveyor import PROJECTION_DEV_WORKFLOW, run_controller

    title = f"Research 0.14 Field Projection DEV source={MAIN_SHA}"
    api = _ConveyorAPI(
        runs={PROJECTION_DEV_WORKFLOW: [_run_row(10, title, None)]},
        b2_status=("queued", None),
    )
    run_controller(api, ref="main", execute=True)
    assert api.dispatched == []


def test_a_failed_dev_screen_is_retried_up_to_the_infrastructure_bound():
    from scripts.research_014_conveyor import (
        MAX_INFRA_ATTEMPTS,
        PROJECTION_DEV_WORKFLOW,
        advance_projection_dev,
    )

    title = f"Research 0.14 Field Projection DEV source={MAIN_SHA}"
    failures = [_run_row(20 + i, title, "failure") for i in range(MAX_INFRA_ATTEMPTS - 1)]
    api = _ConveyorAPI(runs={PROJECTION_DEV_WORKFLOW: failures})
    actions: list[str] = []
    advance_projection_dev(api, ref="main", execute=True, actions=actions)
    assert len(api.dispatched) == 1

    exhausted = [_run_row(30 + i, title, "failure") for i in range(MAX_INFRA_ATTEMPTS)]
    api = _ConveyorAPI(runs={PROJECTION_DEV_WORKFLOW: exhausted})
    actions = []
    advance_projection_dev(api, ref="main", execute=True, actions=actions)
    assert api.dispatched == []
    assert actions == ["stopped_projection_dev_infrastructure_failure_after_retries"]


# --- source freeze (review #508, blocking finding 1) ------------------------


def test_projection_never_reuses_the_frozen_chain_source():
    """`DOWNSTREAM_IMPLEMENTATION_SHA` predates every projection script.

    Dispatching a projection stage against it checks out a tree that cannot run
    the experiment. Stub-based tests cannot see that, so the rule is pinned
    directly: a projection dispatch must never carry that SHA.
    """
    from scripts.research_014_conveyor import (
        DOWNSTREAM_IMPLEMENTATION_SHA,
        advance_projection_confirmation,
        advance_projection_dev,
    )

    for advance in (
        lambda api, actions: advance_projection_dev(
            api, ref="main", execute=True, actions=actions
        ),
        lambda api, actions: advance_projection_confirmation(
            api, ref="main", execute=True, actions=actions, terminal_digest="sha256:t"
        ),
    ):
        api = _ConveyorAPI()
        actions: list[str] = []
        advance(api, actions)
        assert api.dispatched
        for _, inputs in api.dispatched:
            assert inputs["source_sha"] != DOWNSTREAM_IMPLEMENTATION_SHA
            assert inputs["source_sha"] == MAIN_SHA


def test_a_source_without_the_experiment_files_is_never_dispatched():
    # The exact failure mode review #508 caught: the stage would check out a
    # revision that does not contain its own scripts and die at run time.
    from scripts.research_014_conveyor import (
        PROJECTION_REQUIRED_PATHS,
        advance_projection_dev,
    )

    api = _ConveyorAPI(present_paths=set(PROJECTION_REQUIRED_PATHS[:-1]))
    actions: list[str] = []
    advance_projection_dev(api, ref="main", execute=True, actions=actions)
    assert api.dispatched == []
    assert actions and actions[0].startswith(
        "blocked_projection_source_missing_experiment_files:"
    )


def test_the_frozen_projection_source_is_not_moved_by_later_main_commits():
    from scripts.research_014_conveyor import (
        PROJECTION_DEV_WORKFLOW,
        PROJECTION_WORKFLOW,
        advance_projection_confirmation,
        frozen_projection_source,
    )

    first = "f" * 40
    title = f"Research 0.14 Field Projection DEV source={first}"
    api = _ConveyorAPI(runs={PROJECTION_DEV_WORKFLOW: [_run_row(50, title, "success")]})
    actions: list[str] = []

    # main has moved on to MAIN_SHA, but the freeze must hold.
    assert frozen_projection_source(api, ref="main", actions=actions) == first

    advance_projection_confirmation(
        api, ref="main", execute=True, actions=actions, terminal_digest="sha256:t"
    )
    assert api.dispatched == [
        (PROJECTION_WORKFLOW, {"evidence_digest": "sha256:t", "source_sha": first})
    ]


def test_both_arms_share_one_projection_source():
    from scripts.research_014_conveyor import (
        PROJECTION_DEV_WORKFLOW,
        advance_projection_confirmation,
        advance_projection_dev,
    )

    api = _ConveyorAPI()
    actions: list[str] = []
    advance_projection_dev(api, ref="main", execute=True, actions=actions)
    dev_source = api.dispatched[0][1]["source_sha"]

    # The DEV run now exists and fixes the freeze for confirmation.
    title = f"Research 0.14 Field Projection DEV source={dev_source}"
    api.runs_by_workflow[PROJECTION_DEV_WORKFLOW] = [_run_row(60, title, "success")]
    api.dispatched.clear()
    advance_projection_confirmation(
        api, ref="main", execute=True, actions=actions, terminal_digest="sha256:t"
    )
    assert api.dispatched[0][1]["source_sha"] == dev_source


def test_both_workflows_refuse_a_checkout_without_the_experiment():
    from pathlib import Path

    workflows = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    for name in (
        "research-0.14-field-projection-dev.yml",
        "research-0.14-field-projection.yml",
    ):
        text = (workflows / name).read_text(encoding="utf-8")
        assert "Refuse a source revision that cannot run this experiment" in text, name
        assert "scripts/evaluate_agent_utility_v7_projection.py" in text, name
        assert "raise SystemExit(1)" in text, name


# --- governance (review #508, finding 2) ------------------------------------


def test_the_preregistration_states_one_unambiguous_dev_rule():
    import json
    from pathlib import Path

    prereg = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "benchmarks"
            / "agent-utility-v7-field-projection-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    governance = prereg["dev_confirmation_governance"]
    assert governance["rule"] == "option_a_shared_frozen_corpus_dev_is_diagnostic_only"
    # Option A and "DEV may drive design changes" cannot both hold.
    assert governance["dev_may_inform_design"] is False
    for frozen in ("conditions", "the scorer", "thresholds and promotion gates"):
        assert frozen in governance["dev_results_may_not_change"]


def test_the_confirmation_arm_is_keyed_on_the_terminal_digest():
    from scripts.research_014_conveyor import (
        PROJECTION_WORKFLOW,
        advance_projection_confirmation,
    )

    api = _ConveyorAPI()
    actions: list[str] = []
    advance_projection_confirmation(
        api,
        ref="main",
        execute=True,
        actions=actions,
        terminal_digest="sha256:terminal",
    )
    assert api.dispatched == [
        (
            PROJECTION_WORKFLOW,
            {"evidence_digest": "sha256:terminal", "source_sha": MAIN_SHA},
        )
    ]

    # A second controller pass over the same terminal evidence must not
    # re-dispatch; duplicate stage dispatch for one identity is forbidden.
    title = f"Research 0.14 Field Projection sha256:terminal source={MAIN_SHA}"
    api = _ConveyorAPI(runs={PROJECTION_WORKFLOW: [_run_row(40, title, "success")]})
    actions = []
    advance_projection_confirmation(
        api,
        ref="main",
        execute=True,
        actions=actions,
        terminal_digest="sha256:terminal",
    )
    assert api.dispatched == []


def test_the_confirmation_workflow_does_not_compare_a_terminal_digest_to_b2():
    # The controller now passes the combined terminal digest. Comparing it to a
    # single stage artifact digest would fail every time, so that equality
    # assertion must not come back.
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "research-0.14-field-projection.yml"
    ).read_text(encoding="utf-8")
    assert 'matches[0]["digest"] == os.environ["EXPECTED_DIGEST"]' not in workflow
    assert 'assert run["conclusion"] == "success"' in workflow


def test_the_default_harness_path_is_unchanged():
    # Without the new keywords the episode must behave exactly as before: the
    # condition doubles as the routing condition and observations are untouched.
    from scripts.agent_utility_generated_common import (
        build_extended_registry,
        run_generated_episode,
    )

    task = _single_step_task()
    agent = _ScriptedAgent(_call_then_answer(task))
    row = run_generated_episode(agent, build_extended_registry(100), task, "ORACLE")
    assert row["condition"] == "ORACLE"
    assert row["candidate_condition"] == "ORACLE"
    assert "youngs_modulus_at_900k" in "".join(_tool_messages(agent))
