"""Offline research-loop tests: no model weights or GitHub writes."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.research_operation_fit_auto_loop import (
    CORPUS_SHA,
    KINDS,
    STATE_END,
    STATE_MARKER,
    VARIANTS,
    choose_prediction,
    empty_state,
    evaluate_variant,
    formatted_comment,
    loop,
    metrics,
    next_variant,
    parse_comments,
    protocol,
    validate_state,
)


def test_allowlist_and_no_release_promotion() -> None:
    plan, corpus, digest = protocol()
    assert digest == CORPUS_SHA
    assert len(corpus["cases"]) == 72
    assert [x["id"] for x in plan["variants"]] == list(VARIANTS)
    assert plan["per_run_budget"] == 2
    assert plan["independent_evaluation_approved"] is False
    assert plan["automatic_source_code_changes"] is False
    assert plan["automatic_pr_merges"] is False
    assert plan["release_policy"] == "no_release_or_product_promotion"
    assert next_variant(empty_state()) == "language_aligned_entailment"


def fake_score(
    _query: str, _hypotheses: tuple[str, ...],
) -> tuple[dict[str, float], dict[str, float]]:
    entail = {name: 0.05 for name in KINDS}
    contradict = {name: 0.05 for name in KINDS}
    entail["search"] = 0.92
    return entail, contradict


def test_iterative_loop_runs_two_trials_then_resumes_without_repeat() -> None:
    _, corpus, _ = protocol()
    first = loop(empty_state(), corpus, fake_score, 123)
    assert len(first["new_results"]) == 2
    assert [x["variant"] for x in first["new_results"]] == list(VARIANTS[:2])
    assert len(first["state"]["results"]) == 2
    assert first["variants_exhausted"] is False
    assert first["may_execute_tools"] is False
    assert first["may_auto_merge_pr"] is False
    assert first["independent_validation"] is False
    second = loop(first["state"], corpus, fake_score, 124)
    assert [x["variant"] for x in second["new_results"]] == [VARIANTS[2]]
    assert len(second["state"]["results"]) == 3
    assert second["variants_exhausted"] is True
    assert next_variant(second["state"]) is None
    assert all(len(trial["rows"]) == 72 for trial in first["new_results"])


def test_resume_cursor_is_bot_owned_and_checked() -> None:
    _, corpus, _ = protocol()
    report = loop(empty_state(), corpus, fake_score, 123)
    note = formatted_comment(report, "https://github.com/JDeun/SchemaRouter/actions/runs/123")
    assert note.count(STATE_MARKER) == 1
    assert STATE_END in note
    comments = [
        {"user": {"login": "human"}, "body": note},
        {"user": {"login": "github-actions[bot]"}, "body": note},
    ]
    loaded = parse_comments(comments)
    assert loaded == report["state"]
    assert parse_comments([comments[0]]) == empty_state()


@pytest.mark.parametrize("change", [
    "unknown_variant", "claimed_independent", "release_authority",
    "duplicate", "bad_totals", "invented_run", "wrong_digest",
])
def test_cursor_tampering_never_enables_unregistered_experiment(
    change: str,
) -> None:
    _, corpus, _ = protocol()
    state = loop(empty_state(), corpus, fake_score, 123)["state"]
    damaged = copy.deepcopy(state)
    if change == "unknown_variant":
        damaged["results"][0]["variant"] = "inject_model"
    elif change == "claimed_independent":
        damaged["independent_qualification"] = True
    elif change == "release_authority":
        damaged["may_merge_release"] = True
    elif change == "duplicate":
        damaged["results"][1]["variant"] = damaged["results"][0]["variant"]
    elif change == "bad_totals":
        damaged["results"][0]["supported_correct"] += 2
    elif change == "invented_run":
        damaged["results"][0]["run_id"] = -1
    elif change == "wrong_digest":
        damaged["source_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        validate_state(damaged)


def test_invalid_bot_comment_does_not_reset_cursor() -> None:
    comment = {
        "user": {"login": "github-actions[bot]"},
        "body": f"{STATE_MARKER}" + '{"schema_version":1}' + STATE_END,
    }
    with pytest.raises(ValueError):
        parse_comments([comment])


def test_signed_threshold_and_veto_are_not_execution_authority() -> None:
    entail, contrad = fake_score("anything", ())
    assert choose_prediction(
        "search for paper", entail, contrad, VARIANTS[0],
    ) == "search"
    assert choose_prediction(
        "search for paper", entail, contrad, VARIANTS[1],
    ) == "search"
    assert choose_prediction(
        "do not search for paper", entail, contrad, VARIANTS[2],
    ) is None
    assert choose_prediction(
        "search for paper", entail, contrad, VARIANTS[2],
    ) == "search"
    with pytest.raises(ValueError):
        choose_prediction("hello", {"search": 0.1}, contrad, VARIANTS[0])
    entail["search"] = float("nan")
    with pytest.raises(ValueError):
        choose_prediction("search", entail, contrad, VARIANTS[0])


def test_language_metrics_have_disjoint_denominators() -> None:
    _, corpus, _ = protocol()
    rows, result = evaluate_variant(VARIANTS[0], corpus, fake_score)
    assert len(rows) == 72
    assert sum(row["kind"] == "supported" for row in rows) == 54
    assert sum(row["kind"] == "unsupported" for row in rows) == 18
    assert sum(result[k] for k in (
        "supported_correct", "supported_wrong", "supported_refused",
    )) == 54
    assert 0 <= result["unsupported_false_accepted"] <= 18
    assert all(
        sum(row["language"] == lang for row in rows) == 24
        for lang in ("en", "ko", "ja")
    )
    with pytest.raises(ValueError):
        metrics(rows[:-1])


def test_plan_output_no_fictional_progress(monkeypatch: pytest.MonkeyPatch,
                                         tmp_path: Path) -> None:
    # Exact marker JSON is roundtrippable as a GitHub comments API payload.
    _, corpus, _ = protocol()
    measured = loop(empty_state(), corpus, fake_score, 123)
    comments = [{
        "user": {"login": "github-actions[bot]"},
        "body": formatted_comment(
            measured, "https://github.com/JDeun/SchemaRouter/actions/runs/123",
        ),
    }]
    path = tmp_path / "comments.json"
    path.write_text(json.dumps(comments), encoding="utf-8")
    assert parse_comments(json.loads(path.read_text(encoding="utf-8"))) == measured["state"]
