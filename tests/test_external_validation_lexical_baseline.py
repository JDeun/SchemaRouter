from __future__ import annotations

import json
from pathlib import Path

from scripts.run_lexical_external_validation import LexicalIndex

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "benchmarks" / "external-validation-smart-mcp-dev-v1"


def test_lexical_baseline_uses_same_smartmcp_snapshot_surface() -> None:
    snapshot = json.loads(
        (PACKAGE / "smartmcp-snapshot.json").read_text(encoding="utf-8")
    )
    index = LexicalIndex(snapshot)

    cancel = index.search("cancel running computation job", top_k=1)
    assert cancel[0][0]["name"] == "jobs__cancel"

    full_text = index.search("retrieve full text body stored document", top_k=1)
    assert full_text[0][0]["name"] == "documents__full_text"


def test_lexical_baseline_is_deterministic_for_zero_overlap_queries() -> None:
    snapshot = json.loads(
        (PACKAGE / "smartmcp-snapshot.json").read_text(encoding="utf-8")
    )
    index = LexicalIndex(snapshot)

    first = index.search("재즈 화성 진행을 만들어줘", top_k=5)
    second = index.search("재즈 화성 진행을 만들어줘", top_k=5)

    assert [tool["name"] for tool, _ in first] == [
        tool["name"] for tool, _ in second
    ]
