"""Isolated adapter rejects invalid scope before invoking the agent."""
import pytest
from scripts.research_paper_fixed5_episode_e0 import run_paper_fixed5_episode_e0


def test_episode_rejects_unscoped_view():
    with pytest.raises(ValueError, match="scoped source view"):
        run_paper_fixed5_episode_e0(object(), view=None, task={}, plan=None)


def test_episode_uses_only_existing_executor():
    import inspect

    from scripts import research_paper_fixed5_episode_e0 as module

    assert module.run_generated_episode.__module__ == "scripts.agent_utility_generated_common"
    assert tuple(inspect.signature(run_paper_fixed5_episode_e0).parameters) == (
        "agent", "view", "task", "plan",
    )
