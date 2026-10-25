"""A5 async vertical slice: verify callback ordering and fail-closed boundaries."""
import pytest

from scripts import research_paper_scoped_agent_episode_e0 as module


class View:
    original_query = "bounded question"

    def __init__(self):
        self.events = []

    def assert_source_unchanged(self):
        self.events.append("check")


@pytest.fixture(autouse=True)
def scoped_view_contract(monkeypatch):
    monkeypatch.setattr(module, "AuthorizedAgentToolSurface", View)


@pytest.mark.asyncio
async def test_model_then_existing_episode_in_order(monkeypatch):
    view = View()
    plan = object()

    async def analyze(model, **kwargs):
        view.events.append("understand")
        assert kwargs["view"] is view
        return "offer", plan

    def episode(agent, **kwargs):
        view.events.append("episode")
        assert kwargs["plan"] is plan
        assert kwargs["view"] is view
        return {"outcome": "bounded"}

    monkeypatch.setattr(module, "analyze_and_plan_paper_scoped_e0", analyze)
    monkeypatch.setattr(module, "run_paper_fixed5_episode_e0", episode)
    result = await module.run_paper_scoped_agent_episode_e0(
        lambda _: {}, object(), view=view, task={"query": view.original_query},
        catalog=None, intent_registry=None, index=None,
        model_visible_intent_ids=(), model_visible_concept_ids=(),
    )
    assert result == ("offer", {"outcome": "bounded"})
    assert view.events == ["check", "understand", "check", "episode", "check"]


@pytest.mark.asyncio
async def test_source_drift_after_understand_prevents_episode(monkeypatch):
    view = View()
    calls = []

    async def analyze(model, **kwargs):
        view.assert_source_unchanged = lambda: (_ for _ in ()).throw(
            RuntimeError("source changed")
        )
        return "offer", object()

    monkeypatch.setattr(module, "analyze_and_plan_paper_scoped_e0", analyze)
    monkeypatch.setattr(
        module, "run_paper_fixed5_episode_e0", lambda *args, **kwargs: calls.append(1),
    )
    with pytest.raises(RuntimeError, match="source changed"):
        await module.run_paper_scoped_agent_episode_e0(
            lambda _: {}, object(), view=view, task={"query": view.original_query},
            catalog=None, intent_registry=None, index=None,
            model_visible_intent_ids=(), model_visible_concept_ids=(),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_query_mismatch_rejected_before_model(monkeypatch):
    calls = []
    monkeypatch.setattr(
        module, "analyze_and_plan_paper_scoped_e0",
        lambda *args, **kwargs: calls.append(1),
    )
    with pytest.raises(ValueError, match="task/query"):
        await module.run_paper_scoped_agent_episode_e0(
            lambda _: {}, object(), view=View(), task={"query": "different"},
            catalog=None, intent_registry=None, index=None,
            model_visible_intent_ids=(), model_visible_concept_ids=(),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_empty_source_plan_reaches_host_terminal_without_agent(monkeypatch):
    view = View()
    calls = []

    async def analyze(model, **kwargs):
        calls.append("understand")
        return "abstain", None

    def episode(agent, **kwargs):
        calls.append("existing_executor")
        assert kwargs["plan"] is None
        return {"final_text": "REQUEST_MORE_TOOLS", "turns": []}

    monkeypatch.setattr(module, "analyze_and_plan_paper_scoped_e0", analyze)
    monkeypatch.setattr(module, "run_paper_fixed5_episode_e0", episode)
    decision, result = await module.run_paper_scoped_agent_episode_e0(
        lambda _: {}, object(), view=view, task={"query": view.original_query},
        catalog=None, intent_registry=None, index=None,
        model_visible_intent_ids=(), model_visible_concept_ids=(),
    )
    assert decision == "abstain"
    assert result["final_text"] == "REQUEST_MORE_TOOLS"
    assert calls == ["understand", "existing_executor"]


@pytest.mark.asyncio
async def test_model_analysis_failure_never_reaches_executor(monkeypatch):
    view = View()
    calls = []

    async def analyze(model, **kwargs):
        raise ValueError("invalid model response")

    monkeypatch.setattr(module, "analyze_and_plan_paper_scoped_e0", analyze)
    monkeypatch.setattr(
        module, "run_paper_fixed5_episode_e0",
        lambda *args, **kwargs: calls.append("executor"),
    )
    with pytest.raises(ValueError, match="invalid model response"):
        await module.run_paper_scoped_agent_episode_e0(
            lambda _: {}, object(), view=view, task={"query": view.original_query},
            catalog=None, intent_registry=None, index=None,
            model_visible_intent_ids=(), model_visible_concept_ids=(),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_source_drift_during_episode_rejects_result(monkeypatch):
    view = View()

    async def analyze(model, **kwargs):
        return "offer", object()

    def episode(agent, **kwargs):
        view.assert_source_unchanged = lambda: (_ for _ in ()).throw(
            RuntimeError("post-episode source drift")
        )
        return {"outcome": "untrusted"}

    monkeypatch.setattr(module, "analyze_and_plan_paper_scoped_e0", analyze)
    monkeypatch.setattr(module, "run_paper_fixed5_episode_e0", episode)
    with pytest.raises(RuntimeError, match="post-episode source drift"):
        await module.run_paper_scoped_agent_episode_e0(
            lambda _: {}, object(), view=view, task={"query": view.original_query},
            catalog=None, intent_registry=None, index=None,
            model_visible_intent_ids=(), model_visible_concept_ids=(),
        )
