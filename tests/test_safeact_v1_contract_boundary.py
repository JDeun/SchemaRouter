"""Regression tests for provenance path escape attempts."""
from __future__ import annotations

import importlib.util
from pathlib import Path

script = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "validate_safeact_v1_contract_provenance.py"
)
spec = importlib.util.spec_from_file_location("safeact_provenance", script)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_gold_manifest_source_is_rejected() -> None:
    for path in ("env/case_manifest.json", "env/case_provenance.json", "data/safeact/cases.json"):
        doc = {
            "contracts": [
                {"action": "act", "sources": [{"kind": "public_policy", "path": path}]}
            ]
        }
        assert module.validate(doc), path


def test_missing_contract_sources_are_rejected() -> None:
    assert module.validate({"contracts": [{"action": "act", "sources": []}]})


def test_unknown_source_kind_is_rejected() -> None:
    doc = {
        "contracts": [
            {"action": "act", "sources": [{"kind": "evaluator_gold", "path": "gold.json"}]}
        ]
    }
    assert module.validate(doc)
