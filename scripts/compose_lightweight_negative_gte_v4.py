"""Offline composition of frozen BGE strict base, negative veto, and GTE rescue."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "operation-routing-v4-lightweight-negative-gte-composite.json"
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _index_rows(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{label}: invalid case_id at row {index}")
        if case_id in indexed:
            raise ValueError(f"{label}: duplicate case_id {case_id!r}")
        indexed[case_id] = row
    return indexed


def _passes_rescue(row: dict[str, Any], rule: dict[str, float]) -> bool:
    if row.get("base_accepted"):
        return False
    if not row.get("gte_agrees"):
        return False
    return (
        float(row["gte_top_score"]) >= float(rule["min_gte_score"])
        and float(row["gte_margin"]) >= float(rule["min_gte_margin"])
        and float(row["base_score_deficit"])
        <= float(rule["max_base_score_deficit"])
        and float(row["base_margin_deficit"])
        <= float(rule["max_base_margin_deficit"])
    )


def _negative_veto(
    row: dict[str, Any],
    *,
    score_min: float,
    advantage_min: float,
) -> bool:
    return (
        float(row["max_negative_score"]) >= score_min
        and float(row["negative_advantage"]) >= advantage_min
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def compose(
    gte_analysis: dict[str, Any],
    negative_analysis: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    gte_rows_raw = gte_analysis.get("rows")
    negative_rows_raw = negative_analysis.get("rows")
    if not isinstance(gte_rows_raw, list) or not isinstance(negative_rows_raw, list):
        raise ValueError("both analyses must contain row lists")

    gte_rows = _index_rows(gte_rows_raw, "gte")
    neg_rows = _index_rows(negative_rows_raw, "negative")
    if set(gte_rows) != set(neg_rows):
        raise ValueError("source artifacts do not have identical case IDs")
    if len(gte_rows) != int(manifest["canonical_dev"]["case_count"]):
        raise ValueError("unexpected case count")

    veto_cfg = manifest["negative_veto"]
    rescue_cfg = manifest["gte_rescue"]
    rules = rescue_cfg["rules"]

    rows: list[dict[str, Any]] = []
    authority_violations = 0
    negative_veto_total = 0
    negative_veto_correct_supported = 0
    negative_veto_unsupported = 0
    rescued_correct_supported = 0
    rescued_wrong_supported = 0
    rescued_unsupported = 0

    for case_id in sorted(gte_rows):
        gte = gte_rows[case_id]
        neg = neg_rows[case_id]

        for key_a, key_b in (
            ("expected", "expected"),
            ("category", "category"),
            ("language", "language"),
        ):
            if gte.get(key_a) != neg.get(key_b):
                raise ValueError(
                    f"case {case_id}: source mismatch for {key_a}: "
                    f"{gte.get(key_a)!r} != {neg.get(key_b)!r}"
                )

        base_route = str(gte["base_raw_route"])
        if base_route != str(neg["raw_top_route"]):
            raise ValueError(f"case {case_id}: BGE raw route mismatch")

        expected = gte.get("expected")
        base_accepted = bool(gte["base_accepted"])
        final_route: str | None = None
        path = "base_abstain"

        if base_accepted:
            vetoed = _negative_veto(
                neg,
                score_min=float(veto_cfg["max_negative_score_min"]),
                advantage_min=float(veto_cfg["negative_advantage_min"]),
            )
            if vetoed:
                path = "negative_veto"
                negative_veto_total += 1
                if expected is None:
                    negative_veto_unsupported += 1
                elif expected == base_route:
                    negative_veto_correct_supported += 1
            else:
                final_route = base_route
                path = "base_accept"
        else:
            rule = rules.get(base_route)
            if rule is None:
                raise ValueError(f"case {case_id}: no rescue rule for {base_route}")
            if _passes_rescue(gte, rule):
                final_route = base_route
                path = "gte_rescue"
                if expected is None:
                    rescued_unsupported += 1
                elif expected == base_route:
                    rescued_correct_supported += 1
                else:
                    rescued_wrong_supported += 1

        if final_route is not None and final_route != base_route:
            authority_violations += 1

        rows.append(
            {
                "case_id": case_id,
                "category": gte.get("category"),
                "language": gte.get("language"),
                "unsupported_family": neg.get("unsupported_family"),
                "expected": expected,
                "base_raw_route": base_route,
                "base_accepted": base_accepted,
                "max_negative_score": float(neg["max_negative_score"]),
                "negative_advantage": float(neg["negative_advantage"]),
                "gte_route": str(gte["gte_route"]),
                "gte_agrees": bool(gte["gte_agrees"]),
                "gte_top_score": float(gte["gte_top_score"]),
                "gte_margin": float(gte["gte_margin"]),
                "base_score_deficit": float(gte["base_score_deficit"]),
                "base_margin_deficit": float(gte["base_margin_deficit"]),
                "decision_path": path,
                "final_route": final_route,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    unsupported = [row for row in rows if row["expected"] is None]

    supported_correct = sum(
        row["final_route"] == row["expected"] for row in supported
    )
    wrong_supported_accepted = sum(
        row["final_route"] is not None and row["final_route"] != row["expected"]
        for row in supported
    )
    near_rejected = sum(row["final_route"] is None for row in near)
    ood_rejected = sum(row["final_route"] is None for row in ood)
    false_routes = sum(row["final_route"] is not None for row in unsupported)

    per_language: dict[str, Any] = {}
    for language in sorted({str(row["language"]) for row in rows}):
        subset = [row for row in rows if str(row["language"]) == language]
        lang_supported = [row for row in subset if row["expected"] is not None]
        lang_unsupported = [row for row in subset if row["expected"] is None]
        per_language[language] = {
            "cases": len(subset),
            "supported_exact_route_accuracy": _rate(
                sum(
                    row["final_route"] == row["expected"]
                    for row in lang_supported
                ),
                len(lang_supported),
            ),
            "unsupported_rejection": _rate(
                sum(row["final_route"] is None for row in lang_unsupported),
                len(lang_unsupported),
            ),
            "false_routes": sum(
                row["final_route"] is not None for row in lang_unsupported
            ),
        }

    per_route: dict[str, Any] = {}
    for route in sorted(
        {str(row["expected"]) for row in supported if row["expected"] is not None}
    ):
        subset = [row for row in supported if row["expected"] == route]
        exact = sum(row["final_route"] == route for row in subset)
        per_route[route] = {
            "cases": len(subset),
            "exact": exact,
            "exact_rate": _rate(exact, len(subset)),
        }

    per_family: dict[str, Any] = {}
    for family in sorted(
        {
            str(row["unsupported_family"])
            for row in unsupported
            if row["unsupported_family"] is not None
        }
    ):
        subset = [
            row
            for row in unsupported
            if str(row["unsupported_family"]) == family
        ]
        rejected = sum(row["final_route"] is None for row in subset)
        per_family[family] = {
            "cases": len(subset),
            "rejected": rejected,
            "rejection_rate": _rate(rejected, len(subset)),
        }

    exact_rate = _rate(supported_correct, len(supported))
    near_rate = _rate(near_rejected, len(near))
    ood_rate = _rate(ood_rejected, len(ood))
    false_rate = _rate(false_routes, len(unsupported))

    gate = manifest["promotion_gate"]
    promotion_gate_pass = (
        exact_rate >= float(gate["supported_exact_route_accuracy_min"])
        and near_rate
        >= float(gate["near_domain_unsupported_rejection_min"])
        and ood_rate == float(gate["out_of_domain_rejection"])
        and false_rate <= float(gate["false_route_rate_max"])
        and authority_violations <= int(gate["authority_violations_max"])
    )

    result = {
        "experiment": manifest["experiment"],
        "summary": {
            "cases": len(rows),
            "supported_correct": supported_correct,
            "supported_exact_route_accuracy": exact_rate,
            "wrong_supported_accepted": wrong_supported_accepted,
            "near_domain_rejected": near_rejected,
            "near_domain_unsupported_rejection": near_rate,
            "out_of_domain_rejected": ood_rejected,
            "out_of_domain_rejection": ood_rate,
            "false_routes": false_routes,
            "false_route_rate": false_rate,
            "authority_violations": authority_violations,
            "execution_errors": 0,
            "negative_veto_total": negative_veto_total,
            "negative_veto_correct_supported": negative_veto_correct_supported,
            "negative_veto_unsupported": negative_veto_unsupported,
            "rescued_correct_supported": rescued_correct_supported,
            "rescued_wrong_supported": rescued_wrong_supported,
            "rescued_unsupported": rescued_unsupported,
            "promotion_gate_pass": promotion_gate_pass,
        },
        "per_language": per_language,
        "per_expected_route": per_route,
        "per_unsupported_family": per_family,
        "rows": rows,
        "policy": {
            "offline_artifact_composition_only": True,
            "new_model_inference": False,
            "failed_270_fresh_used": False,
            "failed_287_fresh_used": False,
            "calibration_or_blind_used": False,
            "rank2_fallback": False,
            "negative_vetoed_base_accepts_rescue_eligible": False,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gte-analysis", type=Path, required=True)
    parser.add_argument("--negative-analysis", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = _load_json(args.manifest)
    gte_analysis = _load_json(args.gte_analysis)
    negative_analysis = _load_json(args.negative_analysis)
    result = compose(gte_analysis, negative_analysis, manifest)

    expected = manifest.get("design_expectation", {})
    for key in (
        "supported_exact_route_accuracy",
        "near_domain_unsupported_rejection",
        "out_of_domain_rejection",
        "false_route_rate",
    ):
        if key in expected:
            actual = float(result["summary"][key])
            target = float(expected[key])
            if not math.isclose(actual, target, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(
                    f"design expectation mismatch for {key}: "
                    f"expected {target}, got {actual}"
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
