from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_agent_utility_v3_heldout_corpus.py"


def _module():
    spec = importlib.util.spec_from_file_location("v3_corpus_validator", VALIDATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_corpus(module) -> dict:
    plan = module._authoring_plan()
    tasks = []
    for index, slot in enumerate(plan["slots"]):
        unsupported = slot["task_stratum"] in {
            "missing_capability_unsupported",
            "out_of_domain",
        }
        tasks.append(
            {
                "semantic_task_id": slot["semantic_task_id"],
                "task_stratum": slot["task_stratum"],
                "language": slot["language"],
                "query": f"synthetic validator fixture {index} {slot['language']}",
                "supported": not unsupported,
                "required_routes": [] if unsupported else [f"fixture.tool_{index}.call"],
                "executor_fixture": {"initial_state": {"fixture_index": index}},
                "expected_outcome": {"fixture_status": "deterministic"},
            }
        )

    return {
        "schema_version": 1,
        "issue": 432,
        "benchmark": plan["benchmark"],
        "authoring_slots_sha256": plan["slots_sha256"],
        "generator_source_revision": "a" * 40,
        "tasks_sha256": module._sha(tasks),
        "catalogs": {
            str(size): {
                "endpoint_count": size,
                "sha256": f"{position + 1:064x}",
            }
            for position, size in enumerate(module.EXPECTED_CATALOGS)
        },
        "candidate_set_manifest_sha256": "f" * 64,
        "prior_query_manifest_sha256": (
            module.known_prior_query_manifest()["union_sha256"]
        ),
        "tasks": tasks,
    }


def test_v3_corpus_validator_accepts_exact_frozen_surface() -> None:
    module = _module()
    corpus = _valid_corpus(module)

    summary = module.validate_corpus(corpus)

    assert summary["issue"] == 432
    assert summary["task_count"] == 780
    assert summary["unique_query_count"] == 780
    assert summary["tasks_sha256"] == corpus["tasks_sha256"]
    assert summary["catalog_sizes"] == [100, 250, 500, 1000]
    assert summary["exact_prior_query_overlap_count"] == 0
    assert summary["prior_query_manifest_sha256"] == (
        corpus["prior_query_manifest_sha256"]
    )


def test_v3_corpus_validator_rejects_duplicate_query() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][1]["query"] = corpus["tasks"][0]["query"]
    corpus["tasks_sha256"] = module._sha(corpus["tasks"])

    with pytest.raises(ValueError, match="duplicate normalized query"):
        module.validate_corpus(corpus)


def test_v3_corpus_validator_rejects_slot_metadata_drift() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["language"] = "wrong"

    with pytest.raises(ValueError, match="language drifted"):
        module.validate_corpus(corpus)


def test_v3_corpus_validator_rejects_gold_routes_on_unsupported_task() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    task = next(row for row in corpus["tasks"] if not row["supported"])
    task["required_routes"] = ["fixture.invalid.call"]

    with pytest.raises(ValueError, match="unsupported task must not declare gold routes"):
        module.validate_corpus(corpus)


def test_v3_corpus_validator_rejects_content_hash_drift() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["query"] += " changed"

    with pytest.raises(ValueError, match="tasks_sha256"):
        module.validate_corpus(corpus)


def test_v3_corpus_validator_rejects_prior_benchmark_query_overlap() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["tasks"][0]["query"] = (
        "Search scientific papers about solid-state battery electrolytes."
    )
    corpus["tasks_sha256"] = module._sha(corpus["tasks"])

    with pytest.raises(ValueError, match="prior benchmark surface"):
        module.validate_corpus(corpus)


def test_corpus_validator_rejects_prior_query_manifest_drift() -> None:
    module = _module()
    corpus = _valid_corpus(module)
    corpus["prior_query_manifest_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="prior_query_manifest_sha256"):
        module.validate_corpus(corpus)
