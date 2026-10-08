from __future__ import annotations

import argparse
import json
from pathlib import Path


def score(rows: list[dict[str, object]]) -> dict[str, float]:
    total = len(rows)
    if total == 0:
        raise ValueError("benchmark requires at least one row")

    def rate(key: str) -> float:
        return sum(bool(row.get(key, False)) for row in rows) / total

    return {
        "premature_action_rate": rate("premature_action"),
        "evidence_complete_action_rate": rate("evidence_complete_action"),
        "unsupported_action_rate": rate("unsupported_action"),
        "exact_action_success": rate("exact_action_success"),
        "provenance_correctness": rate("provenance_correct"),
        "argument_schema_validity": rate("argument_schema_valid"),
        "route_field_exactness": rate("route_field_exact"),
        "false_refusal_rate": rate("false_refusal"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("input must contain a rows array")
    result = {"condition": payload.get("condition"), "metrics": score(rows)}
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
