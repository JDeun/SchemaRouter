"""Scored workflow entrypoints are tested without model calls or approvals."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.external_validation.safeact_v1.run_plan import CONDITIONS
from scripts import launch_safeact_v1_scored_workflow as scored


def _argv(tmp_path: Path, *, extra: tuple[str, ...] = ()) -> list[str]:
    return [
        "scored-workflow",
        "--safeact-root", str(tmp_path / "safeact"),
        "--contracts", str(tmp_path / "contracts.json"),
        "--public-source-root", str(tmp_path / "public-sources"),
        "--manifest", str(tmp_path / "manifest.json"),
        "--model", "fixed-model",
        "--report", str(tmp_path / "readiness.json"),
        *extra,
    ]


def test_missing_review_and_contracts_never_run_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "argv", _argv(tmp_path))
    def must_not_run(*args, **kwargs):
        raise AssertionError("no model or process launch authorized")
    monkeypatch.setattr(scored.subprocess, "run", must_not_run)
    assert scored.main() == 0
    state = json.loads((tmp_path / "readiness.json").read_text())
    assert state["ready"] is False
    assert state["model_calls"] == 0
    assert any("reviewed contract" in item or "reviewed intervention" in item
               for item in state["blockers"])
    assert not (tmp_path / "scored.json").exists()


def test_dispatch_requires_independently_reviewed_readiness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, extra=("--require-ready",)))
    assert scored.main() == 2
    result = json.loads((tmp_path / "readiness.json").read_text())
    assert not result["ready"]


def test_untrusted_command_substitution_refused_even_if_manifest_signed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    official = tmp_path / "safeact"
    (official / ".git").mkdir(parents=True)
    (official / "agents").mkdir()
    (official / "agents" / "coding_cli_safeact_agent.py").write_text("# synthetic")
    public = tmp_path / "public-sources"
    public.mkdir()
    (tmp_path / "contracts.json").write_text('{"contracts":[]}')
    (tmp_path / "manifest.json").write_text(json.dumps({
        "conditions": {
            c: {
                "agent_command": "python3 /tmp/attacker-script.py --model fixed-model"
            }
            for c in CONDITIONS
        }
    }))
    monkeypatch.setattr(
        scored, "validate_launch",
        lambda **kwargs: pytest.fail("untrusted agent must not reach scoring"),
    )
    result, commands = scored.inspect(
        safeact_root=official, contracts_path=tmp_path / "contracts.json",
        source_root=public, manifest_path=tmp_path / "manifest.json",
        model="fixed-model",
    )
    assert not result["ready"]
    assert commands is None
    assert any("untrusted official host adapter" in b
               or "FileNotFoundError" in b for b in result["blockers"])


def test_scored_execute_fails_without_protected_runtime_authorization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "argv", _argv(tmp_path, extra=("--execute",)))
    monkeypatch.setattr(scored, "inspect", lambda **kw: (
        {"ready": True, "blockers": [], "model_calls": 0}, {
            c: "python3 safeact.py --model fixed-model" for c in CONDITIONS
        },
    ))
    monkeypatch.setenv("GITHUB_REF", "refs/heads/feature")
    monkeypatch.delenv("SAFEACT_V1_RUNTIME_VERIFIED", raising=False)
    def cannot_run(*args, **kwargs):
        raise AssertionError("no real agent may be invoked")
    monkeypatch.setattr(scored.subprocess, "run", cannot_run)
    assert scored.main() == 2
    result = json.loads((tmp_path / "readiness.json").read_text())
    assert len(result["blockers"]) == 2
    assert result["ready"] is False


def test_explicit_scoring_uses_reviewed_commands_only_on_trusted_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys, "argv",
        _argv(tmp_path, extra=(
            "--execute", "--scored-report", str(tmp_path / "scored.json")
        ))
    )
    commands = {
        c: f"python3 host_{i}.py --model fixed-model"
        for i, c in enumerate(CONDITIONS)
    }
    monkeypatch.setattr(scored, "inspect", lambda **kw: (
        {"ready": True, "blockers": [], "model_calls": 0}, commands
    ))
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("SAFEACT_V1_RUNTIME_VERIFIED", "1")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "conditions": {
            condition: {
                "agent_command_sha256": __import__("hashlib").sha256(
                    commands[condition].encode("utf-8")
                ).hexdigest(),
            }
            for condition in CONDITIONS
        },
    }))
    invoked = []
    def fake_run(argv, **kwargs):
        invoked.append(argv)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(scored.subprocess, "run", fake_run)
    assert scored.main() == 0
    assert len(invoked) == 1
    tokens = invoked[0]
    assert tokens[-1] == "--execute"
    assert tokens.count("--agent-cmd") == 0
    for command in commands.values():
        assert command in tokens
    assert "--report" in tokens
    assert str(tmp_path / "scored.json") in tokens
    assert str(tmp_path / "safeact-v1-expanded-runtime-manifest.json") in tokens
    runtime = json.loads(
        (tmp_path / "safeact-v1-expanded-runtime-manifest.json").read_text()
    )
    assert runtime["conditions"][CONDITIONS[0]]["reviewed_command_template_sha256"]


def test_portable_command_template_expands_only_verified_checkout_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    upstream = tmp_path / "safeact"
    official_agent = upstream / "agents" / "coding_cli_safeact_agent.py"
    official_agent.parent.mkdir(parents=True)
    official_agent.write_text("# synthetic official entrypoint")
    (upstream / ".git").mkdir()
    public = tmp_path / "public-sources"
    public.mkdir()
    (tmp_path / "contracts.json").write_text('{"contracts":[]}')
    import hashlib
    schema_root = Path(scored.__file__).resolve().parents[1]
    command_templates = {
        CONDITIONS[0]: (
            "python3 @SAFEACT_ROOT@/agents/coding_cli_safeact_agent.py "
            "--backend codex --model fixed-model --strategy baseline"
        ),
        CONDITIONS[1]: (
            "python3 @SCHEMAROUTER_ROOT@/examples/external_validation/"
            "safeact_v1/official_routing_hook.py --condition routing_only "
            "--backend codex --model fixed-model --strategy baseline"
        ),
        CONDITIONS[2]: (
            "python3 @SCHEMAROUTER_ROOT@/examples/external_validation/"
            "safeact_v1/official_agent_hook.py --condition evidence_gate "
            "--backend codex --model fixed-model --strategy baseline"
        ),
    }
    manifest = {
        "conditions": {
            k: {
                "agent_command": v,
                "agent_command_sha256": hashlib.sha256(v.encode()).hexdigest(),
            }
            for k, v in command_templates.items()
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    observed = []
    def fake_validation(**kwargs):
        observed.append(kwargs)
    monkeypatch.setattr(scored, "validate_launch", fake_validation)
    state, commands = scored.inspect(
        safeact_root=upstream,
        contracts_path=tmp_path / "contracts.json",
        source_root=public,
        manifest_path=tmp_path / "manifest.json",
        model="fixed-model",
    )
    assert state["ready"] is True
    assert len(observed) == 1
    assert "@SAFEACT_ROOT@" not in commands[CONDITIONS[0]]
    assert str(upstream) in commands[CONDITIONS[0]]
    assert str(schema_root) in commands[CONDITIONS[1]]
    for condition in CONDITIONS:
        assert observed[0]["intervention_manifest"]["conditions"][condition][
            "reviewed_command_template_sha256"
        ] == hashlib.sha256(command_templates[condition].encode()).hexdigest()


def test_portable_command_template_rejects_digest_tampering(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    upstream = tmp_path / "safeact"
    (upstream / ".git").mkdir(parents=True)
    (tmp_path / "public").mkdir()
    (tmp_path / "contracts.json").write_text('{"contracts":[]}')
    commands = {
        c: "python3 @SAFEACT_ROOT@/agents/coding_cli_safeact_agent.py"
        for c in CONDITIONS
    }
    manifest = {"conditions": {
        c: {"agent_command": commands[c], "agent_command_sha256": "0" * 64}
        for c in CONDITIONS
    }}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    state, cmd = scored.inspect(
        safeact_root=upstream,
        contracts_path=tmp_path / "contracts.json",
        source_root=tmp_path / "public",
        manifest_path=tmp_path / "manifest.json",
        model="fixed-model",
    )
    assert not state["ready"]
    assert cmd is None
    assert any("template digest mismatch" in item for item in state["blockers"])
