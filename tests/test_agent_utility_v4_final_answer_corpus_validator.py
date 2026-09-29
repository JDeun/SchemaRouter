from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_agent_utility_v4_final_answer_corpus.py"


def _module():
    spec = importlib.util.spec_from_file_location("v4_corpus_validator", VALIDATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_corpus(module) -> dict:
    plan = module._authoring_plan()
    tasks = []
    for index, slot in enumerate(plan["slots"]):
        source_id = f"fixture.source:{index}"
        corrective = None
        if slot["answer_task_stratum"] == "corrective_expansion_required":
            corrective = {
                "initial_candidate_miss": True,
                "ground_truth_trigger_visible": False,
            }

        tasks.append(
            {
                "semantic_task_id": slot["semantic_task_id"],
                "answer_task_stratum": slot["answer_task_stratum"],
                "language": slot["language"],
                "query": f"synthetic answer validator fixture {index} {slot['language']}",
                "required_routes": [f"fixture.tool_{index}.call"],
                "evidence_payloads": [
                    {
                        "source_id": source_id,
                        "payload": {"fixture_value": index + 0.5},
                    }
                ],
                "allowed_source_ids": [source_id],
                "required_facts": [
                    {
                        "key": "fixture_value",
                        "value": index + 0.5,
                        "unit": "fixture_unit",
                        "source_id": source_id,
                    }
                ],
                "forbidden_facts": [],
                "numeric_tolerances": {
                    "fixture_value": {
                        "absolute": 0.0,
                        "relative": 0.0,
                    }
                },
                "accepted_units": {
                    "fixture_value": ["fixture_unit"],
                },
                "mandatory_answer_fields": ["answer", "facts", "sources"],
                "corrective_contract": corrective,
            }
        )

    return {
        "schema_version": 1,
        "issue": 424,
        "experiment": plan["experiment"],
        "authoring_slots_sha256": plan["slots_sha256"],
        "generator_source_revision": "b" * 40,
        "tasks_sha256": module._sha(tasks),
        "catalogs": {
            "100": {"endpoint_count": 100, "sha256": "1" * 64},
            "250": {"endpoint_count": 250, "sha256": "2" * 64},
        },
        "candidate_set_manifest_sha256": "e" * 64,
        "tasks": tasks,
    }


def test_v4_corpus_validator_accepts_exact_frozen_surface() -> None:
    module = _module()
    corpus = _valid_corpus(module)

    summary = module.validate_corpus(corpus)

    assert summary["issue"] == 424
    assert summary["task_count"] == 144
    assert summary["unique_query_count"] == 144
    assert summary["tasks_sha256"] == corpus["tasks_sha256"]
    assert summary["catalog_sizes"] == [100, 250]


def test_v4_corpus_validator_rejects_missing_numeric_tolerance() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["numeric_tolerances"] = {}

    with pytest.raises(ValueError, match="numeric_tolerances keys"):
        module.validate_corpus(corpus)


def test_v4_corpus_validator_rejects_bad_provenance_source() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["required_facts"][0]["source_id"] = "unknown.source"

    with pytest.raises(ValueError, match="source_id is not allowed evidence"):
        module.validate_corpus(corpus)


def test_v4_corpus_validator_rejects_missing_canonical_unit() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["accepted_units"]["fixture_value"] = ["other_unit"]

    with pytest.raises(ValueError, match="must include canonical unit"):
        module.validate_corpus(corpus)


def test_v4_corpus_validator_rejects_invalid_corrective_contract() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    task = next(
        row
        for row in corpus["tasks"]
        if row["answer_task_stratum"] == "corrective_expansion_required"
    )
    task["corrective_contract"]["ground_truth_trigger_visible"] = True

    with pytest.raises(ValueError, match="ground_truth_trigger_visible=false"):
        module.validate_corpus(corpus)


def test_v4_corpus_validator_rejects_content_hash_drift() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["query"] += " changed"

    with pytest.raises(ValueError, match="tasks_sha256"):
        module.validate_corpus(corpus)
