from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.schema_finetuned_operation_parser import (  # noqa: E402
    BACKGROUND,
    BATCH_SIZE,
    EPOCHS,
    GRAD_CLIP_NORM,
    LEARNING_RATE,
    MAX_LENGTH,
    OPERATION_LABELS,
    SCOPE_LABELS,
    TRAINING_SEED,
    WEIGHT_DECAY,
    apply_structured_membership,
    load_training_rows,
    training_bank_sha256,
)


def test_v6h_frozen_training_bank_and_hyperparameters() -> None:
    data = json.loads(
        (
            ROOT
            / "benchmarks"
            / "operation-routing-v6h-finetuned-operation-parser-preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert data["issue"] == 415
    assert data["training_evidence"]["sha256"] == training_bank_sha256()
    assert data["training_evidence"]["bank_wording_mutable"] is False
    assert data["training_evidence"]["dev_rows_used"] is False
    assert TRAINING_SEED == 20260929
    assert MAX_LENGTH == 96
    assert BATCH_SIZE == 32
    assert EPOCHS == 4
    assert LEARNING_RATE == 2e-5
    assert WEIGHT_DECAY == 0.01
    assert GRAD_CLIP_NORM == 1.0
    assert len(OPERATION_LABELS) == 18
    assert SCOPE_LABELS == ("TOOL_OPERATION", "BACKGROUND")


def test_v6h_training_rows_are_exactly_frozen_bank() -> None:
    rows = load_training_rows()
    assert len(rows) == 816
    assert sum(row["scope_id"] == 0 for row in rows) == 432
    assert sum(row["scope_id"] == 1 for row in rows) == 384
    assert sum(row["operation_id"] >= 0 for row in rows) == 432
    assert sum(row["operation_id"] == -100 for row in rows) == 384
    assert len({str(row["text"]) for row in rows}) == 816


def test_v6h_decision_is_veto_only() -> None:
    route = "tool.retrieve"
    supported = {"retrieve", "update"}

    predicted, reason = apply_structured_membership(
        raw_top_route=route,
        scope_class="TOOL_OPERATION",
        operation_class="retrieve",
        supported_leaves=supported,
        unknown_tool=False,
    )
    assert predicted == route
    assert reason == "registered_operation_parser_preserve"

    predicted, reason = apply_structured_membership(
        raw_top_route=route,
        scope_class="TOOL_OPERATION",
        operation_class="delete",
        supported_leaves=supported,
        unknown_tool=False,
    )
    assert predicted is None
    assert reason == "unsupported_operation_parser_veto"

    predicted, reason = apply_structured_membership(
        raw_top_route=route,
        scope_class=BACKGROUND,
        operation_class="retrieve",
        supported_leaves=supported,
        unknown_tool=False,
    )
    assert predicted is None
    assert reason == "background_parser_veto"

    predicted, reason = apply_structured_membership(
        raw_top_route=route,
        scope_class="TOOL_OPERATION",
        operation_class="delete",
        supported_leaves=set(),
        unknown_tool=True,
    )
    assert predicted == route
    assert reason == "unknown_operation_semantics_preserve"
