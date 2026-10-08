"""SafeAct V1 official batch-CLI plan contract tests."""
from __future__ import annotations

import shlex
from pathlib import Path

import pytest

from examples.external_validation.safeact_v1.run_plan import CONDITIONS, V1RunPlan


@pytest.mark.parametrize("condition", CONDITIONS)
def test_each_condition_uses_official_v1_and_distinct_output(condition: str) -> None:
    plan = V1RunPlan(
        condition=condition,
        safeact_root=Path("/tmp/safeact"),
        model="frozen-model-id",
        agent_command="python3 ../../../trusted_agent.py",
    )
    argv = plan.argv()
    assert argv[:4] == ("python", "run_benchmark.py", "--protocol", "v1")
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
