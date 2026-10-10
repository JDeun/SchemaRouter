"""Ensure declined maintainer feedback cannot be presented as benchmark scores."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "benchmarks/external-validation-outreach-decisions.json"


def test_declined_outreach_is_not_scored_evidence() -> None:
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["kind"] == "external-validation-outreach-decisions"
    assert data["evidence_level"] == "outreach_feedback_only"
    assert data["not_product_performance_evidence"] is True
    records = {record["project"]: record for record in data["entries"]}
    assert set(records) == {
        "stacklok/toolhive",
        "Knuckles-Team/agent-utilities",
        "Consiliency/pmcp",
    }
    for record in records.values():
        assert record["decision"].startswith("declined_")
        assert record["tracking_issue"] == 1229
        assert record["external_endorsement"] is False
        assert record["active_joint_benchmark"] is False
        assert record["no_further_solicitation"] is True
        assert record["maintainer_reply"].startswith("https://github.com/")
    assert records["Knuckles-Team/agent-utilities"]["obsolete_comparator"] == (
        "DynamicToolOrchestrator"
    )


def test_public_reply_links_are_in_both_locales() -> None:
    records = json.loads(REGISTER.read_text(encoding="utf-8"))["entries"]
    for docs in ("docs", "docs_ko"):
        content = (
            ROOT / docs / "research/external-validation-freeze.md"
        ).read_text(encoding="utf-8")
        for record in records:
            assert record["maintainer_reply"] in content
        assert "DynamicToolOrchestrator" in content
