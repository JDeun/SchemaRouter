"""SafeAct V1 official batch-CLI plan contract tests."""
from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from examples.external_validation.safeact_v1.run_plan import (
    CONDITIONS,
    V1RunPlan,
    validate_comparison_matrix,
)


@pytest.mark.parametrize("condition", CONDITIONS)
def test_each_condition_uses_official_v1_and_distinct_output(condition: str) -> None:
    plan = V1RunPlan(
        condition=condition,
        safeact_root=Path("/tmp/safeact"),
        model="frozen-model-id",
        agent_command="python3 ../../../trusted_agent.py",
    )
    argv = plan.argv()
    assert argv[:4] == (
        sys.executable,
        "/tmp/safeact/run_benchmark.py",
        "--protocol",
        "v1",
    )
    assert argv[4:6] == ("--agent-cmd", "python3 ../../../trusted_agent.py")
    assert argv[6] == "--output-dir"
    assert argv[7] == str(Path("/tmp/safeact/output") / condition.lower())
    assert "--simulate" not in argv
    assert "--allow-shell" not in argv


def test_three_output_directories_cannot_overlap() -> None:
    outputs = {
        V1RunPlan(c, Path("/tmp/safeact"), "model", "python3 agent.py").argv()[-1]
        for c in CONDITIONS
    }
    assert len(outputs) == 3


@pytest.mark.parametrize("bad_condition", ["SAFEACT-V2", "", "UNGATED"])
def test_unregistered_condition_is_rejected(bad_condition: str) -> None:
    with pytest.raises(ValueError, match="unknown preregistered condition"):
        V1RunPlan(bad_condition, Path("."), "model", "python3 agent.py")


@pytest.mark.parametrize(
    ("model", "agent"),
    [("", "python3 agent.py"), ("model", ""), (" ", "python3 agent.py")],
)
def test_missing_model_or_agent_is_rejected(model: str, agent: str) -> None:
    with pytest.raises(ValueError, match="model and external agent command required"):
        V1RunPlan(CONDITIONS[0], Path("."), model, agent)


def test_agent_command_remains_one_argument() -> None:
    command = "python3 my_agent.py --model 'frozen model'"
    plan = V1RunPlan(CONDITIONS[0], Path("."), "frozen model", command)
    assert plan.argv()[5] == command
    assert shlex.split(plan.command_string()) == list(plan.argv())


def _matrix() -> list[V1RunPlan]:
    return [
        V1RunPlan(
            condition=condition,
            safeact_root=Path("/tmp/safeact"),
            model="frozen-model-id",
            agent_command=f"python3 ../../../agent_{index}.py",
        )
        for index, condition in enumerate(CONDITIONS)
    ]


def test_comparison_matrix_requires_every_condition_once() -> None:
    plans = _matrix()
    assert tuple(item.condition for item in validate_comparison_matrix(plans[::-1])) == CONDITIONS
    with pytest.raises(ValueError, match="duplicate experiment condition"):
        validate_comparison_matrix([plans[0], plans[0], plans[2]])
    with pytest.raises(ValueError, match="all three"):
        validate_comparison_matrix(plans[:2])


def test_comparison_matrix_rejects_model_drift() -> None:
    plans = _matrix()
    plans[1] = V1RunPlan(
        plans[1].condition,
        plans[1].safeact_root,
        "different-model",
        plans[1].agent_command,
    )
    with pytest.raises(ValueError, match="one declared model"):
        validate_comparison_matrix(plans)


def test_comparison_matrix_rejects_different_upstream_checkouts() -> None:
    plans = _matrix()
    plans[2] = V1RunPlan(
        plans[2].condition,
        Path("/tmp/not-the-frozen-safeact"),
        plans[2].model,
        plans[2].agent_command,
    )
    with pytest.raises(ValueError, match="one pinned SafeAct checkout"):
        validate_comparison_matrix(plans)


def test_absolute_official_runner_path_does_not_depend_on_calling_cwd() -> None:
    plan = _matrix()[0]
    assert plan.argv()[1] == "/tmp/safeact/run_benchmark.py"
    assert plan.argv()[0] == sys.executable
