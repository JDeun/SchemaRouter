"""Manifest authoring is tested without approving contracts or calling models."""

import hashlib
import json

import pytest

from examples.external_validation.safeact_v1.run_plan import CONDITIONS
from scripts.prepare_safeact_v1_scored_manifest import (
    build_unreviewed_manifest,
    canonical_digest,
)


def _draft() -> dict:
    return {
        "contracts": [
            {
                "action": "synthetic_tool",
                "sources": [{"kind": "independent_contract", "path": "policy.txt"}],
            }
        ],
        "case_coverage": {"SAB-V1-001": "synthetic_tool"},
    }


def test_manifest_fixes_all_three_official_entrypoints_without_approval() -> None:
    contract = _draft()
    manifest = build_unreviewed_manifest(
        contract,
        model="fixed-scoring-model",
        backend="codex",
        adapter_commit="a" * 40,
    )
    assert manifest["reviewed"] is False
    assert manifest["independent_contract_review"]["approved"] is False
    assert manifest["independent_contract_review"]["author"] == ""
    assert manifest["independent_contract_review"]["reviewer"] == ""
    assert manifest["contract_sha256"] == canonical_digest(contract)
    assert set(manifest["conditions"]) == set(CONDITIONS)
    rows = [manifest["conditions"][key] for key in CONDITIONS]
    assert [row["mode"] for row in rows] == [
        "ungated", "routing_only", "evidence_gate"
    ]
    assert all("--backend codex" in row["agent_command"] for row in rows)
    assert all("--model fixed-scoring-model" in row["agent_command"] for row in rows)
    assert all("--strategy baseline" in row["agent_command"] for row in rows)
    assert "coding_cli_safeact_agent.py" in rows[0]["agent_command"]
    assert "official_routing_hook.py" in rows[1]["agent_command"]
    assert "official_agent_hook.py" in rows[2]["agent_command"]
    assert "--contract-sha256 " + canonical_digest(contract) in rows[2]["agent_command"]
    for row in rows:
        assert row["agent_command_sha256"] == hashlib.sha256(
            row["agent_command"].encode("utf-8")
        ).hexdigest()


@pytest.mark.parametrize(
    ("model", "backend", "commit", "message"),
    [
        ("", "codex", "a" * 40, "model"),
        ("bad\nmodel", "codex", "a" * 40, "model"),
        ("m", "bad-backend", "a" * 40, "backend"),
        ("m", "claude", "not-a-commit", "commit"),
    ],
)
def test_draft_rejects_invalid_identity(model, backend, commit, message) -> None:
    with pytest.raises(ValueError, match=message):
        build_unreviewed_manifest(
            _draft(), model=model, backend=backend,
            adapter_commit=commit,
        )


def test_manifest_sha_is_canonical_key_order_insensitive() -> None:
    data = _draft()
    reversed_document = dict(reversed(list(data.items())))
    assert canonical_digest(data) == canonical_digest(reversed_document)
    assert build_unreviewed_manifest(
        data, model="m", backend="claude", adapter_commit="a" * 40
    )["contract_sha256"] == canonical_digest(data)
    assert json.loads(json.dumps(data)) == data
