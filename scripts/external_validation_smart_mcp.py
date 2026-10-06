"""Validate and score the SchemaRouter × SmartMCP shared retrieval fixture."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> int:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return len(rendered.encode("utf-8"))


def _finite_nonnegative(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number or null")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _ndcg(candidates: list[str], required: set[str], k: int) -> float:
    if not required:
        return 0.0
    dcg = 0.0
    for rank, name in enumerate(candidates[:k], start=1):
        if name in required:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(required), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def load_package(package_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = _load(package_dir / "manifest.json")
    catalog = _load(package_dir / manifest["files"]["catalog"])
    cases = _load(package_dir / manifest["files"]["cases"])
    return manifest, catalog, cases


def validate_package(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    cases: dict[str, Any],
) -> None:
    package_id = manifest["package_id"]
    if catalog["catalog_id"] != package_id or cases["case_set_id"] != package_id:
        raise ValueError("package/catalog/case identifiers do not match")
    if (
        manifest.get("status") == "development_unfrozen"
        and manifest["governance"]["heldout_scoring_allowed"]
    ):
        raise ValueError("development fixture must not enable held-out scoring")

    tools = {tool["name"]: tool for tool in catalog["tools"]}
    if len(tools) != len(catalog["tools"]):
        raise ValueError("duplicate tool names")

    seen_ids: set[str] = set()
    observed = {"supported": 0, "ambiguous": 0, "unsupported": 0, "multi_tool": 0}
    for case in cases["cases"]:
        case_id = case["id"]
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        label = case["label"]
        if label not in {"supported", "ambiguous", "unsupported"}:
            raise ValueError(f"unknown case label: {label}")
        observed[label] += 1
        required = case.get("required_tools", [])
        if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
            raise ValueError(f"{case_id} required_tools must be a string list")
        unknown = set(required) - set(tools)
        if unknown:
            raise ValueError(f"{case_id} references unknown required tools: {sorted(unknown)}")
        if label == "supported" and not required:
            raise ValueError(f"{case_id} supported case must require at least one tool")
        if label != "supported" and required:
            raise ValueError(f"{case_id} negative/ambiguous case must not have required tools")
        if len(required) > 1:
            observed["multi_tool"] += 1
        acceptable = case.get("acceptable_candidate_tools", [])
        if not isinstance(acceptable, list) or not all(isinstance(x, str) for x in acceptable):
            raise ValueError(f"{case_id} acceptable_candidate_tools must be a string list")
        if set(acceptable) - set(tools):
            raise ValueError(f"{case_id} references unknown acceptable candidates")
        if label == "ambiguous" and not acceptable:
            raise ValueError(f"{case_id} ambiguous case must declare acceptable candidates")

    expected = manifest["counts"]
    actual = {
        "tools": len(tools),
        "cases": len(cases["cases"]),
        **observed,
    }
    if actual != expected:
        raise ValueError(f"package counts drifted: expected={expected} actual={actual}")

    top_k_values = manifest["comparison"]["top_k_values"]
    if top_k_values != sorted(set(top_k_values)) or not top_k_values or top_k_values[0] < 1:
        raise ValueError("top_k_values must be a sorted unique positive list")
    if manifest["comparison"]["max_candidates"] != max(top_k_values):
        raise ValueError("max_candidates must equal the largest Top-K")
    latency_repeats = manifest["comparison"].get("latency_repeats")
    if (
        isinstance(latency_repeats, bool)
        or not isinstance(latency_repeats, int)
        or latency_repeats < 1
    ):
        raise ValueError("latency_repeats must be a positive integer")


def build_template(manifest: dict[str, Any], cases: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "",
            "commit": None,
            "commit_source": "unavailable",
            "fixture_reference_revision": None,
            "package_version": None,
            "configuration": {},
        },
        "index_build_ms": None,
        "results": [
            {
                "id": case["id"],
                "candidate_tools": [],
                "exposed_contracts": [],
                "latency_ms": None,
            }
            for case in cases["cases"]
        ],
    }


def score(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    cases: dict[str, Any],
    submitted: dict[str, Any],
) -> dict[str, Any]:
    if submitted.get("package_id") != manifest["package_id"]:
        raise ValueError("result package id mismatch")

    implementation = submitted.get("implementation")
    if not isinstance(implementation, dict):
        raise ValueError("implementation must be an object")
    commit = implementation.get("commit")
    if commit is not None and (not isinstance(commit, str) or not commit.strip()):
        raise ValueError("implementation.commit must be a non-empty string or null")
    if manifest["governance"].get("heldout_scoring_allowed") and not commit:
        raise ValueError("held-out scoring requires the actual implementation.commit")

    tools = {tool["name"]: tool for tool in catalog["tools"]}
    case_map = {case["id"]: case for case in cases["cases"]}
    rows = submitted.get("results")
    if not isinstance(rows, list):
        raise ValueError("results must be a list")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("every result row must be an object")
    result_ids = [row.get("id") for row in rows]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("result ids must not contain duplicates")
    result_map = {row["id"]: row for row in rows}
    if set(result_map) != set(case_map):
        raise ValueError("result ids must match case ids exactly")

    top_ks = list(manifest["comparison"]["top_k_values"])
    max_candidates = int(manifest["comparison"]["max_candidates"])
    recall_by_k: dict[int, list[float]] = {k: [] for k in top_ks}
    full_by_k: dict[int, list[float]] = {k: [] for k in top_ks}
    ndcg_by_k: dict[int, list[float]] = {k: [] for k in top_ks}
    reciprocal_ranks: list[float] = []
    unsupported_nonempty: list[float] = []
    ambiguous_nonempty: list[float] = []
    ambiguous_top1_acceptable: list[float] = []
    ambiguous_any_acceptable: dict[int, list[float]] = {k: [] for k in top_ks}
    latencies: list[float] = []
    exposure_bytes: list[int] = []
    candidate_counts: list[int] = []
    per_case: list[dict[str, Any]] = []

    for case_id, case in case_map.items():
        row = result_map[case_id]
        candidates = row.get("candidate_tools", [])
        if not isinstance(candidates, list) or not all(isinstance(x, str) for x in candidates):
            raise ValueError(f"{case_id} candidate_tools must be a string list")
        if len(candidates) != len(set(candidates)):
            raise ValueError(f"{case_id} candidate_tools must not contain duplicates")
        if len(candidates) > max_candidates:
            raise ValueError(f"{case_id} exceeds max_candidates={max_candidates}")
        unknown = set(candidates) - set(tools)
        if unknown:
            raise ValueError(f"{case_id} references unknown candidate tools: {sorted(unknown)}")

        exposed = row.get("exposed_contracts", [])
        if not isinstance(exposed, list) or not all(isinstance(x, dict) for x in exposed):
            raise ValueError(f"{case_id} exposed_contracts must be an object list")
        exposed_names: list[str] = []
        for item in exposed:
            name = item.get("target") or item.get("name") or item.get("tool")
            if not isinstance(name, str) or name not in tools:
                raise ValueError(f"{case_id} exposed contract must identify a known target/name")
            if name not in candidates:
                raise ValueError(f"{case_id} exposes contract for non-candidate {name}")
            exposed_names.append(name)
        if len(exposed_names) != len(set(exposed_names)):
            raise ValueError(f"{case_id} exposes duplicate contracts")
        if exposed_names != candidates:
            raise ValueError(
                f"{case_id} exposed_contracts must match candidate_tools in ranked order"
            )

        latency = _finite_nonnegative(row.get("latency_ms"), field=f"{case_id}.latency_ms")
        if latency is not None:
            latencies.append(latency)
        bytes_exposed = _canonical_bytes(exposed)
        exposure_bytes.append(bytes_exposed)
        candidate_counts.append(len(candidates))

        required = set(case.get("required_tools", []))
        row_metrics: dict[str, Any] = {
            "id": case_id,
            "label": case["label"],
            "stratum": case.get("stratum"),
            "candidate_count": len(candidates),
            "exposed_contract_bytes": bytes_exposed,
        }

        if case["label"] == "supported":
            ranks = [candidates.index(name) + 1 for name in required if name in candidates]
            reciprocal_ranks.append(1.0 / min(ranks) if ranks else 0.0)
            for k in top_ks:
                prefix = set(candidates[:k])
                recall = len(required & prefix) / len(required)
                full = 1.0 if required <= prefix else 0.0
                ndcg = _ndcg(candidates, required, k)
                recall_by_k[k].append(recall)
                full_by_k[k].append(full)
                ndcg_by_k[k].append(ndcg)
                row_metrics[f"recall_at_{k}"] = recall
                row_metrics[f"full_coverage_at_{k}"] = bool(full)
        elif case["label"] == "unsupported":
            unsupported_nonempty.append(1.0 if candidates else 0.0)
        else:
            acceptable = set(case["acceptable_candidate_tools"])
            ambiguous_nonempty.append(1.0 if candidates else 0.0)
            ambiguous_top1_acceptable.append(
                1.0 if candidates and candidates[0] in acceptable else 0.0
            )
            for k in top_ks:
                ambiguous_any_acceptable[k].append(
                    1.0 if acceptable & set(candidates[:k]) else 0.0
                )

        per_case.append(row_metrics)

    index_build = _finite_nonnegative(submitted.get("index_build_ms"), field="index_build_ms")
    summary: dict[str, Any] = {
        "supported_mrr": mean(reciprocal_ranks) if reciprocal_ranks else None,
        "unsupported_nonempty_candidate_rate": (
            mean(unsupported_nonempty) if unsupported_nonempty else None
        ),
        "ambiguous_nonempty_candidate_rate": (
            mean(ambiguous_nonempty) if ambiguous_nonempty else None
        ),
        "ambiguous_top1_acceptable_rate": (
            mean(ambiguous_top1_acceptable) if ambiguous_top1_acceptable else None
        ),
        "mean_candidate_count": mean(candidate_counts) if candidate_counts else 0.0,
        "mean_exposed_contract_bytes": mean(exposure_bytes) if exposure_bytes else 0.0,
        "median_retrieval_ms": median(latencies) if latencies else None,
        "p95_retrieval_ms": _percentile(latencies, 0.95),
        "index_build_ms": index_build,
    }
    for k in top_ks:
        summary[f"supported_recall_at_{k}"] = mean(recall_by_k[k]) if recall_by_k[k] else None
        summary[f"supported_full_coverage_at_{k}"] = mean(full_by_k[k]) if full_by_k[k] else None
        summary[f"supported_ndcg_at_{k}"] = mean(ndcg_by_k[k]) if ndcg_by_k[k] else None
        summary[f"ambiguous_any_acceptable_at_{k}"] = (
            mean(ambiguous_any_acceptable[k]) if ambiguous_any_acceptable[k] else None
        )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": submitted.get("implementation", {}),
        "summary": summary,
        "per_case": per_case,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--package-dir", required=True, type=Path)

    template_parser = sub.add_parser("template")
    template_parser.add_argument("--package-dir", required=True, type=Path)
    template_parser.add_argument("--out", required=True, type=Path)

    score_parser = sub.add_parser("score")
    score_parser.add_argument("--package-dir", required=True, type=Path)
    score_parser.add_argument("--results", required=True, type=Path)
    score_parser.add_argument("--out", type=Path)

    args = parser.parse_args()
    manifest, catalog, cases = load_package(args.package_dir)
    validate_package(manifest, catalog, cases)

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "package_id": manifest["package_id"],
                    "status": "valid",
                    "counts": manifest["counts"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if args.command == "template":
        payload = build_template(manifest, cases)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(args.out)
        return

    submitted = _load(args.results)
    payload = score(manifest, catalog, cases, submitted)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
