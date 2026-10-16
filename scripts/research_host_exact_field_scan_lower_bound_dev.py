"""Research-only cost lower bound for trusted host field contracts.

This module is NOT a public selector, authorization API, execution gate, or
candidate retrieval replacement. It compares exact declared metadata matching
against the real, much richer full authorized retrieval receipt on the same
source-authored development fixtures. All fast-path outcomes MUST equal the
full public selector on the registered cases or the experiment fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import principal
from benchmarks.current_adapter_scaled_authorized_dev_v1 import (
    DENIED_VIEWER,
    SIZES,
    build_fixture,
)
from schemarouter import (
    HostFieldContract,
    PlanRequest,
    SchemaRouter,
    select_authorized_field_contract,
)

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "ko", "ja")
SOURCE_PATHS = (
    "scripts/research_host_exact_field_scan_lower_bound_dev.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "benchmarks/current_adapter_field_scope_dev_v1.py",
    "src/schemarouter/host_field_contract.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/authorization.py",
)
# Same-author visible DEV expectations, deliberately not a blinded holdout.
CASES = (
    ("invoice", ("invoice_id", "total_amount"), "billing.getInvoice",
     "Read invoice identifier and total amount.",
     "청구서 식별자와 총액을 조회해 주세요.",
     "請求書の識別子と合計金額を取得してください。"),
    ("vector", ("distance", "title"), "vectors.search",
     "Read vector search titles and distances.",
     "벡터 검색 제목과 거리를 읽어주세요.",
     "ベクトル検索のタイトルと距離を取得してください。"),
    ("denied-payment", ("payment_id",), None,
     "Pay invoice as a viewer.",
     "조회 권한으로 청구서를 결제해주세요.",
     "閲覧権限で請求書を支払ってください。"),
    ("absent-field", ("never_published_output",), None,
     "Read a nonexistent field.",
     "존재하지 않는 필드를 읽어주세요.",
     "存在しないフィールドを取得してください。"),
    ("hidden-audit", ("audit_tag",), None,
     "Read hidden audit tag.",
     "숨겨진 감사 태그를 읽어주세요.",
     "非表示の監査タグを取得してください。"),
    ("ambiguous-payload", ("payload",), None,
     "Read common payload.",
     "공통 payload를 읽어주세요.",
     "共通の payload を取得してください。"),
)


def _matches(endpoint: Any, contract: HostFieldContract) -> bool:
    """Only an exact, declared, visible and read-only field conjunction."""
    if endpoint.read_only is not True or endpoint.destructive is True:
        return False
    for required in contract.required_enums:
        found = False
        for parameter in endpoint.parameters:
            if parameter.location != "query" or parameter.name != required.parameter:
                continue
            schema = parameter.json_schema
            values = schema.get("enum") if isinstance(schema, dict) else None
            if isinstance(schema, dict) and schema.get("type") == "array":
                items = schema.get("items")
                values = items.get("enum") if isinstance(items, dict) else None
            if (isinstance(values, list)
                and all(type(value) is str for value in values)
                and required.value in values):
                found = True
                break
        if not found:
            return False
    allowed = {
        label
        for field in endpoint.output_fields
        for label in (field.name, field.semantic_id)
        if label is not None
    }
    return all(field in allowed for field in contract.required_output_fields)


def direct_scan(router: SchemaRouter, who: Any, contract: HostFieldContract) -> dict[str, Any]:
    """Internal read-only DEV comparator; never a product trust boundary.

    Explicit identity and source checks are necessary but NOT sufficient for
    a future production path: dynamic policy, availability and registry
    mutation require dedicated security tests and authority snapshots.
    """
    if router.authorization_policy is None:
        raise ValueError("explicit authorization policy required")
    if contract.operation != "read":
        raise ValueError("read-only trusted contract required")
    policy = router.authorization_policy
    availability = router.planner.availability_predicate
    version = router.registry.version
    available_count = 0
    matches = []
    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            if not policy.visible(who, tool, endpoint):
                continue
            if availability is not None and not availability(tool, endpoint):
                continue
            projected = router._data_scope_endpoint_view(who, tool, endpoint)
            if projected is None:
                continue
            available_count += 1
            if _matches(projected, contract):
                matches.append(f"{tool.key}.{endpoint.name}")
    if (
        version != router.registry.version
        or policy is not router.authorization_policy
        or availability is not router.planner.availability_predicate
    ):
        raise ValueError("scope changed mid-scan")
    if available_count == 0:
        reason = "empty_authorized_catalog"
    elif len(matches) == 0:
        reason = "no_contract_match"
    elif len(matches) > 1:
        reason = "ambiguous_contract_match"
    else:
        reason = "unique_contract_match"
    return {
        "reason": reason,
        "selected_route_id": matches[0] if len(matches) == 1 else None,
        "matching_route_ids": sorted(matches) if len(matches) > 1 else (
            matches if len(matches) == 1 else []
        ),
        "visible_candidate_count": available_count,
    }


def _metrics(values: list[float]) -> dict[str, float | int]:
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("invalid or absent actual CPU times")
    values = sorted(values)
    def at(p: float) -> float:
        return round(values[math.ceil(p * len(values)) - 1], 5)
    return {
        "n": len(values), "p50_ms": at(0.50),
        "p95_ms": at(0.95), "p99_ms": at(0.99),
        "mean_ms": round(sum(values) / len(values), 5),
    }


def assess(*, sizes: tuple[int, ...] = SIZES, repeats: int = 2) -> dict[str, Any]:
    if (type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(n) is not int or n not in SIZES for n in sizes)
        or type(repeats) is not int or not 1 <= repeats <= 3):
        raise ValueError("nonregistered or unbounded DEV experiment")
    if len(CASES) != 6 or len(LANGUAGES) != 3:
        raise ValueError("registered sample shape changed")
    sha = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCE_PATHS
    }
    rows = []
    stats = {}
    for size in sizes:
        router, policy = build_fixture(size)
        who = principal("viewer")
        authorized = {
            f"{tool.key}.{endpoint.name}"
            for tool in router.registry.tools()
            for endpoint in tool.endpoints
            if policy.visible(who, tool, endpoint)
        }
        if len(authorized) != size - len(DENIED_VIEWER):
            raise ValueError("authoritative DEV fixture cardinality changed")

        def no_actions(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("no product planning or tool execution permitted")

        router.execute = no_actions
        router.plan = no_actions

        size_rows = []
        for rep in range(repeats):
            for case_id, fields, expected, *queries in CASES:
                for lang, query in zip(LANGUAGES, queries, strict=True):
                    contract = HostFieldContract(
                        operation="read", required_output_fields=list(fields),
                    )
                    request = PlanRequest(query=query)
                    started = time.perf_counter_ns()
                    retrieved = router.retrieve_authorized(
                        request, principal=who, k=size,
                    )
                    normal_ms = (time.perf_counter_ns() - started) / 1e6
                    if (
                        len(retrieved.candidates) != len(authorized)
                        or {r.route_id for r in retrieved.candidates} != authorized
                        or retrieved.total_ranked != len(authorized)
                        or any(
                            f.name == "audit_tag"
                            for item in retrieved.candidates
                            if item.tool.startswith("bench")
                            for f in item.output_fields
                        )
                    ):
                        raise ValueError("incorrect full authorized retrieval")
                    started = time.perf_counter_ns()
                    real = select_authorized_field_contract(
                        router, request, principal=who,
                        contract=contract, k=size,
                    )
                    real_ms = (time.perf_counter_ns() - started) / 1e6
                    started = time.perf_counter_ns()
                    direct = direct_scan(router, who, contract)
                    scan_ms = (time.perf_counter_ns() - started) / 1e6
                    real_matches = sorted(real.matching_route_ids)
                    if (
                        real.selected_route_id != expected
                        or real.reason != direct["reason"]
                        or real.selected_route_id != direct["selected_route_id"]
                        or real_matches != sorted(direct["matching_route_ids"])
                        or real.candidate_count != direct["visible_candidate_count"]
                        or real.selected_route_id in DENIED_VIEWER
                        or (real.selected_route_id is not None
                            and real.disposition != "selected")
                    ):
                        raise ValueError(
                            f"FULL SELECTOR PARITY FAIL {size}/{case_id}/{lang}"
                        )
                    if case_id == "ambiguous-payload" and (
                        real.reason != "ambiguous_contract_match"
                        or len(real_matches) < 2
                    ):
                        raise ValueError("ambiguous field incorrectly resolved")
                    if case_id != "ambiguous-payload" and (
                        (expected is None and real.reason != "no_contract_match")
                        or (expected is not None
                            and real.reason != "unique_contract_match")
                    ):
                        raise ValueError("missing registered negative/positive case")
                    if any(not math.isfinite(v) or v <= 0
                           for v in (normal_ms, real_ms, scan_ms)):
                        raise ValueError("nonfinite CPU measurement")
                    size_rows.append({
                        "size": size, "repeat": rep, "case": case_id,
                        "language": lang, "normal_full_ms": round(normal_ms, 5),
                        "public_selector_ms": round(real_ms, 5),
                        "direct_scan_ms": round(scan_ms, 5),
                        "reason": real.reason,
                        "selected_route_id": expected,
                        "complete_visible_count": direct["visible_candidate_count"],
                        "matching_authorized_count": len(real_matches),
                    })
        rows.extend(size_rows)
        stats[str(size)] = {
            "cases": len(size_rows),
            "public_selector": _metrics([x["public_selector_ms"] for x in size_rows]),
            "normal_full": _metrics([x["normal_full_ms"] for x in size_rows]),
            "direct_scan": _metrics([x["direct_scan_ms"] for x in size_rows]),
            "parity": True,
        }
    if len(rows) != len(sizes) * repeats * len(CASES) * len(LANGUAGES):
        raise ValueError("missing measurement cells")
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "study": "host_exact_field_scan_lower_bound_dev_v1",
        "schema_version": 1, "checkout_sha": rev, "sources_sha256": sha,
        "sizes": list(sizes), "repeats": repeats, "rows": rows,
        "statistics": stats, "linux_platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "boundaries": {
            "research_only": True, "product_API_modified": False,
            "independent_confirmation": False, "trusted_host_auth_test": False,
            "no_model_or_tool_execution": True,
            "no_new_authorization_or_execution_grant": True,
            "may_release": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    result = assess(repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": result["study"], "statistics": result["statistics"],
        "eligible_for_product": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
