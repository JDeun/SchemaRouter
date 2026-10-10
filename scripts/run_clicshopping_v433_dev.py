"""Offline ClicShopping 4.33 development-only endpoint/action comparison.

The 'native' baseline is the entire *eligible public endpoint/action matrix*,
not a fictional MCP tools/list or LLM-based native ranker.  This script neither
contacts ClicShopping nor invokes any tool, model, or credentialed endpoint.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec

try:
    from scripts.validate_clicshopping_v433_inventory import validate_inventory
except ModuleNotFoundError:  # direct CLI execution
    from validate_clicshopping_v433_inventory import validate_inventory

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks/external-validation-clicshopping-v433"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def eligible_catalog(
    inventory: dict[str, Any], role: dict[str, bool]
) -> list[dict[str, Any]]:
    """Compile only ClicShopping-permitted, verified endpoint/action identities."""
    if not role.get("select_data", False):
        return []
    can_write = role.get("create_data", False) or role.get("update_data", False)
    pure_read_only = not any(
        role.get(key, False)
        for key in ("create_data", "update_data", "delete_data", "create_db")
    )
    result: list[dict[str, Any]] = []
    for endpoint, source in inventory["endpoints"].items():
        if source["status"] != "page_and_permissions_verified":
            continue  # CustomerOrdersPermissions is NOT evidence of a callable page.
        if endpoint == "ChatRagBI" and not pure_read_only:
            continue
        for mode, actions in (
            ("read", source["read_actions"]),
            ("write", source["write_actions"] if can_write else []),
        ):
            for action in actions:
                result.append(
                    {
                        "route": f"{endpoint}.{action}",
                        "endpoint": endpoint,
                        "action": action,
                        "mode": mode,
                        "source_blob": source["permission_source"]["git_blob_sha"],
                    }
                )
    return result


def validate_cases(cases: dict[str, Any], inventory: dict[str, Any]) -> None:
    if cases.get("schema_version") != 1:
        raise ValueError("case schema_version must be 1")
    if cases.get("status") != "preregistered_development_only_no_heldout_claim":
        raise ValueError("do not promote development fixture to held-out evidence")
    if cases.get("pinned_upstream_commit") != inventory["upstream"]["commit"]:
        raise ValueError("unmatched source revision")
    settings = cases.get("protocol", {})
    if (settings.get("model_calls") != 0
            or settings.get("upstream_execution") is not False
            or settings.get("network_calls") is not False):
        raise ValueError("offline boundary violated")
    if settings.get("field_recall") != "not_applicable":
        raise ValueError("no native output-field annotations exist")
    top_k = settings.get("top_k")
    repeats = settings.get("hot_repeats")
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("hot_repeats must be a positive integer")
    ids: set[str] = set()
    counts = {"supported": 0, "forbidden": 0, "unsupported": 0, "ambiguous": 0}
    for case in cases["cases"]:
        case_id = case["id"]
        if not isinstance(case_id, str) or case_id in ids:
            raise ValueError("duplicate or invalid case id")
        ids.add(case_id)
        label = case["label"]
        if label not in counts:
            raise ValueError(f"{case_id}: unknown case label")
        counts[label] += 1
        role = cases["roles"].get(case["role"])
        if not isinstance(role, dict) or any(
            type(flag) is not bool for flag in role.values()
        ):
            raise ValueError(f"{case_id}: invalid role")
        if not case.get("query"):
            raise ValueError(f"{case_id}: query is empty")
        eligible = {item["route"] for item in eligible_catalog(inventory, role)}
        required = case.get("required_routes", [])
        forbidden = case.get("forbidden_routes", [])
        ambiguous = case.get("ambiguous_routes", [])
        if any("customerOrders." in route for route in required + ambiguous):
            raise ValueError("unverified customerOrders endpoint in scored targets")
        if label == "supported":
            if len(required) != 1 or required[0] not in eligible:
                raise ValueError(f"{case_id}: supported route is not eligible")
        elif required:
            raise ValueError(f"{case_id}: only supported cases can have required routes")
        if label == "forbidden":
            if len(forbidden) != 1 or forbidden[0] in eligible:
                raise ValueError(f"{case_id}: forbidden action erroneously eligible")
        elif forbidden:
            raise ValueError(f"{case_id}: unexpected forbidden route")
        if label == "ambiguous":
            if len(ambiguous) < 2 or not set(ambiguous) <= eligible:
                raise ValueError(f"{case_id}: ambiguous alternatives invalid")
        elif ambiguous:
            raise ValueError(f"{case_id}: unexpected ambiguous targets")
    if cases["counts"] != {"total": len(ids), **counts}:
        raise ValueError("preregistered counts do not match case matrix")


def build_router(catalog: list[dict[str, Any]]) -> SchemaRouter:
    """Do not inject case labels or manually enriched field annotations."""
    router = SchemaRouter()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in catalog:
        grouped.setdefault(item["endpoint"], []).append(item)
    for endpoint, items in grouped.items():
        router.add_tool(
            ToolSpec(
                name=endpoint,
                provider="clicshopping-4.33-public-source",
                access_mode="api",
                source_type="benchmark_fixture",
                description=f"ClicShopping REST endpoint {endpoint}",
                endpoints=[
                    EndpointSpec(
                        name=item["action"],
                        description=(
                            f"Public action {item['action'].replace('_', ' ')} "
                            f"at REST endpoint {endpoint}"
                        ),
                        read_only=(item["mode"] == "read"),
                    )
                    for item in items
                ],
            )
        )
    return router


def run(package: Path = PACKAGE) -> dict[str, Any]:
    inventory = load_json(package / "source-inventory.json")
    errors = validate_inventory(inventory)
    if errors:
        raise ValueError("invalid pinned upstream inventory: " + "; ".join(errors))
    fixture = load_json(package / "dev-cases.json")
    validate_cases(fixture, inventory)
    top_k = fixture["protocol"]["top_k"]
    repeats = fixture["protocol"]["hot_repeats"]
    catalogs: dict[str, list[dict[str, Any]]] = {}
    routers: dict[str, SchemaRouter | None] = {}
    for role_name, grants in fixture["roles"].items():
        catalogs[role_name] = eligible_catalog(inventory, grants)
        router = build_router(catalogs[role_name]) if catalogs[role_name] else None
        if router is not None:
            router.retrieve("__development_warmup__", k=1)
        routers[role_name] = router

    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        role_name = case["role"]
        catalog = catalogs[role_name]
        route_map = {x["route"]: x for x in catalog}
        # Same normalized source-contract byte representation in both arms.
        full_bytes = canonical_bytes(catalog)
        full_times = []
        for _ in range(repeats):
            start = time.perf_counter()
            canonical_bytes(catalog)
            full_times.append((time.perf_counter() - start) * 1000)
        router = routers[role_name]
        if router is None:
            selected_routes: list[str] = []
            selected_times = [0.0] * repeats
        else:
            router.retrieve(case["query"], k=top_k)  # warmup before timing
            selected_times = []
            selected_routes = []
            for _ in range(repeats):
                start = time.perf_counter()
                response = router.retrieve(case["query"], k=top_k)
                routes = [
                    f"{candidate.tool}.{candidate.endpoint}"
                    for candidate in response.candidates
                ]
                if len(routes) != len(set(routes)):
                    raise ValueError("duplicate selected route")
                if not set(routes) <= route_map.keys():
                    raise ValueError("retrieval exposed an ineligible route")
                canonical_bytes([route_map[name] for name in routes])
                selected_times.append((time.perf_counter() - start) * 1000)
                selected_routes = routes
        selected_contracts = [route_map[name] for name in selected_routes]
        label = case["label"]
        required = set(case.get("required_routes", []))
        blocked = set(case.get("forbidden_routes", []))
        alternatives = set(case.get("ambiguous_routes", []))
        results.append(
            {
                "id": case["id"],
                "role": role_name,
                "label": label,
                "eligible_full_routes": len(catalog),
                "selected_routes": selected_routes,
                "required_present": (
                    bool(required <= set(selected_routes)) if label == "supported" else None
                ),
                "forbidden_exposed": (
                    bool(blocked & set(selected_routes)) if label == "forbidden" else None
                ),
                "unsupported_nonempty": (
                    bool(selected_routes) if label == "unsupported" else None
                ),
                "ambiguous_candidates": (
                    sorted(alternatives & set(selected_routes))
                    if label == "ambiguous" else None
                ),
                "full_normalized_bytes": full_bytes,
                "preselected_normalized_bytes": canonical_bytes(selected_contracts),
                "baseline_serialization_ms_p50": statistics.median(full_times),
                "retrieval_plus_serialization_ms_p50": statistics.median(selected_times),
            }
        )
    supported = [r for r in results if r["label"] == "supported"]
    unsupported = [r for r in results if r["label"] == "unsupported"]
    forbidden = [r for r in results if r["label"] == "forbidden"]
    return {
        "schema_version": 1,
        "status": "development_fixture_only_not_independent_confirmation",
        "upstream_commit": inventory["upstream"]["commit"],
        "native_baseline": (
            "fully eligible source-declared endpoint/action matrix; "
            "no native ranking"
        ),
        "preselection": "SchemaRouter.retrieve over same permission-filtered normalized catalog",
        "field_recall": None,
        "measured_native_wire_bytes": None,
        "model_calls": 0,
        "live_requests": 0,
        "counts": fixture["counts"],
        "summary": {
            "supported_route_recall_at_k": (
                sum(r["required_present"] for r in supported) / len(supported)
                if supported else None
            ),
            "unsupported_nonempty_fraction": (
                sum(r["unsupported_nonempty"] for r in unsupported) / len(unsupported)
                if unsupported else None
            ),
            "forbidden_exposures": sum(r["forbidden_exposed"] for r in forbidden),
            "mean_normalized_exposure_ratio": statistics.mean(
                r["preselected_normalized_bytes"] / r["full_normalized_bytes"]
                for r in results if r["full_normalized_bytes"] > 0
            ),
        },
        "limitations": [
            "Only authored development cases; no held-out or independent confirmation.",
            (
                "No native ClicShopping ranking algorithm was executed; "
                "full eligible matrix is the comparison baseline."
            ),
            (
                "SchemaRouter contract descriptors are compiled from publicly available "
                "endpoint/action identifiers, not live MCP tool schemas."
            ),
            (
                "customerOrders endpoint page is absent at pinned SHA; "
                "permissions-only actions excluded."
            ),
            (
                "No action output-field labels, transport measurements, "
                "authorization execution or application correctness scores."
            ),
            "Do not tune queries, labels, thresholds or descriptions from evaluated rows.",
        ],
        "per_case": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.package)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
