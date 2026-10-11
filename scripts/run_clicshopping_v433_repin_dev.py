"""Offline *development-only* paired preselection comparison for ClicShopping 8ada7f1.

Old visible 32-query suite is unchanged, and 10 prospective visible queries
exercise newly source-verified customerOrders. No claim of held-out independence,
actual ClicShopping HTTP/auth execution, or native router performance is made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.run_clicshopping_v433_dev import (
    PACKAGE,
    build_router,
    canonical_bytes,
    eligible_catalog as historical_eligible_catalog,
    load_json,
    validate_cases,
)
from scripts.validate_clicshopping_v433_inventory import validate_inventory

PIN_NEW = "8ada7f1f392f3dd2800e825dac8d245dfd53944a"
PIN_OLD = "3bac851759234a4babb49d3f351e472cd9e0f31f"
NEW_CASES = "visible-dev-repin-cases-8ada7f1.json"
MANIFEST = "maintainer-repin-8ada7f1.json"
OLD_CASES = "dev-cases.json"



# Upstream CustomerOrdersPermissions.php requires update_data for cancellation,
# but create_data for messaging. The historical DEV benchmark used a single
# (create OR update) gate across all write actions. That is observationally
# equivalent on its frozen 3 roles, but unsafe for role-split test scenarios.
CUSTOMER_ORDERS_WRITE_GRANTS = {
    "customerOrders.cancel_order": "update_data",
    "customerOrders.send_message": "create_data",
}


def eligible_catalog(
    inventory: dict, role: dict[str, bool]
) -> list[dict[str, Any]]:
    """Conservatively retain source-specific CustomerOrders write grants."""
    original = historical_eligible_catalog(inventory, role)
    return [
        route
        for route in original
        if (
            (grant := CUSTOMER_ORDERS_WRITE_GRANTS.get(route["route"])) is None
            or role.get(grant, False)
        )
    ]


def pin_new_inventory(old: dict, transition: dict) -> dict:
    """Construct prospective source catalog; NEVER mutate the old DEV inventory."""
    errors = validate_inventory(old)
    if errors:
        raise ValueError("invalid historical source: " + "; ".join(errors))
    if (old["upstream"]["commit"] != PIN_OLD
            or transition.get("historical_dev_pin") != PIN_OLD
            or transition.get("new_source_pin") != PIN_NEW):
        raise ValueError("source revision transition mismatch")
    safety = transition["source_verification"]
    if (safety.get("heldout_approved") is not False
            or safety.get("offline_only") is not True
            or safety.get("live_endpoint_calls") != 0
            or safety.get("model_calls") != 0):
        raise ValueError("unapproved evidence level or live data usage")
    target = deepcopy(old)
    target["upstream"]["commit"] = PIN_NEW
    orders = target["endpoints"]["customerOrders"]
    if (orders["status"] != "permissions_only_unverified_endpoint"
            or orders["page_source"]["present"] is not False):
        raise ValueError("historical customerOrders absence cannot be rewritten")
    details = transition["new_customer_orders_page"]
    if (set(details["read_actions"]) != set(orders["read_actions"])
            or set(details["write_actions"]) != set(orders["write_actions"])):
        raise ValueError("new dispatch does not match historical permission actions")
    orders["page_source"] = {
        "path": details["path"],
        "present": True,
        "git_blob_sha": details["git_blob_sha"],
    }
    orders["status"] = "page_and_permissions_verified"
    orders["dispatch_actions"] = sorted(
        set(orders["read_actions"]) | set(orders["write_actions"])
    )
    orders["authentication_scope"] = (
        "Authenticated trusted CRM/ERP supplies customer_id; "
        "static audit cannot validate runtime tenant enforcement."
    )
    target["comparison"]["status"] = "development_fixture_only_not_scored_heldout"
    return target


def validate_repin_cases(fixture: dict, original: dict, prospect: dict) -> None:
    """Pre-run sanity check; not external approval or independence proof."""
    if fixture.get("schema_version") != 1:
        raise ValueError("invalid prospective fixture schema")
    if (fixture.get("pinned_upstream_commit") != PIN_NEW
            or fixture.get("historical_dev_pin") != PIN_OLD
            or fixture.get("evidence_role")
            != "new_visible_development_cases_not_independent_confirmation"
            or fixture.get("independent_cases") is not False):
        raise ValueError("prospective cases lack accurate provenance")
    if (fixture.get("top_k") != original["protocol"]["top_k"]
            or fixture.get("hot_repeats") != original["protocol"]["hot_repeats"]
            or fixture.get("model_calls") != 0 or fixture.get("live_requests") != 0):
        raise ValueError("development measurement protocol changed")
    ids: set[str] = set()
    counts = {"supported": 0, "forbidden": 0, "unsupported": 0, "ambiguous": 0}
    old_ids = {x["id"] for x in original["cases"]}
    for case in fixture["cases"]:
        ident = case["id"]
        if (not isinstance(ident, str) or not ident.startswith("clic433r-")
                or ident in ids or ident in old_ids):
            raise ValueError("duplicate or reused case identity")
        ids.add(ident)
        label = case["label"]
        if label not in counts:
            raise ValueError("invalid prospective case label")
        counts[label] += 1
        role = original["roles"].get(case["role"])
        if role is None:
            raise ValueError("unknown frozen role")
        catalog = {x["route"] for x in eligible_catalog(prospect, role)}
        required = case.get("required_routes", [])
        forbidden = case.get("forbidden_routes", [])
        ambiguous = case.get("ambiguous_routes", [])
        if label == "supported":
            if len(required) != 1 or required[0] not in catalog:
                raise ValueError("supported route is not source-verified and eligible")
        elif required:
            raise ValueError("unexpected scored supported route")
        if label == "forbidden":
            if len(forbidden) != 1 or forbidden[0] in catalog:
                raise ValueError("forbidden route unexpectedly eligible")
        elif forbidden:
            raise ValueError("unexpected forbidden route")
        if label == "ambiguous":
            if len(ambiguous) < 2 or not set(ambiguous) <= catalog:
                raise ValueError("invalid ambiguous alternative routes")
        elif ambiguous:
            raise ValueError("unexpected ambiguity targets")
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError("empty development query")
    if fixture["counts"] != {"total": len(ids), **counts}:
        raise ValueError("prospective case counts drift")


def evaluate(
    inventory: dict, fixture: dict, *, suite: str, repeats: int, top_k: int
) -> dict:
    """Full permission-filtered *exposure* vs real SchemaRouter.retrieve Top-K."""
    catalogs: dict[str, list[dict[str, Any]]] = {}
    routers: dict[str, Any] = {}
    for role_name, grants in fixture["roles"].items():
        catalog = eligible_catalog(inventory, grants)
        catalogs[role_name] = catalog
        router = build_router(catalog) if catalog else None
        if router is not None:
            router.retrieve("__warmup_dev_only__", k=1)
        routers[role_name] = router
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        catalog = catalogs[case["role"]]
        candidates = {item["route"]: item for item in catalog}
        full_bytes = canonical_bytes(catalog)
        full_times: list[float] = []
        for _ in range(repeats):
            start = time.perf_counter()
            canonical_bytes(catalog)
            full_times.append((time.perf_counter() - start) * 1000)
        router = routers[case["role"]]
        selected: list[str] = []
        selected_times: list[float] = []
        if router is not None:
            router.retrieve(case["query"], k=top_k)
            for _ in range(repeats):
                start = time.perf_counter()
                response = router.retrieve(case["query"], k=top_k)
                selected = [
                    f"{candidate.tool}.{candidate.endpoint}"
                    for candidate in response.candidates
                ]
                if (len(selected) != len(set(selected))
                        or not set(selected) <= candidates.keys()):
                    raise ValueError("router selected duplicate or unauthorized route")
                canonical_bytes([candidates[r] for r in selected])
                selected_times.append((time.perf_counter() - start) * 1000)
        else:
            selected_times = [0.0] * repeats
        label = case["label"]
        required = set(case.get("required_routes", []))
        denied = set(case.get("forbidden_routes", []))
        alternatives = set(case.get("ambiguous_routes", []))
        results.append({
            "id": case["id"],
            "role": case["role"],
            "label": label,
            "eligible_full_routes": len(catalog),
            "selected_routes": selected,
            "required_present": (
                bool(required <= set(selected)) if label == "supported" else None
            ),
            "forbidden_exposed": (
                bool(denied & set(selected)) if label == "forbidden" else None
            ),
            "unsupported_nonempty": (
                bool(selected) if label == "unsupported" else None
            ),
            "ambiguous_candidates": (
                sorted(alternatives & set(selected)) if label == "ambiguous"
                else None
            ),
            "full_normalized_bytes": full_bytes,
            "preselected_normalized_bytes": canonical_bytes(
                [candidates[r] for r in selected]
            ),
            "baseline_serialization_ms_p50": statistics.median(full_times),
            "retrieval_plus_serialization_ms_p50": statistics.median(
                selected_times
            ),
        })
    supported = [x for x in results if x["label"] == "supported"]
    denied = [x for x in results if x["label"] == "forbidden"]
    unsupported = [x for x in results if x["label"] == "unsupported"]
    included = [x for x in results if x["full_normalized_bytes"]]
    return {
        "suite": suite,
        "case_count": len(results),
        "counts": fixture["counts"],
        "summary": {
            "supported_route_recall_at_k": (
                sum(x["required_present"] for x in supported) / len(supported)
                if supported else None
            ),
            "supported_route_hits": sum(x["required_present"] for x in supported),
            "supported_route_total": len(supported),
            "forbidden_exposures": sum(x["forbidden_exposed"] for x in denied),
            "unsupported_nonempty_fraction": (
                sum(x["unsupported_nonempty"] for x in unsupported)
                / len(unsupported) if unsupported else None
            ),
            "mean_normalized_exposure_ratio": (
                statistics.mean(
                    x["preselected_normalized_bytes"] / x["full_normalized_bytes"]
                    for x in included
                ) if included else None
            ),
            "median_full_serialization_ms": statistics.median(
                x["baseline_serialization_ms_p50"] for x in results
            ),
            "median_preselection_plus_serialization_ms": statistics.median(
                x["retrieval_plus_serialization_ms_p50"] for x in results
            ),
        },
        "per_case": results,
    }


def run(package: Path = PACKAGE) -> dict:
    old = load_json(package / "source-inventory.json")
    historic_cases = load_json(package / OLD_CASES)
    transition = load_json(package / MANIFEST)
    new_cases = load_json(package / NEW_CASES)
    validate_cases(historic_cases, old)
    new_inventory = pin_new_inventory(old, transition)
    validate_repin_cases(new_cases, historic_cases, new_inventory)
    old_enriched = deepcopy(historic_cases)
    fresh_enriched = deepcopy(new_cases)
    fresh_enriched["roles"] = deepcopy(historic_cases["roles"])
    top_k = new_cases["top_k"]
    repeats = new_cases["hot_repeats"]
    original_sha = hashlib.sha256(
        (package / OLD_CASES).read_bytes()
    ).hexdigest()
    new_sha = hashlib.sha256((package / NEW_CASES).read_bytes()).hexdigest()
    source_sha = hashlib.sha256((package / MANIFEST).read_bytes()).hexdigest()
    return {
        "status": "development_only_not_independent_heldout",
        "source_pin": PIN_NEW,
        "historical_dev_pin": PIN_OLD,
        "source_transition_sha256": source_sha,
        "original_dev_queries_sha256": original_sha,
        "new_visible_dev_queries_sha256": new_sha,
        "top_k": top_k,
        "hot_repeats": repeats,
        "model_calls": 0,
        "live_requests": 0,
        "native_rest_execution": False,
        "independent_confirmation": False,
        "customer_id_runtime_scope_verified": False,
        "field_recall": None,
        "native_rest_wire_bytes": None,
        "native_endpoint_router_score": None,
        "native_baseline": "all permission-eligible REST endpoint/action metadata",
        "cohorts": [
            evaluate(
                new_inventory, old_enriched, suite="32_unchanged_visible_dev_queries",
                repeats=repeats, top_k=top_k,
            ),
            evaluate(
                new_inventory, fresh_enriched,
                suite="10_new_visible_customerorders_dev_queries",
                repeats=repeats, top_k=top_k,
            ),
        ],
        "limitations": [
            "Visible, locally authored DEV cases, NOT independent confirmation.",
            "Original 32 DEV labels/queries unchanged; new 10 cases are not held out.",
            "Top-3 route-level recall is measured, not agent task completion.",
            "Full catalog exposure is not an upstream native routing model.",
            "Context is normalized JSON metadata, not native REST wire bytes.",
            "No live authentication, tenant enforcement, ClicShopping HTTP or PHP.",
            "No comparable output-field labels; do not report field recall.",
            "Observed results must not be used to retune query labels or Top-K.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package", type=Path, default=PACKAGE)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    report = run(args.package)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for x in report["cohorts"]:
        print(json.dumps({
            "suite": x["suite"], "counts": x["counts"], "summary": x["summary"]
        }, sort_keys=True))
    print("DEV-only; no independent held-out, native ranking or execution claim.")


if __name__ == "__main__":
    main()
