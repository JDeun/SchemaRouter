"""Score the frozen adaptive-context v1 protocol with deterministic synthetic cases."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from schemarouter.adaptive_context import (  # noqa: E402
    SessionSchemaExposure,
    SuccessfulCapabilityHistory,
    apply_success_prior,
    filter_unexposed_schemas,
)
from schemarouter.models import CapabilityCandidate, CapabilityRetrieval  # noqa: E402

ROOT = Path("benchmarks/adaptive-context-evaluation-v1")
MANIFEST = ROOT / "manifest.json"


def candidate(rank: int, route: str, score: float) -> CapabilityCandidate:
    tool, endpoint = route.split(".", 1)
    return CapabilityCandidate(
        rank=rank,
        route_id=route,
        tool=tool,
        endpoint=endpoint,
        score=score,
        tool_fingerprint=f"{tool}-fp",
        endpoint_fingerprint=f"{endpoint}-fp",
    )


def retrieval() -> CapabilityRetrieval:
    return CapabilityRetrieval(
        query="find current weather",
        registry_version=1,
        requested_k=3,
        total_ranked=3,
        candidates=[
            candidate(1, "search.web", 1.0),
            candidate(2, "weather.current", 0.8),
            candidate(3, "weather.forecast", 0.7),
        ],
    )


def timed(callable_):
    start = time.perf_counter_ns()
    value = callable_()
    return value, (time.perf_counter_ns() - start) / 1_000_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results.json")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    if manifest["status"] != "protocol_frozen_unscored" or manifest["evidence"]["scored"]:
        raise SystemExit("refusing to score a manifest that is not the frozen unscored protocol")

    base = retrieval()
    empty_history = SuccessfulCapabilityHistory()
    cold, cold_ms = timed(lambda: apply_success_prior(base, empty_history, weight=0.5))

    frozen_history = SuccessfulCapabilityHistory()
    frozen_history.record_success(
        "weather", "current", endpoint_fingerprint="current-fp"
    )
    checkpoint = frozen_history.dumps()
    warmed, warm_ms = timed(lambda: apply_success_prior(base, frozen_history, weight=0.5))

    exposure = SessionSchemaExposure()
    first, first_ms = timed(lambda: filter_unexposed_schemas(base, exposure))
    for item in first.candidates:
        exposure.mark_exposed(
            item.tool,
            item.endpoint,
            endpoint_fingerprint=item.endpoint_fingerprint,
        )
    duplicate, duplicate_ms = timed(lambda: filter_unexposed_schemas(base, exposure))
    exposure.compacted()
    recovered, recovery_ms = timed(lambda: filter_unexposed_schemas(base, exposure))

    required = "weather.current"
    rows = {
        "stateless": [item.route_id for item in base.candidates],
        "cold_start": [item.route_id for item in cold.candidates],
        "frozen_history": [item.route_id for item in warmed.candidates],
        "first_exposure": [item.route_id for item in first.candidates],
        "duplicate_exposure": [item.route_id for item in duplicate.candidates],
        "post_compaction": [item.route_id for item in recovered.candidates],
    }
    result = {
        "schema_version": 1,
        "experiment": manifest["experiment"],
        "status": "development_scored",
        "performance_evidence": False,
        "protocol_changed_after_scoring": False,
        "metrics": {
            "cold_start_matches_stateless": rows["cold_start"] == rows["stateless"],
            "frozen_history_checkpoint_unchanged": frozen_history.dumps() == checkpoint,
            "frozen_history_required_tool_rank": rows["frozen_history"].index(required) + 1,
            "stateless_required_tool_rank": rows["stateless"].index(required) + 1,
            "cumulative_schema_candidates_exposed": len(rows["first_exposure"]),
            "duplicate_schema_injections": len(rows["duplicate_exposure"]),
            "post_compaction_recovery": required in rows["post_compaction"],
            "required_tool_recall": float(required in rows["frozen_history"]),
            "required_field_recall": None,
            "unsupported_rejection": None,
            "task_success": None,
            "latency_ms_median": statistics.median(
                [cold_ms, warm_ms, first_ms, duplicate_ms, recovery_ms]
            ),
        },
        "rows": rows,
        "limitations": [
            "Deterministic development scorer only; not held-out evidence.",
            "Required-field recall, unsupported rejection, and end-to-end task success "
            "require a later task corpus.",
            "Timing is diagnostic and environment-dependent.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
