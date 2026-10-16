"""New manual current-adapter, principal and required-field DEV scorer (#1412).

Offline-only typed registration runs the *current* OpenAPI and MCP parsers
alongside native typed DB/vector/graph capabilities, then invokes the public
SchemaRouter.retrieve_authorized() API. No external requests or execution.
The locally authored cases are DEV, not a blinded independent test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import (
    LANGUAGES,
    PROVIDERS,
    SOURCE_CLASS,
    authored_tasks,
    principal,
    router_and_policy,
)
from schemarouter import PlanRequest
from scripts.research_current_main_multilingual_dev import encoded

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "benchmarks/current_adapter_field_scope_dev_v1.py",
    "scripts/research_current_adapter_field_scope_dev.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/planner.py",
    "src/schemarouter/authorization.py",
    "src/schemarouter/adapters/openapi.py",
    "src/schemarouter/adapters/mcp.py",
)
TRUTH = {
    "case_origin": SOURCE_CLASS,
    "source_is_live_real_providers": False,
    "auth_principal_authenticated_by_host": False,
    "principal_visibility_via_current_router": True,
    "field_gold_independently_audited": False,
    "agent_task_success_measured": False,
    "executed_tools": 0,
    "independent_confirmation": False,
    "may_promote_to_product": False,
    "may_release": False,
}


def validate_gold(task: dict[str, Any], existing: dict[str, Any], policy: Any) -> None:
    if task["language"] not in LANGUAGES or task["role"] not in ("viewer", "editor"):
        raise ValueError("unregistered DEV language or principal")
    gold = task["gold_route"]
    fields = task["gold_fields"]
    if not isinstance(fields, list) or len(fields) != len(set(fields)):
        raise ValueError("duplicate or invalid declared required fields")
    if gold is None:
        if fields:
            raise ValueError("unsupported case must not have required fields")
        return
    if gold not in existing:
        raise ValueError("gold capability absent from current parsed registry")
    tool, endpoint = existing[gold]
    if not policy.visible(principal(task["role"]), tool, endpoint):
        raise ValueError("gold capability not eligible for declared principal")
    exposed_fields = {field.name for field in endpoint.output_fields}
    if not set(fields) <= exposed_fields:
        raise ValueError("field gold not supported by parsed typed contract")


def evaluate(k: int = 5) -> dict[str, Any]:
    if type(k) is not int or k not in (3, 5, 10):
        raise ValueError("nonregistered DEV candidate exposure")
    router, policy = router_and_policy()
    tools = router.registry.tools()
    existing = {
        f"{tool.key}.{endpoint.name}": (tool, endpoint)
        for tool in tools for endpoint in tool.endpoints
    }
    if len(existing) != 10:
        raise ValueError("parsed protocol/typed registry changed unexpectedly")
    providers = {tool.provider for tool in tools if tool.provider is not None}
    if not set(PROVIDERS[2:]) <= providers:
        raise ValueError("missing native DB/vector/graph provider categories")
    if not any(tool.execution_metadata.get("adapter") == "openapi" for tool in tools):
        raise ValueError("OpenAPI adapter output absent")
    if not any(tool.execution_metadata.get("adapter") == "mcp" for tool in tools):
        raise ValueError("MCP adapter output absent")
    tasks = authored_tasks()
    if len(tasks) != 27 or len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("local query-disjoint development cohort drift")
    rows = []
    for task in tasks:
        validate_gold(task, existing, policy)
        who = principal(task["role"])
        eligible_routes = {
            route for route, (tool, endpoint) in existing.items()
            if policy.visible(who, tool, endpoint)
        }
        started = time.perf_counter_ns()
        retrieved = router.retrieve_authorized(
            PlanRequest(query=task["query"]), principal=who, k=k,
        )
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        candidates = retrieved.candidates
        chosen = [c.route_id for c in candidates]
        if (
            len(chosen) != len(set(chosen))
            or len(chosen) > k
            or not set(chosen) <= eligible_routes
        ):
            raise ValueError("unauthorized or duplicate candidate escaped current router")
        # Don't use reference gold in retrieval/authorization/ranking: score
        # it only AFTER the authorized shortlist is returned.
        gold = task["gold_route"]
        match = next((c for c in candidates if c.route_id == gold), None)
        found = bool(gold and match is not None)
        fields_found = set(task["gold_fields"]) & (
            {field.name for field in match.output_fields}
            if match is not None else set()
        )
        rows.append({
            "task_id": task["id"], "language": task["language"],
            "scenario": task["scenario"], "role": task["role"],
            "required_route": gold,
            "required_fields": task["gold_fields"],
            "selected_route_ids": chosen,
            "required_route_found": found,
            "required_fields_found": sorted(fields_found),
            "missing_required_fields": sorted(set(task["gold_fields"]) - fields_found),
            "unauthorized_candidate_count": 0,
            "unsupported_nonempty_shortlist": gold is None and bool(chosen),
            "retrieval_ms": round(elapsed, 6),
        })
    def summary(group: list[dict[str, Any]]) -> dict[str, Any]:
        supported = [r for r in group if r["required_route"] is not None]
        fields = sum(len(r["required_fields"]) for r in supported)
        return {
            "cases": len(group),
            "supported_cases": len(supported),
            "required_tool_recall": (
                sum(r["required_route_found"] for r in supported) / len(supported)
                if supported else None
            ),
            "required_field_recall": (
                sum(len(r["required_fields_found"]) for r in supported) / fields
                if fields else None
            ),
            "unsupported_nonempty_shortlist_count": sum(
                r["unsupported_nonempty_shortlist"] for r in group
            ),
            "unauthorized_retrievals": sum(
                r["unauthorized_candidate_count"] for r in group
            ),
            "request_p95_ms": (
                round(sorted(r["retrieval_ms"] for r in group)[
                    max(0, math.ceil(len(group) * 0.95) - 1)
                ], 6) if group else None
            ),
        }
    sources = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCE_FILES
    }
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        text=True, capture_output=True, check=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "hand_authorized_multisource_typed_field_dev_v1",
        "scope": TRUTH.copy(),
        "source_commit": sha,
        "source_file_sha256": sources,
        "dev_cases_sha256": hashlib.sha256(encoded(tasks)).hexdigest(),
        "k": k,
        "route_count": len(existing),
        "tool_count": len(tools),
        "protocol_adapters": ["openapi", "mcp"],
        "native_schema_sources": list(PROVIDERS[2:]),
        "global": summary(rows),
        "languages": {language: summary([
            row for row in rows if row["language"] == language
        ]) for language in LANGUAGES},
        "principal_roles": {role: summary([
            row for row in rows if row["role"] == role
        ]) for role in ("viewer", "editor")},
        "raw_dev_cases": rows,
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, choices=(3, 5, 10), default=5)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = evaluate(args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for lang, result in report["languages"].items():
        print(json.dumps({
            "language": lang,
            "route_recall": result["required_tool_recall"],
            "required_field_recall": result["required_field_recall"],
            "unauthorized_retrievals": result["unauthorized_retrievals"],
        }))
    print(json.dumps({
        "status": SOURCE_CLASS,
        "cases": len(report["raw_dev_cases"]),
        "actual_protocol_adapters": 2,
        "independent": False,
        "agent": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
