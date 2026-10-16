"""Current-product 100/250/500 authorized host contract CPU performance DEV.

Synthetic OpenAPI/MCP/database/vector/graph catalogs reused from an already
published fixed fixture. No execution, model, live provider, inferred intent,
external task gold, independent benchmark, or release qualification.
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
    select_authorized_field_contract,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "src/schemarouter/host_field_contract.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "benchmarks/current_adapter_scaled_authorized_dev_v1.py",
    "benchmarks/current_adapter_field_scope_dev_v1.py",
    "scripts/research_host_field_contract_scaled_cpu_dev.py",
)
LANGUAGES = ("en", "ko", "ja")
# This is new same-author exploratory DEV labeling. The host contracts are
# supplied in advance; it does NOT test natural-language extraction.
SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "invoice",
        "expected": "billing.getInvoice",
        "fields": ("invoice_id", "total_amount"),
        "queries": (
            "Read the invoice total amount and invoice identifier.",
            "청구서 총액과 청구서 식별자를 읽어주세요.",
            "請求書の合計金額と識別子を読み取ってください。",
        ),
        "expected_reason": "unique_contract_match",
    },
    {
        "id": "vector",
        "expected": "vectors.search",
        "fields": ("distance", "title"),
        "queries": (
            "Retrieve matching vector record titles with distances.",
            "유사 벡터 기록의 제목과 거리를 조회해주세요.",
            "類似ベクトル記録のタイトルと距離を取得してください。",
        ),
        "expected_reason": "unique_contract_match",
    },
    {
        "id": "viewer-denied-payment",
        "expected": None,
        "fields": ("payment_id",),
        "queries": (
            "Pay an invoice using viewer-only privileges.",
            "조회 권한으로 청구서를 결제해주세요.",
            "閲覧権限だけで請求書を支払ってください。",
        ),
        "expected_reason": "no_contract_match",
    },
    {
        "id": "unknown-field",
        "expected": None,
        "fields": ("never_published_output",),
        "queries": (
            "Find an unsupported private telemetry field.",
            "지원하지 않는 내부 원격 측정값을 찾아주세요.",
            "未対応の非公開テレメトリーフィールドを取得して。",
        ),
        "expected_reason": "no_contract_match",
    },
    {
        "id": "hidden-audit",
        "expected": None,
        "fields": ("audit_tag",),
        "queries": (
            "Read a hidden parcel audit tag under viewer permissions.",
            "조회 권한으로 숨긴 택배 감사 태그를 읽어주세요.",
            "閲覧権限で非表示の荷物監査タグを取得してください。",
        ),
        "expected_reason": "no_contract_match",
    },
    {
        "id": "ambiguous-payload",
        "expected": None,
        "fields": ("payload",),
        "queries": (
            "Read a parcel ledger payload without specifying a record.",
            "특정 기록을 선택하지 않고 택배 원장 payload를 읽어주세요.",
            "特定の記録を指定せず荷物台帳の payload を取得して。",
        ),
        "expected_reason": "ambiguous_contract_match",
    },
)
DEFAULT_REPEATS = 5


def _nearest_rank(values: list[float], q: float) -> float:
    if not values or not 0 < q <= 1:
        raise ValueError("percentile needs nonempty positive bounded samples")
    return round(sorted(values)[math.ceil(q * len(values)) - 1], 5)


def _check_result(
    receipt: Any, *, scenario: dict[str, Any], expected_visible: int,
    registry_version: int, width: int,
) -> None:
    if (
        receipt.reason != scenario["expected_reason"]
        or receipt.selected_route_id != scenario["expected"]
        or receipt.registry_version != registry_version
        or receipt.requested_k != width
        or receipt.candidate_count != expected_visible
    ):
        raise ValueError(
            "real public selector disagrees with source-authored typed "
            f"DEV contract: {scenario['id']} got {receipt.model_dump(mode='json')}"
        )
    if receipt.selected_route_id in DENIED_VIEWER or (
        receipt.disposition == "abstained" and receipt.selected_route_id is not None
    ):
        raise ValueError("denied or abstained typed route was promoted")
    if scenario["expected"] is not None and (
        not receipt.selected_tool_fingerprint or
        not receipt.selected_endpoint_fingerprint
    ):
        raise ValueError("selected receipt lacks actual published tool identity")
    if scenario["id"] == "ambiguous-payload" and (
        len(receipt.matching_route_ids) < 2
    ):
        raise ValueError("wrongly collapsed many visible common-field routes")


def _stat(samples: list[float]) -> dict[str, float | int]:
    if not samples or any(not math.isfinite(x) or x < 0 for x in samples):
        raise ValueError("invalid measured CPU timing")
    return {
        "n": len(samples),
        "p50_ms": _nearest_rank(samples, 0.50),
        "p95_ms": _nearest_rank(samples, 0.95),
        "p99_ms": _nearest_rank(samples, 0.99),
        "max_ms": round(max(samples), 5),
        "mean_ms": round(sum(samples) / len(samples), 5),
    }


def assess(
    *, sizes: tuple[int, ...] = SIZES,
    repeats: int = DEFAULT_REPEATS,
) -> dict[str, Any]:
    if (
        type(sizes) is not tuple or not sizes
        or len(set(sizes)) != len(sizes)
        or any(type(s) is not int or s not in SIZES for s in sizes)
        or type(repeats) is not int or not 1 <= repeats <= 8
    ):
        raise ValueError("unregistered or unbounded CPU DEV experiment")
    if len(SCENARIOS) != 6 or set(LANGUAGES) != {"en", "ko", "ja"}:
        raise ValueError("missing preregistered multilingual source cases")
    source_sha256 = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCE_PATHS
    }
    rows: list[dict[str, Any]] = []
    statistics: dict[str, Any] = {}
    for size in sizes:
        router, policy = build_fixture(size)
        viewer = principal("viewer")
        allowed = {
            f"{tool.key}.{endpoint.name}"
            for tool in router.registry.tools()
            for endpoint in tool.endpoints
            if policy.visible(viewer, tool, endpoint)
        }
        # Exactly five existing mutators denied, all synthetic read routes
        # are visible. This is a source-locked role fixture, not host auth.
        if len(allowed) != size - len(DENIED_VIEWER):
            raise ValueError("synthetic authorization cardinality changed")
        scenario_rows: list[dict[str, Any]] = []
        for repeat in range(repeats):
            for scenario in SCENARIOS:
                for lang, query in zip(
                    LANGUAGES, scenario["queries"], strict=True,
                ):
                    structured = HostFieldContract(
                        operation="read",
                        required_output_fields=list(scenario["fields"]),
                    )
                    # Do not reuse a cached retrieved result in new API: it
                    # must exercise the real repeated authorized call.
                    start = time.perf_counter_ns()
                    normal = router.retrieve_authorized(
                        PlanRequest(query=query), principal=viewer, k=size,
                    )
                    normal_ms = (
                        time.perf_counter_ns() - start
                    ) / 1_000_000
                    if (
                        len(normal.candidates) != len(allowed)
                        or normal.total_ranked != len(allowed)
                        or {item.route_id for item in normal.candidates} != allowed
                    ):
                        raise ValueError(
                            "retrieval did not expose whole authorized catalog"
                        )
                    if any(
                        item.route_id in DENIED_VIEWER
                        or (
                            item.route_id.startswith("bench")
                            and any(
                                f.name == "audit_tag"
                                for f in item.output_fields
                            )
                        )
                        for item in normal.candidates
                    ):
                        raise ValueError("current retrieval leaked denied schema")
                    start = time.perf_counter_ns()
                    receipt = select_authorized_field_contract(
                        router, query, principal=viewer,
                        contract=structured, k=size,
                    )
                    elapsed_ms = (
                        time.perf_counter_ns() - start
                    ) / 1_000_000
                    _check_result(
                        receipt, scenario=scenario,
                        expected_visible=len(allowed),
                        registry_version=router.registry.version,
                        width=size,
                    )
                    if (
                        not math.isfinite(elapsed_ms)
                        or not math.isfinite(normal_ms)
                        or min(normal_ms, elapsed_ms) < 0
                    ):
                        raise ValueError("nonfinite CPU time recorded")
                    scenario_rows.append({
                        "size": size, "repeat": repeat,
                        "scenario": scenario["id"], "language": lang,
                        "normal_full_retrieval_ms": round(normal_ms, 5),
                        "host_contract_end_to_end_ms": round(elapsed_ms, 5),
                        "receipt": receipt.model_dump(mode="json"),
                        "no_tools_invoked": True,
                    })
        rows.extend(scenario_rows)
        statistics[str(size)] = {
            "registered_routes": size,
            "viewer_authorized_routes": len(allowed),
            "cases": len(scenario_rows),
            "normal_retrieve_full": _stat([
                x["normal_full_retrieval_ms"] for x in scenario_rows
            ]),
            "host_contract_end_to_end": _stat([
                x["host_contract_end_to_end_ms"] for x in scenario_rows
            ]),
            "by_scenario": {
                scenario["id"]: {
                    "cases": len([r for r in scenario_rows
                                  if r["scenario"] == scenario["id"]]),
                    "host_contract": _stat([
                        r["host_contract_end_to_end_ms"]
                        for r in scenario_rows
                        if r["scenario"] == scenario["id"]
                    ]),
                }
                for scenario in SCENARIOS
            },
            "no_invalid_route_or_wrong_or_unauthorized_selected": all(
                r["receipt"]["selected_route_id"] ==
                next(s["expected"] for s in SCENARIOS
                     if s["id"] == r["scenario"])
                for r in scenario_rows
            ),
        }
    if len(rows) != len(sizes) * repeats * len(SCENARIOS) * len(LANGUAGES):
        raise ValueError("silent lost performance trials")
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "study": "host_scoped_field_contract_product_cpu_scale_dev",
        "repo_commit": rev,
        "source_sha256": source_sha256,
        "sizes": list(sizes), "repeats": repeats,
        "scenarios": [x["id"] for x in SCENARIOS],
        "languages": list(LANGUAGES),
        "statistics": statistics,
        "rows": rows,
        "cpu": platform.platform(),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cpu_count": os.cpu_count(),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "scope": {
            "real_public_host_contract_selector": True,
            "real_current_authorized_adapter_parsers": True,
            "synthetic_provider_descriptions": True,
            "complete_authorized_catalog_checked": True,
            "no_host_intent_inference": True,
            "no_actual_tool_executed": True,
            "authenticated_production_host": False,
            "independent_quality_holdout": False,
            "agent_task_success_test": False,
            "latency_slo_established": False,
            "may_promote_default_or_release": False,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    args = p.parse_args()
    report = assess(repeats=args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "study": report["study"],
        "size_metrics": report["statistics"],
        "may_release": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
