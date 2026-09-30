"""Select the frozen #510 runtime from validated candidate evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.qualify_agent_utility_runtime import (  # noqa: E402
    ROSTER,
    roster_exhausted,
    select_runtime,
)
from scripts.validate_agent_utility_v8_qualification_corpus import (  # noqa: E402
    validate_qualification_corpus,
)


def select(
    corpus: dict[str, Any],
    *,
    evidence_dir: Path,
) -> dict[str, Any]:
    validate_qualification_corpus(corpus)
    evidence_by_candidate: dict[str, dict[str, Any]] = {}
    for path in sorted(evidence_dir.rglob("*.json")):
        evidence = json.loads(path.read_text(encoding="utf-8"))
        candidate = str(evidence.get("candidate_model", ""))
        if candidate not in ROSTER:
            continue
        if candidate in evidence_by_candidate:
            raise ValueError(f"duplicate candidate evidence: {candidate}")
        evidence_by_candidate[candidate] = evidence

    selected = select_runtime(
        evidence_by_candidate,
        qualification_corpus=corpus,
    )
    exhausted = roster_exhausted(evidence_by_candidate)

    if selected is None and not exhausted:
        evaluated = [name for name in ROSTER if name in evidence_by_candidate]
        raise ValueError(
            "qualification evidence is an incomplete roster prefix with no "
            f"qualifier: evaluated={evaluated}"
        )

    return {
        "schema_version": 1,
        "issue": 510,
        "source_revision": corpus["source_revision"],
        "corpus_tasks_sha256": corpus["tasks_sha256"],
        "evaluated_candidates": [
            name for name in ROSTER if name in evidence_by_candidate
        ],
        "selected_runtime": selected,
        "roster_exhausted": exhausted,
        "terminal": selected is not None or exhausted,
        "rates_by_candidate": {
            name: evidence_by_candidate[name].get("rates")
            for name in ROSTER
            if name in evidence_by_candidate
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = select(corpus, evidence_dir=args.evidence_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
