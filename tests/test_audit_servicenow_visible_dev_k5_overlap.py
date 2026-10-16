"""Entirely synthetic offline integrity tests; NO model or independent gold."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import audit_servicenow_visible_dev_k5_overlap as study
from scripts.research_servicenow_native_e5_dev import case_metrics, summarize


def _synthetic_source(monkeypatch):
    # The real GitHub Actions workflow validates actual source bytes before
    # calling audit. Here we only exercise ranking and metric invariants.
    monkeypatch.setattr(study, "validate_package", lambda *_: None)
    names = [f"synthetic_tool_{i}" for i in range(12)]
    source = {
        name: {
            "name": name,
            "inputSchema": {
                "properties": {"id": {"type": "string"}},
            },
        } for name in names
    }
    case_list, rows = [], []
    for index in range(24):
        supported = index < 20
        name = names[index % len(names)]
        case = {
            "id": f"sn-dev-{index + 1:03d}",
            "query": f"synthetic fixture request {index}",
            "label": "supported" if supported else "unsupported",
            "required_tools": [name] if supported else [],
            "required_fields": {name: ["id"]} if supported else {},
        }
        case_list.append(case)
        lexical = names[:]
        semantic = names[5:] + names[:5]
        arms = {
            "static_full": names[:],
            "lexical_k3": lexical[:3],
            "lexical_k5": lexical[:5],
            "e5_k3": semantic[:3],
            "e5_k5": semantic[:5],
        }
        rows.append({
            "id": case["id"], "kind": case["label"],
            "original_visible_dev_query": case["query"],
            "lexical_order": lexical,
            "e5_order": semantic,
            "selected": arms,
            "metrics": {
                a: case_metrics(case, selected, source)
                for a, selected in arms.items()
            },
        })
    report = {
        "study": "native_servicenow_original_visible_dev_e5_vs_lexical",
        "status": "same_author_visible_dev_not_independent",
        "model_revision": study.MODEL_REVISION,
        "upstream_commit": study.PINNED_UPSTREAM,
        "native_readonly_tools_sha256": study.PINNED_NATIVE_TOOL_SHA256,
        "actions_run_id": str(study.PINNED_RUN),
        "limitations": {
            "release_authorized": False,
            "original_visible_dev_only": True,
            "no_fit_calibrated": False,
        },
        "cases": rows, "summary": summarize(rows, case_list),
    }
    snapshot = {
        "tools": list(source.values()),
        "tools_sha256": study.PINNED_NATIVE_TOOL_SHA256,
    }
    return report, {}, {"cases": case_list}, snapshot


def test_union_preserves_original_lexical_order_and_de_duplicates() -> None:
    base = ["a", "b", "c", "d", "e"]
    next_ = ["e", "f", "a", "g", "h"]
    assert study.ordered_union(
        base, next_, allowed=set(base + next_)
    ) == ["a", "b", "c", "d", "e", "f", "g", "h"]


@pytest.mark.parametrize("first,second", [
    (["a"] * 5, ["a", "b", "c", "d", "e"]),
    (["a", "b", "c", "d", "e"], ["x", "b", "c", "d", "e"]),
    (["a", "b", "c", "d", "e"], ["a", "b", "c", "d", 3]),
    (["a", "b", "c", "d"], ["a", "b", "c", "d", "e"]),
])
def test_union_rejects_duplicate_foreign_or_invalid_width(first, second) -> None:
    with pytest.raises(ValueError, match="invalid K5"):
        study.ordered_union(first, second, allowed=set("abcdefghi"))


def test_immutable_report_digest_rejects_changed_bytes() -> None:
    with pytest.raises(ValueError, match="pinned report raw SHA-256 mismatch"):
        study.verify_sha(b"changed", study.PINNED_REPORT_SHA256, kind="report")


def test_synthetic_audit_only_reports_complementarity_not_release(monkeypatch) -> None:
    report, manifest, cases, snapshot = _synthetic_source(monkeypatch)
    output = study.audit(report, manifest, cases, snapshot)
    assert output["evidence_class"] == "POST_HOC_PREVIOUSLY_VISIBLE_ENGLISH_DEV_ONLY"
    assert output["supported_cases"] == 20
    assert output["unsupported_cases"] == 4
    assert output["unsupported_nonempty_not_no_fit"] == 4
    assert 5 <= output["mean_native_tool_count"] <= 10
    assert output["limitations"]["may_promote_model_or_release"] is False
    assert output["limitations"]["new_independent_query_or_gold"] is False


@pytest.mark.parametrize("forgery", (
    "prefix", "source_duplicate", "query", "label", "metric", "model", "row",
))
def test_synthetic_audit_fails_on_forged_original_report(
    monkeypatch, forgery: str,
) -> None:
    report, manifest, cases, snapshot = _synthetic_source(monkeypatch)
    report = deepcopy(report)
    if forgery == "prefix":
        report["cases"][0]["selected"]["lexical_k5"] = ["synthetic_tool_9"]
    elif forgery == "source_duplicate":
        report["cases"][0]["lexical_order"][0] = "synthetic_tool_1"
    elif forgery == "query":
        report["cases"][0]["original_visible_dev_query"] = "injected"
    elif forgery == "label":
        report["cases"][0]["kind"] = "unsupported"
    elif forgery == "metric":
        report["cases"][0]["metrics"]["lexical_k5"]["route_hits"] = 99
    elif forgery == "model":
        report["model_revision"] = "main"
    else:
        report["cases"].pop()
    with pytest.raises(ValueError):
        study.audit(report, manifest, cases, snapshot)
