"""Branch-level safety regressions for fixed5 paper plan disclosure."""
from types import SimpleNamespace
import pytest
from schemarouter import PolicyViolationError
from scripts import research_paper_fixed5_menu_e0 as module


class View:
    def __init__(self):
        self.witness = ("opaque", 7)
        self.visible_route_ids = ("a.run", "b.run")
        self.calls = 0
    def assert_source_unchanged(self):
        self.calls += 1
    def tool_definitions(self, routes, *, k):
        assert k == 5
        assert routes == ["a.run"]


class Plan:
    def __init__(self, status, calls=(), bindings=(), executable_authority=False):
        self.status = status
        self.calls = calls
        self.bindings = bindings
        self.executable_authority = executable_authority
        self.requested_k = 5
        self.registry_version = 7


def receipt(route="a.run", tool="tool", schema="schema"):
    return SimpleNamespace(
        route_id=route,
        call=SimpleNamespace(tool_fingerprint=tool, schema_fingerprint=schema),
    )


@pytest.fixture(autouse=True)
def isolated_contract(monkeypatch):
    monkeypatch.setattr(module, "AuthorizedAgentToolSurface", View)
    monkeypatch.setattr(module, "PaperTypedToolPlan", Plan)
    monkeypatch.setattr(module, "_visible_fingerprints",
                        lambda view: {"a.run": ("tool", "schema"),
                                      "b.run": ("other", "schema")})


def test_ready_direct_receipt_reuses_current_source_menu():
    view = View()
    assert module.paper_plan_fixed5_menu(view, Plan("ready", (receipt(),))) == ["a.run"]
    assert view.calls >= 2


@pytest.mark.parametrize("status", [
    "no_proven_hit", "over_k_unranked", "budget_unsatisfied", "ambiguous_paths",
])
def test_abstention_does_not_disclose_routes(status):
    assert module.paper_plan_fixed5_menu(View(), Plan(status)) == []


def test_observation_dependency_never_flattens():
    assert module.paper_plan_fixed5_menu(
        View(), Plan("requires_observation", (receipt(),), (object(),)),
    ) == []


@pytest.mark.parametrize("plan", [
    Plan("ready", (receipt("hidden.run"),)),
    Plan("ready", (receipt("a.run", "forged", "schema"),)),
    Plan("ready", (receipt(), receipt())),
    Plan("ready", (receipt(),), executable_authority=True),
    Plan("requires_observation", (receipt(),)),
    Plan("no_proven_hit", (receipt(),)),
    Plan("ready", (receipt(),), (object(),)),
])
def test_invalid_or_executable_receipts_fail_closed(plan):
    with pytest.raises(PolicyViolationError):
        module.paper_plan_fixed5_menu(View(), plan)


def test_registry_version_mismatch_rejected():
    plan = Plan("ready", (receipt(),))
    plan.registry_version = 8
    with pytest.raises(PolicyViolationError):
        module.paper_plan_fixed5_menu(View(), plan)
