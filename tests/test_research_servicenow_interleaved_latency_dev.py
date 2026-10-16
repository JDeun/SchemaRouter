"""Integrity and statistical-contract checks for ServiceNow latency DEV only."""
from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from scripts.research_servicenow_interleaved_latency_dev import (
    ARMS,
    canonical,
    percentile,
    schedule,
    summarize,
    validate_samples,
)


def _fixture(repeats: int = 6):
    tools = [
        {
            "name": "a",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        },
        {
            "name": "b",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
    cases = {"cases": [
        {
            "id": "supported",
            "label": "supported",
            "required_tools": ["a"],
            "required_fields": {"a": ["query"]},
        },
        {
            "id": "unsupported",
            "label": "unsupported",
            "required_tools": [],
            "required_fields": {},
        },
    ]}
    samples = []
    for case_id, iteration, arm, order in schedule(
        [c["id"] for c in cases["cases"]], repeats, 20261016,
    ):
        selected = ["a", "b"] if arm == "static_readonly" else ["a"]
        visible = canonical([t for t in tools if t["name"] in selected])
        samples.append({
            "case_id": case_id,
            "iteration": iteration,
            "arm": arm,
            "order_position": order,
            "latency_ms": float(iteration + 1),
            "candidate_tools": selected,
            "contract_sha256": hashlib.sha256(visible).hexdigest(),
            "visible_schema_bytes": len(visible),
        })
    return cases, {"tools": tools}, samples


def test_repeat_schedule_is_deterministic_and_balances_position():
    ids = ["case_a", "case_b", "case_c"]
    first = list(schedule(ids, repeats=6, seed=20261016))
    assert first == list(schedule(ids, repeats=6, seed=20261016))
    assert len(first) == 54
    assert len({
        (case_id, iteration, arm)
        for case_id, iteration, arm, _ in first
    }) == 54
    for case_id in ids:
        for arm in ARMS:
            positions = [
                position
                for c, _, a, position in first
                if c == case_id and a == arm
            ]
            assert sorted(positions) == [0, 0, 1, 1, 2, 2]


@pytest.mark.parametrize(("ids", "repeats", "seed"), [
    ([], 6, 20261016),
    (["duplicate", "duplicate"], 6, 20261016),
    (["a"], 0, 20261016),
    (["a"], True, 20261016),
    (["a"], 3, False),
])
def test_invalid_schedule_rejected(ids, repeats, seed):
    with pytest.raises(ValueError, match="invalid interleaved schedule"):
        list(schedule(ids, repeats, seed))


def test_per_request_p95_is_not_p95_of_case_medians():
    cases, snapshot, samples = _fixture()
    for sample in samples:
        if (sample["arm"] == "schemarouter_k5"
                and sample["case_id"] == "supported"
                and sample["iteration"] == 5):
            sample["latency_ms"] = 1000.0
    validate_samples(samples, cases, snapshot, 6, 20261016)
    result = summarize(samples, cases, snapshot)
    item = result["schemarouter_k5"]
    assert item["request_samples"] == 12
    assert item["request_p95_ms"] > 300
    assert item["p95_of_per_case_medians_ms_not_request_p95"] < 5
    assert item["supported_tool_recall_macro_per_case"] == 1.0
    assert item["supported_tool_recall_micro_per_required_tool"] == 1.0
    assert item["supported_input_field_recall_macro_per_case"] == 1.0
    assert item["supported_input_field_recall_micro_per_required_field"] == 1.0
    assert item["unsupported_nonempty_candidate_fraction_not_no_fit"] == 1.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == pytest.approx(3.85)


@pytest.mark.parametrize("mutation", [
    lambda rows: rows.pop(),
    lambda rows: rows[0].update(latency_ms=float("nan")),
    lambda rows: rows[0].update(latency_ms=-1),
    lambda rows: rows[0].update(latency_ms=True),
    lambda rows: rows[0].update(arm="schemarouter_k5"),
    lambda rows: rows[0].update(order_position=99),
    lambda rows: rows[0].update(case_id="foreign"),
    lambda rows: rows[0].update(contract_sha256="0" * 64),
    lambda rows: rows[0].update(visible_schema_bytes=True),
    lambda rows: rows[0].update(candidate_tools=["a", "a"]),
    lambda rows: rows[0].update(candidate_tools=["unknown"]),
    lambda rows: rows[0].update(candidate_tools=[]),
    lambda rows: rows[0].update(user_claim="unapproved"),
])
def test_missing_or_forged_request_level_sample_rejected(mutation):
    cases, snapshot, source_rows = _fixture()
    rows = deepcopy(source_rows)
    mutation(rows)
    with pytest.raises(ValueError):
        validate_samples(rows, cases, snapshot, 6, 20261016)


def test_complete_original_samples_validate_without_external_agent_claim():
    cases, snapshot, samples = _fixture()
    validate_samples(samples, cases, snapshot, 6, 20261016)
    measured = summarize(samples, cases, snapshot)
    assert set(measured) == set(ARMS)
    assert all(arm["request_samples"] == 12 for arm in measured.values())
    assert all(arm["case_count"] == 2 for arm in measured.values())


def test_ranking_drift_rejected_even_when_each_contract_hash_is_valid():
    cases, snapshot, samples = _fixture()
    rows = deepcopy(samples)
    altered = next(
        row for row in rows
        if row["case_id"] == "supported"
        and row["arm"] == "schemarouter_k5"
        and row["iteration"] == 5
    )
    native = snapshot["tools"]
    altered["candidate_tools"] = ["b"]
    raw = canonical([native[1]])
    altered["contract_sha256"] = hashlib.sha256(raw).hexdigest()
    altered["visible_schema_bytes"] = len(raw)
    with pytest.raises(ValueError, match="candidate order drift"):
        validate_samples(rows, cases, snapshot, 6, 20261016)
