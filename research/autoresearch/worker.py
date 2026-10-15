"""Unprivileged JSONL worker for candidate-only research ranking.

This worker is invoked exclusively in the read-only CPU research workflow.
Candidate Python remains arbitrary code: use only disposable runners without
secrets, writable GitHub tokens, production credentials or sensitive holdouts.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main() -> int:
    # Program path is pinned by the harness; no user-provided executable path.
    candidate_path = Path(__file__).resolve().with_name("candidate.py")
    spec = importlib.util.spec_from_file_location("editable_research_candidate", candidate_path)
    if spec is None or spec.loader is None:
        raise ValueError("missing candidate module loader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    callback = getattr(module, "rerank", None)
    if not callable(callback):
        raise ValueError("candidate must define rerank(query, candidates)")
    for line in sys.stdin:
        request = json.loads(line)
        if not isinstance(request, dict) or set(request) != {"query", "candidates"}:
            raise ValueError("invalid request envelope")
        ranking = callback(request["query"], request["candidates"])
        # Refuse noncanonical payloads at the worker boundary. The trusted
        # parent additionally validates registered ID permutation on return.
        if not isinstance(ranking, list) or any(type(x) is not str for x in ranking):
            raise ValueError("candidate must return list[str] route IDs")
        sys.stdout.write(json.dumps(ranking, ensure_ascii=True, allow_nan=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
