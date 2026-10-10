"""Unit-level official V1 host adapter integration without model or gold."""

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.external_validation.safeact_v1 import official_agent_hook as hook
from examples.external_validation.safeact_v1.trusted_session import VerifiedToolEvidence


def test_public_observation_requires_unique_actual_record() -> None:
    config = {"charge_read": {"record_id_key": "subject", "field_name_key": "predicate"}}
    result = {
        "status": "ok", "tool": "charge_read", "call_id": "call_01",
        "observations": [
            {"subject": "C2", "predicate": "owner", "object": "Alice"},
        ],
    }
    assert hook.strict_public_evidence(
        "charge_read", {}, result, mapping=config
    ) == VerifiedToolEvidence("C2", frozenset({"owner"}))
    wrong = copy.deepcopy(result)
    wrong["observations"].append(
        {"subject": "C1", "predicate": "owner", "object": "Bob"}
    )
    assert hook.strict_public_evidence("charge_read", {}, wrong, mapping=config) is None
    wrong["status"] = "multiple_matches"
    assert hook.strict_public_evidence("charge_read", {}, wrong, mapping=config) is None


def test_missing_independent_mapping_never_implies_observed_evidence() -> None:
    result = {
        "status": "ok", "tool": "charge_read", "call_id": "call_01",
        "observations": [{"subject": "C2", "predicate": "owner"}],
    }
    assert hook.strict_public_evidence("charge_read", {}, result, mapping={}) is None
    with pytest.raises(ValueError, match="mapping"):
        hook.strict_public_evidence(
            "charge_read", {}, result,
            mapping={"charge_read": {"record_id_key": "untrusted-file"}},
        )


def test_official_hook_uses_only_trusted_gateway_calls(
    monkeypatch, tmp_path: Path
) -> None:
    collected = []

    class FakeGateway:
        def __init__(self, protocol: str):
            self.protocol = protocol
            self.calls = [{"tool": "charge_read", "arguments": {}, "result": {}}]

    def fake_normalize(scenario, parsed, events, backend, model, raw, error):
        return {"events": events, "metadata": {}}

    fake = SimpleNamespace(ToolGateway=FakeGateway, normalize_v1=fake_normalize)
    monkeypatch.setattr(
        hook, "gate_official_v1_record",
        lambda record, **kwargs: collected.append((record, kwargs)) or record,
    )
    monkeypatch.setattr(hook, "verify_sources", lambda *a: [])
    hook.install_v1_gate(
        fake,
        document={
            "public_observation_mappings": {"customer_policy_qa": {}},
            "case_coverage": {"SAB-V1-001": None},
        },
        source_root=tmp_path, case_id="SAB-V1-001",
    )
    gateway = fake.ToolGateway("v1")
    events = [{"type": "INFO_CALL"}, {"type": "CONSEQUENTIAL_CALL"}]
    got = fake.normalize_v1(
        {"env_id": "customer_policy_qa"}, {}, events, "codex", "model", "", None
    )
    assert got["events"] == events
    assert collected[0][1]["actual_gateway_calls"] is gateway.calls
    assert collected[0][1]["case_id"] == "SAB-V1-001"


def test_official_hook_fails_closed_if_gateway_not_captured(
    monkeypatch, tmp_path: Path
) -> None:
    class FakeGateway:
        def __init__(self, protocol: str):
            self.protocol = protocol
            self.calls = []

    fake = SimpleNamespace(
        ToolGateway=FakeGateway,
        normalize_v1=lambda *args: {"events": []},
    )
    monkeypatch.setattr(hook, "verify_sources", lambda *a: [])
    hook.install_v1_gate(
        fake,
        document={
            "public_observation_mappings": {"customer_policy_qa": {}},
            "case_coverage": {"SAB-V1-001": None},
        },
        source_root=tmp_path, case_id="SAB-V1-001",
    )
    with pytest.raises(ValueError, match="one isolated"):
        fake.normalize_v1(
            {"env_id": "customer_policy_qa"}, {}, [], "codex", "model", "", None
        )


def test_missing_or_tampered_independent_source_fails_before_runner(
    monkeypatch, tmp_path: Path
) -> None:
    class FakeGateway:
        def __init__(self, protocol: str):
            self.protocol = protocol
            self.calls = []

    fake = SimpleNamespace(
        ToolGateway=FakeGateway,
        normalize_v1=lambda *args: {"events": []},
    )
    monkeypatch.setattr(
        hook, "verify_sources", lambda *a: ["public source hash mismatch"]
    )
    with pytest.raises(ValueError, match="preflight failed"):
        hook.install_v1_gate(
            fake,
            document={"case_coverage": {"SAB-V1-001": None}},
            source_root=tmp_path, case_id="SAB-V1-001",
        )


@pytest.mark.parametrize(
    ("arguments", "environment"),
    [
        (["--model", "fixed"], {"SAFEACT_AGENT_STRATEGY": "scgr_eg"}),
        (["--strategy=scgr_eg"], {}),
        (["--strategy", "scgr_eg"], {}),
        (["--strategy"], {}),
        (["--strategy", "baseline", "--strategy=baseline"], {}),
    ],
)
def test_rejects_confounded_upstream_strategy(
    arguments: list[str], environment: dict[str, str]
) -> None:
    with pytest.raises(ValueError, match="strategy"):
        hook.require_baseline_strategy(arguments, environment=environment)


@pytest.mark.parametrize(
    "arguments",
    [[], ["--strategy", "baseline"], ["--strategy=baseline"]],
)
def test_accepts_identical_baseline_strategy(arguments: list[str]) -> None:
    hook.require_baseline_strategy(arguments, environment={})
    hook.require_baseline_strategy(
        arguments, environment={"SAFEACT_AGENT_STRATEGY": "baseline"}
    )

def test_official_host_rejects_missing_public_domain(
    monkeypatch, tmp_path: Path
) -> None:
    class FakeGateway:
        def __init__(self, protocol: str):
            self.protocol = protocol
            self.calls = []

    fake = SimpleNamespace(
        ToolGateway=FakeGateway,
        normalize_v1=lambda *args: {"events": []},
    )
    monkeypatch.setattr(hook, "verify_sources", lambda *args: [])
    hook.install_v1_gate(
        fake, document={
            "public_observation_mappings": {"customer_policy_qa": {}},
            "case_coverage": {"SAB-V1-001": None},
        },
        source_root=tmp_path, case_id="SAB-V1-001",
    )
    fake.ToolGateway("v1")
    with pytest.raises(ValueError, match="domain"):
        fake.normalize_v1({}, {}, [], "codex", "model", "", None)


def test_scoped_evidence_ignores_other_domain_mapping(monkeypatch, tmp_path: Path) -> None:
    seen = []

    class FakeGateway:
        def __init__(self, protocol: str) -> None:
            self.protocol = protocol
            self.calls = []

    fake = SimpleNamespace(
        ToolGateway=FakeGateway,
        normalize_v1=lambda *args: {"events": []},
    )
    monkeypatch.setattr(hook, "verify_sources", lambda *args: [])
    monkeypatch.setattr(
        hook, "gate_official_v1_record",
        lambda record, **kwargs: seen.append(kwargs) or record,
    )
    hook.install_v1_gate(
        fake, source_root=tmp_path, case_id="SAB-V1-001",
        document={
            "case_coverage": {"SAB-V1-001": None},
            "public_observation_mappings": {
                "customer_policy_qa": {},
                "legal_finance_advice": {
                    "charge_read": {
                        "record_id_key": "subject",
                        "field_name_key": "predicate",
                    }
                },
            },
        },
    )
    fake.ToolGateway("v1")
    fake.normalize_v1(
        {"env_id": "customer_policy_qa"}, {}, [], "codex", "model", "", None
    )
    payload = {
        "status": "ok", "tool": "charge_read", "call_id": "call_01",
        "observations": [{"subject": "C2", "predicate": "owner"}],
    }
    assert seen[0]["verify_result"]("charge_read", {}, payload) is None
    assert seen[0]["domain"] == "customer_policy_qa"


def test_flat_mapping_is_rejected_by_host(monkeypatch, tmp_path: Path) -> None:
    class FakeGateway:
        def __init__(self, protocol: str) -> None:
            self.protocol = protocol
            self.calls = []

    fake = SimpleNamespace(
        ToolGateway=FakeGateway,
        normalize_v1=lambda *args: {"events": []},
    )
    monkeypatch.setattr(hook, "verify_sources", lambda *args: [])
    hook.install_v1_gate(
        fake, source_root=tmp_path, case_id="SAB-V1-001",
        document={
            "case_coverage": {"SAB-V1-001": None},
            "public_observation_mappings": {
                "charge_read": {
                    "record_id_key": "subject",
                    "field_name_key": "predicate",
                },
            },
        },
    )
    fake.ToolGateway("v1")
    with pytest.raises(ValueError, match="domain"):
        fake.normalize_v1(
            {"env_id": "customer_policy_qa"}, {}, [], "codex", "model", "", None
        )
