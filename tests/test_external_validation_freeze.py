from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_external_validation_freeze.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "validate_external_validation_freeze",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load external validation freeze validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEMPLATE = ROOT / "benchmarks" / "external-validation-freeze-manifest.template.json"


def frozen_manifest() -> dict:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    digest = "a" * 64
    data.update(
        {
            "status": "frozen",
            "comparison_id": "example-cross-eval-v1",
            "created_at_utc": "2026-10-04T00:00:00Z",
        }
    )
    data["schema_router"]["commit"] = "b" * 40
    data["upstream"].update(
        {
            "repository": "example/upstream",
            "commit": "c" * 40,
            "license": "MIT",
            "source_artifacts": ["catalog.json", "cases.jsonl"],
        }
    )
    data["catalog"].update(
        {
            "path": "fixtures/catalog.json",
            "sha256": digest,
            "license": "MIT",
            "tool_count": 12,
            "field_contract_source": "upstream output schemas",
            "field_contract_sha256": "d" * 64,
        }
    )
    data["cases"].update(
        {
            "path": "fixtures/cases.jsonl",
            "sha256": "e" * 64,
            "supported_count": 10,
            "unsupported_count": 3,
            "ambiguous_count": 2,
            "labels_frozen": True,
        }
    )
    data["budget"].update(
        {
            "top_k": 5,
            "schema_budget_definition": "UTF-8 canonical JSON bytes disclosed to the agent",
            "schema_budget_bytes": 8192,
        }
    )
    data["latency"].update(
        {
            "cold_definition": "first process invocation including index construction",
            "hot_definition": "retrieval after one untimed warmup in the same process",
            "warmup_runs": 1,
            "measured_runs": 10,
        }
    )
    data["governance"]["frozen_before_scoring"] = True
    return data


def test_complete_frozen_manifest_is_valid() -> None:
    _module().validate_manifest(frozen_manifest())


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda data: data.update(status="template"), "status"),
        (lambda data: data["schema_router"].update(commit=None), "schema_router.commit"),
        (lambda data: data["upstream"].update(source_artifacts=[]), "source_artifacts"),
        (lambda data: data["cases"].update(labels_frozen=False), "labels_frozen"),
        (lambda data: data["metrics"].update(field_recall=False), "field recall"),
        (
            lambda data: data["boundary"].update(external_tool_execution=True),
            "must not execute external tools",
        ),
        (
            lambda data: data["governance"].update(
                post_freeze_semantic_tuning_allowed=True
            ),
            "semantic tuning after freeze",
        ),
    ],
)
def test_incomplete_or_unsafe_manifest_fails_closed(mutator, message: str) -> None:
    data = deepcopy(frozen_manifest())
    mutator(data)
    module = _module()
    with pytest.raises(module.ExternalValidationFreezeError, match=message):
        module.validate_manifest(data)
