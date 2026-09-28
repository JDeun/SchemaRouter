from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "export_research_evidence.py"


def _module():
    spec = importlib.util.spec_from_file_location("export_research_evidence", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evidence exporter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ledger() -> dict:
    return {
        "schema_version": "1",
        "updated_at": "2026-09-28",
        "standing_targets": {"exact": 0.85},
        "governance": {"fresh_is_tuning_eligible": False},
        "experiments": [
            {
                "id": "dev-pass",
                "cycle": "0.11",
                "issue": 1,
                "pull_request": 2,
                "status": "completed",
                "decision": "pass",
                "preregistered": True,
                "source_revision": "abc",
                "workflow_run_id": 10,
                "artifact_id": 20,
                "artifact_sha256": "sha256:deadbeef",
                "dataset": {
                    "role": "tuning_eligible_development",
                    "corpus_sha256": "corpus-dev",
                },
                "result": {
                    "supported_exact_route_accuracy": 0.86,
                    "near_domain_unsupported_rejection": 0.98,
                    "out_of_domain_rejection": 1.0,
                    "false_route_rate": 0.005,
                    "total_p95_ms": 180.0,
                    "authority_violations": 0,
                    "execution_errors": 0,
                },
            },
            {
                "id": "fresh-fail",
                "cycle": "0.11",
                "status": "completed",
                "decision": "reject_after_fresh_failure",
                "fresh_corpus": {"sha256": "fresh-sha"},
                "invalid_technical_runs": [
                    {"workflow_run_id": 11, "reason": "contract failure"}
                ],
                "result": {
                    "exact": 0.84,
                    "near_rejection": 0.90,
                    "ood_rejection": 1.0,
                    "false_route_rate": 0.08,
                    "p95_latency_ms": 278.0,
                },
            },
        ],
    }


def test_build_package_flattens_metrics_and_provenance() -> None:
    module = _module()
    package = module.build_package(_ledger())

    assert package["experiment_count"] == 2
    first = package["experiments"][0]
    assert first["data_role"] == "tuning_eligible_development"
    assert first["corpus_sha256"] == "corpus-dev"
    assert first["supported_exact_route_accuracy"] == 0.86
    assert first["p95_ms"] == 180.0

    second = package["experiments"][1]
    assert second["data_role"] == "fresh_confirmation"
    assert second["corpus_sha256"] == "fresh-sha"
    assert second["supported_exact_route_accuracy"] == 0.84
    assert second["near_domain_unsupported_rejection"] == 0.90
    assert len(package["invalidated_runs"]) == 1
    assert package["invalidated_runs"][0]["workflow_run_id"] == 11


def test_export_writes_machine_and_table_ready_outputs(tmp_path: Path) -> None:
    module = _module()
    ledger_path = tmp_path / "ledger.json"
    out_dir = tmp_path / "out"
    ledger_path.write_text(json.dumps(_ledger()), encoding="utf-8")

    package = module.export(ledger_path, out_dir)

    assert package["experiment_count"] == 2
    assert (out_dir / "research-evidence-package.json").exists()
    assert (out_dir / "research-experiments.csv").exists()
    assert (out_dir / "invalidated-runs.csv").exists()
    table = (out_dir / "research-evidence-table.md").read_text(encoding="utf-8")
    assert "dev-pass" in table
    assert "fresh-fail" in table
