"""Build and validate the frozen pi-jev handoff for external validation #796."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.external_validation_shared_catalog import build_package

PINNED_PI_JEV_COMMIT = "c5b5847aa189fe5ffec52893b7051fe8f9e7a548"


def build_jev_input() -> dict[str, Any]:
    package = build_package()
    return {
        "schema_version": 1,
        "experiment": "schemarouter-pi-jev-v1",
        "pi_jev_commit": PINNED_PI_JEV_COMMIT,
        "catalog_sha256": package["catalog_sha256"],
        "cases_sha256": package["cases_sha256"],
        "top_k": package["budget"]["top_k"],
        "external_execution": False,
        "catalog": [
            {"name": tool["name"], "description": tool["description"]}
            for tool in package["catalog"]
        ],
        "cases": [
            {"id": case["id"], "query": case["query"]}
            for case in package["cases"]
        ],
        "return_per_case": [
            "id",
            "candidate_tools",
            "activated_tools",
            "latency_ms",
            "probabilities",
        ],
        "scoring_note": (
            "Tool recall is scored from activated_tools; candidate recall is reported "
            "separately. probabilities may be null when unavailable."
        ),
    }


def validate_jev_output(payload: Any) -> None:
    package = build_package()
    expected = {case["id"] for case in package["cases"]}
    catalog = {tool["name"] for tool in package["catalog"]}
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("expected schema_version=1 object")
    rows = payload.get("cases")
    if not isinstance(rows, list):
        raise ValueError("cases must be a list")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(expected) or set(ids) != expected:
        raise ValueError("output must contain each frozen case exactly once")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each case result must be an object")
        for key in ("candidate_tools", "activated_tools"):
            tools = row.get(key)
            if not isinstance(tools, list) or not all(isinstance(x, str) for x in tools):
                raise ValueError(f"{row.get('id')}: {key} must be a string list")
            unknown = set(tools) - catalog
            if unknown:
                raise ValueError(f"{row.get('id')}: unknown {key}: {sorted(unknown)}")
        latency = row.get("latency_ms")
        if not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0:
            raise ValueError(f"{row.get('id')}: latency_ms must be non-negative")
        probabilities = row.get("probabilities")
        if probabilities is not None and not isinstance(probabilities, dict):
            raise ValueError(f"{row.get('id')}: probabilities must be object or null")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-out", type=Path)
    parser.add_argument("--validate-output", type=Path)
    args = parser.parse_args()
    if args.validate_output:
        validate_jev_output(json.loads(args.validate_output.read_text(encoding="utf-8")))
        print("valid pi-jev external-validation output")
        return
    payload = build_jev_input()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.input_out:
        args.input_out.parent.mkdir(parents=True, exist_ok=True)
        args.input_out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
