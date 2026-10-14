"""Synthetic tests only; do not use held-out task text or scores as fixtures."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.report_014_heldout_retrieval_language import (
    CANONICAL_TASKS_SHA,
    CATALOGS,
    CONDITIONS,
    FROZEN_SOURCE,
    LANGUAGES,
    audit,
)


def fixture():
    tasks = []
    for language in LANGUAGES:
        for index in range(130):
            supported = index < 100
            tasks.append({
                "semantic_task_id": f"synthetic-{language}-{index:03d}",
                "language": language,
                "task_stratum": "synthetic",
                "supported": supported,
                "required_routes": ["synthetic.route"] if supported else [],
            })
    rows = []
    for task in tasks:
        for catalog in CATALOGS:
            for condition in CONDITIONS:
                supported = task["supported"]
                matched = supported and (
                    condition == "FULL"
                    or condition == "ORACLE"
                    or task["language"] == "en"
                )
                rows.append({
                    "semantic_task_id": task["semantic_task_id"],
                    "task_stratum": task["task_stratum"],
                    "language": task["language"],
                    "supported": supported,
                    "catalog_size": catalog,
                    "condition": condition,
                    "required_count": int(supported),
                    "required_hits": int(matched),
                    "all_required_covered": matched if supported else None,
                })
    corpus = {
        "issue": 432,
        "generator_source_revision": FROZEN_SOURCE,
        "tasks_sha256": CANONICAL_TASKS_SHA,
        "tasks": tasks,
    }
    retrieval = {
        "issue": 432,
        "tasks_sha256": CANONICAL_TASKS_SHA,
        "conditions": list(CONDITIONS),
        "catalog_sizes": list(CATALOGS),
        "rows": rows,
    }
    return corpus, retrieval


def test_audit_uses_weighted_supported_only_recall_and_explicit_null_controls():
    corpus, retrieval = fixture()
    report = audit(corpus, retrieval)
    assert report["retrieval_rows"] == 15600
    assert report["task_count"] == 780
    assert len(report["groups"]) == 120
    def cell(language, condition):
        return next(
            item for item in report["groups"]
            if item["catalog_size"] == 500 and item["language"] == language
            and item["condition"] == condition
        )
    assert cell("ko", "SR-10")["initial_required_route_recall"] == 0
    assert cell("ja", "SR-10")["required"] == 100
    assert cell("en", "SR-10")["initial_required_route_recall"] == 1
    assert cell("ko", "ORACLE")["initial_required_route_recall"] == 1
    assert cell("ko", "SR-10")["supported"] == 100
    assert cell("ko", "SR-10")["unsupported"] == 30
    assert cell("ko", "SR-10")["all_required_coverage_supported"] == 0
    assert "not final-agent" in report["warning"].lower()


@pytest.mark.parametrize("corruption", [
    lambda c, r: r["rows"].pop(),
    lambda c, r: r["rows"].append(deepcopy(r["rows"][0])),
    lambda c, r: r["rows"].__setitem__(1, deepcopy(r["rows"][0])),
    lambda c, r: r["rows"][0].update(language="ko"),
    lambda c, r: r["rows"][0].update(required_hits=100),
    lambda c, r: r["rows"][0].update(all_required_covered=False),
    lambda c, r: r["rows"][0].update(required_count=9),
    lambda c, r: r["rows"][0].update(condition="fabricated"),
    lambda c, r: r["rows"][0].update(supported=False),
    lambda c, r: r.update(tasks_sha256="forged"),
    lambda c, r: c.update(generator_source_revision="retuned"),
    lambda c, r: c["tasks"][0].update(required_routes=[]),
])
def test_audit_rejects_missing_modified_or_unfrozen_provenance(corruption):
    corpus, retrieval = fixture()
    corruption(corpus, retrieval)
    with pytest.raises(ValueError):
        audit(corpus, retrieval)
