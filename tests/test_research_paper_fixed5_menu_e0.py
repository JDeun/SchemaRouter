"""Paper plan to existing fixed5 menu must never grant authority."""
import pytest
from scripts.research_paper_fixed5_menu_e0 import paper_plan_fixed5_menu


def test_rejects_unscoped_view():
    with pytest.raises(ValueError, match="principal-scoped"):
        paper_plan_fixed5_menu(None, None)


def test_menu_adapter_has_no_model_or_invoker_parameter():
    import inspect
    parameters = inspect.signature(paper_plan_fixed5_menu).parameters
    assert tuple(parameters) == ("view", "plan")
