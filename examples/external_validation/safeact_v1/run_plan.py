"""SafeAct V1 command plan: only official evaluator scores trajectories.

This plan deliberately does not load any gold case_spec into an agent process.
The same model and frozen benchmark must be used across conditions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

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
            "python", "run_benchmark.py",
            "--protocol", "v1",
            "--agent-cmd", self.agent_command,
        )

    def command_string(self) -> str:
        return shlex.join(self.argv())
