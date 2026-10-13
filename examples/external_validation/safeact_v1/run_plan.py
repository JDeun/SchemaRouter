"""SafeAct V1 command plan: only official evaluator scores trajectories.

This plan deliberately does not load any gold case_spec into an agent process.
The same model and frozen benchmark must be used across conditions.
"""
from __future__ import annotations

import shlex
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

CONDITIONS = (
    "SAFEACT-UNGATED",
    "SAFEACT-SCHEMAROUTER-NO-EVIDENCE-GATE",
    "SAFEACT-SCHEMAROUTER-EVIDENCE-GATE",
)


@dataclass(frozen=True)
class V1RunPlan:
    condition: str
    safeact_root: Path
    model: str
    agent_command: str

    def __post_init__(self) -> None:
        if self.condition not in CONDITIONS:
            raise ValueError("unknown preregistered condition")
        if not self.model.strip() or not self.agent_command.strip():
            raise ValueError("model and external agent command required")

    def argv(self) -> tuple[str, ...]:
        """SafeAct's batch runner controls workspace and post-run evaluator."""
        return (
            sys.executable, str(self.safeact_root.resolve() / "run_benchmark.py"),
            "--protocol", "v1",
            "--agent-cmd", self.agent_command,
            "--output-dir", str(self.safeact_root.resolve() / "output" / self.condition.lower()),
        )

    def command_string(self) -> str:
        return shlex.join(self.argv())


def validate_comparison_matrix(plans: Sequence[V1RunPlan]) -> tuple[V1RunPlan, ...]:
    """Freeze exactly one three-arm comparison under one model and checkout.

    This validates *declared* model identity. The trusted agent adapter must
    separately attest the model it actually ran for each official task.
    """
    if len(plans) != len(CONDITIONS):
        raise ValueError("all three preregistered conditions are required")
    by_condition: dict[str, V1RunPlan] = {}
    for plan in plans:
        if plan.condition in by_condition:
            raise ValueError("duplicate experiment condition")
        by_condition[plan.condition] = plan
    if set(by_condition) != set(CONDITIONS):
        raise ValueError("experiment must cover all preregistered conditions")
    ordered = tuple(by_condition[condition] for condition in CONDITIONS)
    if len({plan.model for plan in ordered}) != 1:
        raise ValueError("comparison must freeze one declared model")
    if len({plan.safeact_root.resolve() for plan in ordered}) != 1:
        raise ValueError("comparison must use one pinned SafeAct checkout")
    outputs = {plan.argv()[-1] for plan in ordered}
    if len(outputs) != len(CONDITIONS):
        raise ValueError("comparison output paths must not overlap")
    return ordered
