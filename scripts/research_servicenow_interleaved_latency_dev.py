"""Source-pinned, interleaved ServiceNow request-latency DEV experiment.

Measures actual per-request HOT selection + canonical native contract exposure.
This is NOT independent heldout scoring or an end-to-end ServiceNow benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

import schemarouter as schemarouter_package
from schemarouter import SchemaRouter
from schemarouter.adapters.mcp import tool_from_mcp
from scripts.external_validation_provenance import implementation_provenance
from scripts.external_validation_servicenow_platform_mcp import validate_package

ARMS = ("static_readonly", "schemarouter_k3", "schemarouter_k5")
SAMPLE_KEYS = frozenset({
    "case_id", "iteration", "arm", "order_position", "latency_ms",
    "candidate_tools", "contract_sha256", "visible_schema_bytes",
})


def canonical(data: Any) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def percentile(values: list[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("nonempty timing samples and valid probability required")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (
        ordered[upper] - ordered[lower]
    ) * (position - lower)


def schedule(case_ids: list[str], repeats: int, seed: int):
    """Interleave arms for every case; rotate orders across hot repetitions."""
    if (not case_ids or len(set(case_ids)) != len(case_ids)
            or type(repeats) is not int or repeats < 1
            or type(seed) is not int):
        raise ValueError("invalid interleaved schedule")
    rng = random.Random(seed)
    for iteration in range(repeats):
        shuffled = list(case_ids)
        rng.shuffle(shuffled)
        for case_id in shuffled:
            # Each case sees each order position >= floor(repeats/3) times.
            offset = (iteration + case_ids.index(case_id)) % len(ARMS)
            for order_position in range(len(ARMS)):
                yield (
                    case_id, iteration,
                    ARMS[(offset + order_position) % len(ARMS)],
                    order_position,
                )


def validate_samples(
    samples: list[dict[str, Any]],
    cases: dict[str, Any],
    snapshot: dict[str, Any],
    repeats: int,
    seed: int,
) -> None:
    """Fail closed on missing/forged trial identities and native contracts."""
    case_map = {case["id"]: case for case in cases["cases"]}
    names = [tool["name"] for tool in snapshot["tools"]]
    tool_map = {tool["name"]: tool for tool in snapshot["tools"]}
    expected = list(schedule(list(case_map), repeats, seed))
    if not isinstance(samples, list) or len(samples) != len(expected):
        raise ValueError("request-level sample cardinality changed")
    for row, (case_id, iteration, arm, position) in zip(
        samples, expected, strict=True,
    ):
        if not isinstance(row, dict) or set(row) != SAMPLE_KEYS:
            raise ValueError("invalid request-level sample structure")
        if (row["case_id"], row["iteration"], row["arm"], row["order_position"]) != (
            case_id, iteration, arm, position
        ):
            raise ValueError("request-level schedule identity changed")
        duration = row["latency_ms"]
        if (type(duration) not in (int, float)
                or not math.isfinite(duration) or duration < 0):
            raise ValueError("invalid request-level latency")
        selected = row["candidate_tools"]
        if (not isinstance(selected, list)
                or any(type(name) is not str for name in selected)
                or len(selected) != len(set(selected))
                or set(selected) - set(tool_map)):
            raise ValueError("invalid source-native candidate identity")
        if arm == "static_readonly" and selected != names:
            raise ValueError("static condition must expose full readonly package")
        if arm != "static_readonly" and len(selected) > (3 if arm.endswith("k3") else 5):
            raise ValueError("preselection exceeds preregistered width")
        visible = canonical([tool_map[name] for name in selected])
        if (type(row["visible_schema_bytes"]) is not int
                or row["visible_schema_bytes"] != len(visible)
                or row["contract_sha256"] != hashlib.sha256(visible).hexdigest()):
            raise ValueError("visible contract provenance changed")


def summarize(
    samples: list[dict[str, Any]],
    cases: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    cases_by_id = {case["id"]: case for case in cases["cases"]}
    tools = {tool["name"]: tool for tool in snapshot["tools"]}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in samples:
        groups[row["arm"]].append(row)
    summary: dict[str, Any] = {}
    for arm in ARMS:
        rows = groups[arm]
        case_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            case_groups[row["case_id"]].append(row)
        medians = [
            median([r["latency_ms"] for r in case_groups[case_id]])
            for case_id in cases_by_id
        ]
        supported = [
            case for case in cases_by_id.values()
            if case["label"] == "supported"
        ]
        negatives = [
            case for case in cases_by_id.values()
            if case["label"] == "unsupported"
        ]
        route_hits = 0
        route_total = 0
        field_hits = 0
        field_total = 0
        for case in supported:
            selected = set(case_groups[case["id"]][0]["candidate_tools"])
            required = set(case["required_tools"])
            route_hits += len(selected & required)
            route_total += len(required)
            for name, required_fields in case["required_fields"].items():
                field_total += len(required_fields)
                if name in selected:
                    native_schema = tools[name].get("inputSchema", {})
                    properties = native_schema.get("properties", {})
                    field_hits += len(set(required_fields) & set(properties))
        nonempty_negatives = sum(
            bool(case_groups[case["id"]][0]["candidate_tools"])
            for case in negatives
        )
        durations = [row["latency_ms"] for row in rows]
        summary[arm] = {
            "request_samples": len(rows),
            "case_count": len(case_groups),
            "request_p50_ms": percentile(durations, 0.5),
            "request_p95_ms": percentile(durations, 0.95),
            "p95_of_per_case_medians_ms_not_request_p95": percentile(medians, 0.95),
            "mean_exposed_contract_bytes": mean(
                row["visible_schema_bytes"] for row in rows
            ),
            "mean_exposed_tool_count": mean(
                len(row["candidate_tools"]) for row in rows
            ),
            "supported_required_tool_recall": route_hits / route_total,
            "supported_required_input_field_recall": field_hits / field_total,
            "unsupported_nonempty_candidate_fraction_not_no_fit": (
                nonempty_negatives / len(negatives)
            ),
        }
    return summary


def run(
    package_dir: Path,
    snapshot_path: Path,
    *,
    repeats: int = 20,
    seed: int = 20261016,
    implementation_revision: str | None = None,
) -> dict[str, Any]:
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case_path = package_dir / manifest["files"]["cases"]
    cases = json.loads(case_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validate_package(manifest, cases, snapshot)
    if repeats != manifest["comparison"]["latency_repeats"] or type(repeats) is not int:
        raise ValueError("repeat count must match published development manifest")
    if type(seed) is not int or seed != 20261016:
        raise ValueError("seed must match prospectively declared DEV schedule")
    if sorted(manifest["comparison"]["development_top_k_sensitivity"]) != [3, 5]:
        raise ValueError("unexpected development widths")

    source = implementation_provenance(
        fixture_reference_revision=manifest["source_revisions"]["schemarouter"],
        explicit_revision=implementation_revision,
        source_path=Path(schemarouter_package.__file__),
        distribution="schemarouter",
    )
    tools = snapshot["tools"]
    tool_map = {tool["name"]: tool for tool in tools}
    router = SchemaRouter()
    started = time.perf_counter_ns()
    router.add_tool(tool_from_mcp(
        "servicenow-platform-mcp", {"tools": tools},
        namespace="external-validation-servicenow-platform-mcp",
    ))
    router.retrieve("__servicenow_index_warmup__", k=1)
    build_ms = (time.perf_counter_ns() - started) / 1_000_000

    case_map = {case["id"]: case for case in cases["cases"]}
    # Measure warmed / steady-state lookups; index build and all query
    # prewarm cost are deliberately excluded and separately disclosed.
    for case in cases["cases"]:
        for width in (3, 5):
            router.retrieve(case["query"], k=width)

    samples: list[dict[str, Any]] = []
    for case_id, iteration, arm, order_position in schedule(
        list(case_map), repeats, seed,
    ):
        query = case_map[case_id]["query"]
        begin = time.perf_counter_ns()
        if arm == "static_readonly":
            names = [tool["name"] for tool in tools]
        else:
            width = 3 if arm == "schemarouter_k3" else 5
            result = router.retrieve(query, k=width)
            names = [candidate.endpoint for candidate in result.candidates]
        visible = canonical([tool_map[name] for name in names])
        duration = (time.perf_counter_ns() - begin) / 1_000_000
        samples.append({
            "case_id": case_id,
            "iteration": iteration,
            "arm": arm,
            "order_position": order_position,
            "latency_ms": duration,
            "candidate_tools": names,
            "contract_sha256": hashlib.sha256(visible).hexdigest(),
            "visible_schema_bytes": len(visible),
        })
    validate_samples(samples, cases, snapshot, repeats, seed)
    return {
        "schema_version": 1,
        "status": "source_pinned_visible_development_not_independent",
        "independent_confirmation": False,
        "performance_evidence_for_commercial_release": False,
        "tool_execution": False,
        "live_service_requests": 0,
        "model_calls": 0,
        "package_id": manifest["package_id"],
        "source_revision": snapshot["source"]["commit"],
        "native_tools_sha256": snapshot["tools_sha256"],
        "manifest_file_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "cases_file_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "implementation": source,
        "protocol": {
            "temperature": None,
            "timing_boundary": (
                "hot local retrieval plus exact native contract JSON "
                "serialization, no execution"
            ),
            "warmup": "all 24 queries under K3 and K5 before sampling",
            "index_build_ms_excluded_from_requests": build_ms,
            "repeats": repeats,
            "seed": seed,
            "primary_width_maintainer_preferred": 5,
            "secondary_width": 3,
            "candidate_schema_count": len(tools),
            "arm_order": "seeded case shuffle per repetition and per-case cyclic arm rotation",
        },
        "summary": summarize(samples, cases, snapshot),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument("--implementation-revision")
    args = parser.parse_args()
    result = run(
        args.package_dir, args.snapshot, repeats=args.repeats, seed=args.seed,
        implementation_revision=args.implementation_revision,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
