"""Export paper-ready SchemaRouter research evidence from the canonical ledger."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_LEDGER = Path("benchmarks/research-experiment-ledger.json")
DEFAULT_OUT = Path("docs/research/generated")


def _first(mapping: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        value: Any = mapping
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value is not None:
            return value
    return None


def _metric(result: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = result.get(name)
        if value is not None:
            return value
    return None


def _experiment_row(exp: dict[str, Any]) -> dict[str, Any]:
    result = exp.get("result") if isinstance(exp.get("result"), dict) else {}
    dataset = exp.get("dataset") if isinstance(exp.get("dataset"), dict) else {}
    fresh = exp.get("fresh_corpus") if isinstance(exp.get("fresh_corpus"), dict) else {}

    p95 = _metric(
        result,
        "total_p95_ms",
        "combined_p95_ms",
        "candidate_p95_latency_ms",
        "p95_latency_ms",
        "measured_total_p95_ms",
        "recomputed_promotable_p95_ms_excluding_sparse_scoring",
    )
    if p95 is None:
        latency = result.get("total_latency_ms")
        if isinstance(latency, dict):
            p95 = latency.get("p95")

    corpus_sha = (
        dataset.get("corpus_sha256")
        or fresh.get("sha256")
        or exp.get("corpus_sha256")
    )
    data_role = (
        dataset.get("role")
        or exp.get("data_role")
        or fresh.get("role")
        or ("fresh_confirmation" if fresh else None)
    )

    return {
        "id": exp.get("id"),
        "cycle": exp.get("cycle"),
        "issue": exp.get("issue") or exp.get("work_item"),
        "pull_request": exp.get("pull_request"),
        "status": exp.get("status"),
        "decision": exp.get("decision"),
        "preregistered": exp.get("preregistered"),
        "data_role": data_role,
        "source_revision": exp.get("source_revision"),
        "workflow_run_id": exp.get("workflow_run_id"),
        "artifact_id": exp.get("artifact_id"),
        "artifact_sha256": exp.get("artifact_sha256"),
        "corpus_sha256": corpus_sha,
        "supported_exact_route_accuracy": _metric(
            result,
            "supported_exact_route_accuracy",
            "exact",
            "raw_supported_top1_accuracy",
        ),
        "near_domain_unsupported_rejection": _metric(
            result,
            "near_domain_unsupported_rejection",
            "near_rejection",
        ),
        "out_of_domain_rejection": _metric(
            result,
            "out_of_domain_rejection",
            "ood_rejection",
        ),
        "false_route_rate": _metric(
            result,
            "false_route_rate",
            "canonical_false_route_rate",
        ),
        "p95_ms": p95,
        "authority_violations": _metric(result, "authority_violations"),
        "execution_errors": _metric(result, "execution_errors"),
        "failure_reason": exp.get("failure_reason"),
    }


def _invalid_runs(exp: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in ("invalid_runs", "invalid_pre_runs", "invalid_technical_runs"):
        values = exp.get(field)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            rows.append(
                {
                    "experiment_id": exp.get("id"),
                    "field": field,
                    "workflow_run_id": value.get("workflow_run_id")
                    or value.get("run_id"),
                    "reason": value.get("reason"),
                }
            )
    return rows


def build_package(ledger: dict[str, Any]) -> dict[str, Any]:
    experiments = ledger.get("experiments")
    if not isinstance(experiments, list):
        raise ValueError("ledger.experiments must be a list")

    experiment_rows = [_experiment_row(exp) for exp in experiments]
    invalid_rows = [
        row
        for exp in experiments
        for row in _invalid_runs(exp)
    ]

    role_counts: dict[str, int] = {}
    for row in experiment_rows:
        role = row["data_role"] or "unspecified"
        role_counts[str(role)] = role_counts.get(str(role), 0) + 1

    return {
        "schema_version": 1,
        "source": "benchmarks/research-experiment-ledger.json",
        "ledger_schema_version": ledger.get("schema_version"),
        "ledger_updated_at": ledger.get("updated_at"),
        "standing_targets": ledger.get("standing_targets"),
        "governance": ledger.get("governance"),
        "current_research_conclusion": ledger.get("current_research_conclusion"),
        "experiment_count": len(experiment_rows),
        "dataset_role_counts": dict(sorted(role_counts.items())),
        "experiments": experiment_rows,
        "invalidated_runs": invalid_rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def _write_markdown(path: Path, package: dict[str, Any]) -> None:
    rows = package["experiments"]
    lines = [
        "# SchemaRouter research evidence table",
        "",
        f"Ledger updated: `{package.get('ledger_updated_at')}`  ",
        f"Experiments: **{package['experiment_count']}**",
        "",
        "| ID | Status | Decision | Data role | Exact | Near reject | OOD reject | "
        "False-route | p95 ms | Run |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        def fmt(value: Any) -> str:
            if isinstance(value, float):
                return f"{value:.4f}"
            return "" if value is None else str(value)

        lines.append(
            "| "
            + " | ".join(
                [
                    fmt(row["id"]),
                    fmt(row["status"]),
                    fmt(row["decision"]),
                    fmt(row["data_role"]),
                    fmt(row["supported_exact_route_accuracy"]),
                    fmt(row["near_domain_unsupported_rejection"]),
                    fmt(row["out_of_domain_rejection"]),
                    fmt(row["false_route_rate"]),
                    fmt(row["p95_ms"]),
                    fmt(row["workflow_run_id"]),
                ]
            )
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export(ledger_path: Path, out_dir: Path) -> dict[str, Any]:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    package = build_package(ledger)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "research-evidence-package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(out_dir / "research-experiments.csv", package["experiments"])
    _write_csv(out_dir / "invalidated-runs.csv", package["invalidated_runs"])
    _write_markdown(out_dir / "research-evidence-table.md", package)
    return package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    package = export(args.ledger, args.out_dir)
    print(
        json.dumps(
            {
                "experiment_count": package["experiment_count"],
                "dataset_role_counts": package["dataset_role_counts"],
                "out_dir": str(args.out_dir),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
