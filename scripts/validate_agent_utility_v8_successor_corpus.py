"""Pre-scoring integrity checks for the #510 successor corpus.

Delegates the shape checks to the #506 validator, because the successor's whole
premise is that only the surface and the runtime differ. It adds the one check
that is specific to being a successor: query disjointness from every prior
surface.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_utility_prior_query_guard import (  # noqa: E402
    known_prior_queries,
    normalize_query,
)
from scripts.generate_agent_utility_v8_successor_corpus import (  # noqa: E402
    _506_projection_queries,
    successor_authoring_slots,
)
from scripts.validate_agent_utility_v7_projection_corpus import (  # noqa: E402
    validate as validate_projection_shape,
)


def validate(corpus: dict[str, Any]) -> dict[str, Any]:
    expected_slots = successor_authoring_slots()
    summary = validate_projection_shape(corpus, expected_slots=expected_slots)

    queries = {
        normalize_query(str(task["query"])) for task in corpus["tasks"]
    }
    # See generate_agent_utility_v8_successor_corpus._506_projection_queries:
    # #506 is checked here as a locally built set, not via the guard's
    # registry, so this validator does not depend on #506 being registered
    # in known_prior_queries either.
    forbidden_surfaces = dict(known_prior_queries())
    forbidden_surfaces["projection"] = _506_projection_queries()

    collisions: dict[str, set[str]] = {}
    for name, prior in forbidden_surfaces.items():
        overlap = queries & prior
        if overlap:
            collisions[name] = overlap
    if collisions:
        details = "; ".join(
            f"{name!r} ({len(overlap)} shared queries)"
            for name, overlap in sorted(collisions.items())
        )
        raise SystemExit(
            f"corpus validation failed: overlaps prior surface(s): {details}"
        )

    summary["disjoint_from"] = sorted(forbidden_surfaces)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            validate(json.loads(args.corpus.read_text(encoding="utf-8"))),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
