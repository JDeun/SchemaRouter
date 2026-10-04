"""Validate and score the frozen hope-agent external retrieval package.

This runner intentionally performs no router execution itself. Each implementation
fills the machine-readable result template with its native candidate/activation/
schema-exposure output, then this script applies the same deterministic scoring.
"""
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
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return len(rendered.encode("utf-8"))


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
    if manifest["package_id"] != catalog["catalog_id"]:
        raise ValueError("manifest/catalog package id mismatch")
    if manifest["package_id"] != cases["case_set_id"]:
        raise ValueError("manifest/case package id mismatch")

    tools = {tool["name"]: tool for tool in catalog["tools"]}
    if len(tools) != len(catalog["tools"]):
        raise ValueError("duplicate tool names")

    labels = {"supported": 0, "unsupported": 0, "ambiguous": 0}
    seen_ids: set[str] = set()
    for case in cases["cases"]:
        case_id = case["id"]
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        label = case["label"]
        if label not in labels:
            raise ValueError(f"unknown case label: {label}")
        labels[label] += 1

        required = set(case.get("required_tools", []))
        unknown = required - set(tools)
        if unknown:
            raise ValueError(f"case {case_id} references unknown required tools: {sorted(unknown)}")
        if label == "supported" and not required:
            raise ValueError(f"supported case {case_id} has no required tool")
        if label != "supported" and required:
            raise ValueError(f"negative case {case_id} must not require activation")

        required_fields = case.get("required_fields", {})
        if label == "supported" and not required_fields:
            raise ValueError(f"supported case {case_id} has no required-field ground truth")
        for tool_name, fields in required_fields.items():
            if tool_name not in required:
                raise ValueError(f"case {case_id} has fields for a non-required tool")
            declared = {field["name"] for field in tools[tool_name]["output_fields"]}
            missing = set(fields) - declared
            if missing:
                raise ValueError(
                    f"case {case_id} requires undeclared fields for {tool_name}: {sorted(missing)}"
                )

        acceptable = set(case.get("acceptable_candidate_tools", []))
        if acceptable - set(tools):
            raise ValueError(f"case {case_id} has unknown acceptable candidate tools")

    expected = manifest["frozen_counts"]
    observed = {
        "tools": len(tools),
        "cases": len(cases["cases"]),
        **labels,
    }
    if observed != expected:
        raise ValueError(f"frozen counts drifted: expected={expected} observed={observed}")

    boundary = manifest["comparison_boundary"]
    if boundary["execution"] != "disabled" or boundary["paid_models"] != "disabled":
        raise ValueError("offline package must keep execution and paid models disabled")
    if int(boundary["top_k"]) < 1:
        raise ValueError("top_k must be positive")
    if int(boundary["schema_budget_bytes"]) < 1:
        raise ValueError("schema budget must be positive")


def build_template(manifest: dict[str, Any], cases: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {"name": "", "commit": "", "configuration": {}},
        "results": [
            {
                "id": case["id"],
                "candidate_tools": [],
                "activated_tools": [],
                "exposed_schemas": [],
                "cold_start_ms": None,
                "hot_path_ms": None,
            }
            for case in cases["cases"]
        ],
    }


def _finite_ms(value: Any, *, field: str, case_id: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{case_id} {field} must be a number or null")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{case_id} {field} must be a finite non-negative number")
    return number


def score(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    cases: dict[str, Any],
    submitted: dict[str, Any],
) -> dict[str, Any]:
    if submitted.get("package_id") != manifest["package_id"]:
        raise ValueError("result package id mismatch")

    tools = {tool["name"]: tool for tool in catalog["tools"]}
    case_map = {case["id"]: case for case in cases["cases"]}
    rows = submitted.get("results")
    if not isinstance(rows, list):
        raise ValueError("results must be a list")
    result_map = {row.get("id"): row for row in rows if isinstance(row, dict)}
    if set(result_map) != set(case_map):
        raise ValueError("result ids must match the frozen case ids exactly")

    top_k = int(manifest["comparison_boundary"]["top_k"])
    schema_budget = int(manifest["comparison_boundary"]["schema_budget_bytes"])
    candidate_recalls: list[float] = []
    activation_recalls: list[float] = []
    field_recalls: list[float] = []
    unsupported_false: list[float] = []
    ambiguous_false: list[float] = []
    candidate_counts: list[int] = []
    activation_counts: list[int] = []
    schema_bytes: list[int] = []
    budget_ok: list[float] = []
    cold: list[float] = []
    hot: list[float] = []
    per_case: list[dict[str, Any]] = []

    for case_id, case in case_map.items():
        row = result_map[case_id]
        candidates = row.get("candidate_tools", [])
        activated = row.get("activated_tools", [])
        exposed = row.get("exposed_schemas", [])
        if not isinstance(candidates, list) or not all(isinstance(x, str) for x in candidates):
            raise ValueError(f"{case_id} candidate_tools must be a string list")
        if not isinstance(activated, list) or not all(isinstance(x, str) for x in activated):
            raise ValueError(f"{case_id} activated_tools must be a string list")
        if len(candidates) > top_k or len(activated) > top_k:
            raise ValueError(f"{case_id} exceeds frozen Top-K={top_k}")
        if set(candidates) - set(tools) or set(activated) - set(tools):
            raise ValueError(f"{case_id} references unknown tools")
        if not isinstance(exposed, list) or not all(isinstance(x, dict) for x in exposed):
            raise ValueError(f"{case_id} exposed_schemas must be an object list")

        exposed_fields: dict[str, set[str]] = {}
        exposed_names: set[str] = set()
        for item in exposed:
            name = item.get("name")
            fields = item.get("output_fields", [])
            if not isinstance(name, str) or name not in tools:
                raise ValueError(f"{case_id} exposed schema has unknown tool name")
            if name not in activated:
                raise ValueError(f"{case_id} exposed schema for non-activated tool {name}")
            if name in exposed_names:
                raise ValueError(f"{case_id} exposes duplicate schema for {name}")
            exposed_names.add(name)
            if not isinstance(fields, list) or not all(isinstance(x, dict) for x in fields):
                raise ValueError(f"{case_id} output_fields must be an object list")
            declared = {field["name"] for field in tools[name]["output_fields"]}
            names = {field.get("name") for field in fields}
            if None in names or not names <= declared:
                raise ValueError(f"{case_id} exposed schema invents fields for {name}")
            exposed_fields[name] = {str(value) for value in names}

        required = set(case.get("required_tools", []))
        if case["label"] == "supported":
            candidate_recalls.append(len(required & set(candidates)) / len(required))
            activation_recalls.append(len(required & set(activated)) / len(required))
            required_fields = case["required_fields"]
            hits = 0
            total = 0
            for tool_name, fields in required_fields.items():
                total += len(fields)
                hits += len(set(fields) & exposed_fields.get(tool_name, set()))
            field_recalls.append(hits / total if total else 1.0)
        elif case["label"] == "unsupported":
            unsupported_false.append(1.0 if activated else 0.0)
        else:
            ambiguous_false.append(1.0 if activated else 0.0)

        measured_schema_bytes = sum(_canonical_bytes(item) for item in exposed)
        candidate_counts.append(len(candidates))
        activation_counts.append(len(activated))
        schema_bytes.append(measured_schema_bytes)
        budget_ok.append(1.0 if measured_schema_bytes <= schema_budget else 0.0)
        cold_value = _finite_ms(row.get("cold_start_ms"), field="cold_start_ms", case_id=case_id)
        hot_value = _finite_ms(row.get("hot_path_ms"), field="hot_path_ms", case_id=case_id)
        if cold_value is not None:
            cold.append(cold_value)
        if hot_value is not None:
            hot.append(hot_value)

        per_case.append(
            {
                "id": case_id,
                "label": case["label"],
                "candidate_count": len(candidates),
                "activation_count": len(activated),
                "exposed_schema_bytes": measured_schema_bytes,
                "schema_budget_ok": measured_schema_bytes <= schema_budget,
            }
        )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": submitted.get("implementation", {}),
        "summary": {
            "supported_candidate_tool_recall": mean(candidate_recalls),
            "supported_activation_tool_recall": mean(activation_recalls),
            "supported_required_field_recall": mean(field_recalls),
            "unsupported_false_activation_rate": mean(unsupported_false),
            "ambiguous_false_activation_rate": mean(ambiguous_false),
            "mean_candidate_count": mean(candidate_counts),
            "mean_activation_count": mean(activation_counts),
            "mean_exposed_schema_bytes": mean(schema_bytes),
            "schema_budget_compliance_rate": mean(budget_ok),
            "median_cold_start_ms": median(cold) if cold else None,
            "median_hot_path_ms": median(hot) if hot else None,
        },
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
                    "frozen_counts": manifest["frozen_counts"],
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
