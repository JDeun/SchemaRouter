"""Safe boundary tests for the opt-in scoped model/plan adapter."""
import pytest

from scripts.research_paper_scoped_plan_e0 import analyze_and_plan_paper_scoped_e0

@pytest.mark.asyncio
async def test_rejects_unscoped_view_before_model_invocation():
    calls = []
    def model(payload):
        calls.append(payload)
        return {}
    with pytest.raises(ValueError, match="principal-scoped"):
        await analyze_and_plan_paper_scoped_e0(
            model, view=None, catalog=None, intent_registry=None,
            index=None, model_visible_intent_ids=(), model_visible_concept_ids=(),
        )
    assert calls == []

def test_async_entrypoint_not_an_executor():
    import inspect
    assert inspect.iscoroutinefunction(analyze_and_plan_paper_scoped_e0)
