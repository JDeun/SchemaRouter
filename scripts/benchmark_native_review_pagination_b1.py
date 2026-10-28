"""B1 native schema review paging cost, public synthetic source only.

Measures the ACTUAL prepared-session API. No provider, model, records or
independent ranking gold are involved. This is an E0 source-index benchmark.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict
from math import ceil
from statistics import fmean
from time import perf_counter_ns, process_time_ns
from typing import Any

from schemarouter import PrincipalContext, SchemaFieldRoutingSession
from scripts.benchmark_native_fork_fieldgroup_e0 import ACTOR, build_fixture

EVIDENCE = "SOURCE_OWNED_SYNTHETIC_REVIEW_B1_DEV"


def _linux_peak_rss_kib() -> int | None:
    """Linux ru_maxrss reports process-lifetime peak KiB; other OSes omit it."""
    if sys.platform != "linux":
        return None
    import resource

    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _percentiles(samples: list[float]) -> dict[str, float]:
    if not samples:
        raise ValueError("no actual page measurements")
    ordered = sorted(samples)
    return {
        "p50": round(ordered[ceil(len(ordered) * .50) - 1], 4),
        "p95": round(ordered[ceil(len(ordered) * .95) - 1], 4),
        "p99": round(ordered[ceil(len(ordered) * .99) - 1], 4),
        "mean": round(fmean(ordered), 4),
        "max": round(ordered[-1], 4),
    }


def benchmark_review_pages(
    session: SchemaFieldRoutingSession,
    *,
    principal: PrincipalContext,
    limit: int = 32,
) -> dict[str, Any]:
    """Measure all valid review pages, checking no duplicate cursor output."""
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("bounded public review page size required")
    cursor = None
    seen: set[str] = set()
    last_route: str | None = None
    # Linux ru_maxrss is process peak KiB, not an isolated allocation delta.
    peak_rss_before_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    wall_ms: list[float] = []
    cpu_ms: list[float] = []
    serialized_bytes = 0
    for _ in range(session.indexed_route_count + 1):
        wall_start = perf_counter_ns()
        cpu_start = process_time_ns()
        page = session.inspect_visible_fields(
            principal=principal, after_route=cursor, limit=limit,
        )
        cpu_ms.append((process_time_ns() - cpu_start) / 1_000_000)
        wall_ms.append((perf_counter_ns() - wall_start) / 1_000_000)
        if page.snapshot_id != session.snapshot_id or page.executable_authority:
            raise RuntimeError("review benchmark received untrusted page")
        if len(page.routes) > limit:
            raise RuntimeError("review benchmark received overwide page")
        for route in page.routes:
            if route.route_id in seen or (
                last_route is not None and route.route_id <= last_route
            ):
                raise RuntimeError("review benchmark duplicate/unordered route")
            seen.add(route.route_id)
            last_route = route.route_id
        serialized_bytes += len(json.dumps(
            asdict(page), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"))
        if page.next_after_route is None:
            break
        if page.next_after_route == cursor or not page.routes:
            raise RuntimeError("review benchmark cursor made no progress")
        cursor = page.next_after_route
    else:
        raise RuntimeError("review benchmark exceeded indexed source route budget")

    return {
        "provenance": EVIDENCE,
        "source_snapshot": session.snapshot_id,
        "process_peak_rss_before_kib": peak_rss_before_kib,
        "process_peak_rss_after_kib": _linux_peak_rss_kib(),
        "source_route_count": session.indexed_route_count,
        "reviewed_route_count": len(seen),
        "requested_page_size": limit,
        "page_count": len(wall_ms),
        "serialized_page_bytes": serialized_bytes,
        "page_latency_ms": _percentiles(wall_ms),
        "page_cpu_ms": _percentiles(cpu_ms),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=int, choices=(500, 5000), default=5000)
    parser.add_argument("--limit", type=int, choices=(8, 16, 32, 64), default=64)
    args = parser.parse_args()
    router = build_fixture(args.routes)
    session = router.prepare_field_routing()
    report = benchmark_review_pages(session, principal=ACTOR, limit=args.limit)
    print(json.dumps({
        **report,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "evidence_tier": "E0_SYNTHETIC_NOT_PUBLISHER_E2",
        "rss_unit": "KiB (Linux ru_maxrss; process lifetime peak)",
        "measurement_runs": 1,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
