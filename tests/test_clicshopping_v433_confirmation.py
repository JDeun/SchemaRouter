"""Unscored ClicShopping confirmation gate tests."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.validate_clicshopping_v433_confirmation import check_confirmation

ROOT = Path("benchmarks/external-validation-clicshopping-v433")


def docs():
    def read(name):
        return json.loads((ROOT / name).read_text(encoding="utf-8"))
    return (read("confirmation-plan.json"), read("dev-cases.json"),
            read("source-inventory.json"))


def sample(dev):
    new = deepcopy(dev)
    new["status"] = "external_confirmation_unscored"
    for index, case in enumerate(new["cases"]):
        case["id"] = f"candidate-unscored-{index:03d}"
        case["query"] = f"UNSCORED SYNTHETIC TEST {index}: " + case["query"]
    return new


def test_structural_gate_never_authorizes_scoring():
    plan, dev, inventory = docs()
    result = check_confirmation(plan, sample(dev), dev, inventory)
    assert result["scoring_authorized"] is False
    assert result["independent_human_review_pending"] is True
    assert result["model_calls"] == 0


def test_query_or_case_id_reuse_rejected():
    plan, dev, inventory = docs()
    candidate = sample(dev)
    candidate["cases"][0]["query"] = dev["cases"][0]["query"]
    with pytest.raises(ValueError, match="reuse of development queries"):
        check_confirmation(plan, candidate, dev, inventory)
    candidate = sample(dev)
    candidate["cases"][0]["id"] = dev["cases"][0]["id"]
    with pytest.raises(ValueError, match="reuse of development case identifiers"):
        check_confirmation(plan, candidate, dev, inventory)


def test_topk_and_permission_scope_cannot_change():
    plan, dev, inventory = docs()
    candidate = sample(dev)
    candidate["protocol"]["top_k"] = 5
    with pytest.raises(ValueError, match="Top-K"):
        check_confirmation(plan, candidate, dev, inventory)
    candidate = sample(dev)
    candidate["cases"][0]["required_routes"] = ["customerOrders.list_orders"]
    with pytest.raises(ValueError, match="customerOrders"):
        check_confirmation(plan, candidate, dev, inventory)
