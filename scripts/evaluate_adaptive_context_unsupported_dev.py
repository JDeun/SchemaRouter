"""Development-only #840 unsupported-rejection parity audit.

Reuses the frozen Gearlynx shared-catalog no-route cases. The adaptive success prior is
applied only after SchemaRouter's existing unsupported/no-route safeguard, so an empty
accepted candidate set must remain empty regardless of history.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter.adaptive_context import (  # noqa: E402
    SuccessfulCapabilityHistory,
    apply_success_prior,
)
from scripts.external_validation_gearlynx import (  # noqa: E402
    CASES,
    build_router,
    load_catalog,
    schemarouter_search,
)

PRIOR_WEIGHT = 0.5


def evaluate() -> dict[str, Any]:
    fixture = load_catalog()
    tools = fixture["tools"]
    allowed = {tool["name"] for tool in tools}
    router = build_router(tools)
    unsupported = [(query, required) for query, required in CASES if required is None]
    history = SuccessfulCapabilityHistory()
    first_tool = tools[0]["name"]
    history.record_success(first_tool, "invoke")

    rows: list[dict[str, Any]] = []
    for query, _required in unsupported:
        selected = schemarouter_search(router, query, allowed)
        retrieval = router.retrieve(query, k=3)
        accepted = [
            candidate
            for candidate in retrieval.candidates
            if candidate.tool in selected
        ]
        filtered = retrieval.model_copy(update={"candidates": accepted})
        warmed = apply_success_prior(filtered, history, weight=PRIOR_WEIGHT)
        rows.append(
            {
                "query": query,
                "stateless_selected": selected,
                "stateless_rejected": not selected,
                "adaptive_candidates": [candidate.route_id for candidate in warmed.candidates],
                "adaptive_rejected": not warmed.candidates,
            }
        )

    return {
        "schema_version": 1,
        "experiment": "adaptive-context-unsupported-rejection-development-v1",
        "issue": 840,
        "status": "development_scored",
        "performance_evidence": False,
        "source_fixture": "frozen Gearlynx shared-router cases",
        "prior_weight": PRIOR_WEIGHT,
        "unsupported_cases": len(rows),
        "metrics": {
            "stateless_unsupported_rejection": sum(
                row["stateless_rejected"] for row in rows
            )
            / len(rows),
            "adaptive_unsupported_rejection": sum(
                row["adaptive_rejected"] for row in rows
            )
            / len(rows),
        },
        "rows": rows,
        "limitations": [
            "Development-only; not new held-out evidence.",
            "Reuses four frozen Gearlynx no-route cases.",
            "The prior is evaluated after the existing hard rejection safeguard.",
            "This is a rejection-parity safety check, not a routing-quality claim.",
        ],
    }


def main() -> int:
    result = evaluate()
    out = Path("benchmarks/adaptive-context-evaluation-v1/unsupported-rejection-dev.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
