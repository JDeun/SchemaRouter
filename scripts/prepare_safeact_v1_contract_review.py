"""Generate an intentionally INCOMPLETE V1 review worksheet from public IDs only."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CASE_ID = re.compile(r"SAB-V1-[0-9]{3}\Z")


def review_worksheet(public_listing: dict[str, Any]) -> dict[str, Any]:
    """Never copy task content or evaluator fields into trusted contracts."""
    tasks = public_listing.get("tasks")
    if (
        not isinstance(tasks, list)
        or len(tasks) != 131
        or public_listing.get("case_count") != 131
    ):
        raise ValueError("expected exactly 131 official public V1 case IDs")
    ids: set[str] = set()
    for entry in tasks:
        if not isinstance(entry, dict) or entry.get("protocol") != "v1":
            raise ValueError("public listing contains non-V1 task")
        case_id = entry.get("case_id")
        if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
            raise ValueError("invalid public case ID")
        if case_id in ids:
            raise ValueError("duplicate public case ID")
        ids.add(case_id)
    return {
        "kind": "safeact_v1_unreviewed_contract_authoring_worksheet",
        "scored_run_authorized": False,
        "source": "official --list-only V1 public case identifiers only",
        "independent_policy_author_reviewed": False,
        "case_coverage": {case_id: None for case_id in sorted(ids)},
        "contracts": [],
        "note": (
            "Do not populate action contracts or their evidence requirements "
            "from hidden SafeAct evaluator, gold labels, or case manifest. "
            "Review independent public capability and policy sources."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_listing", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    listing = json.loads(args.public_listing.read_text(encoding="utf-8"))
    document = review_worksheet(listing)
    args.out.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Prepared 131 unreviewed public case IDs; scored run remains blocked")


if __name__ == "__main__":
    main()
