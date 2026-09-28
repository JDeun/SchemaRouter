from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "benchmarks" / "operation-routing-v5-typed-frame-preregistration.json"
PARSER = ROOT / "benchmarks" / "query_first_typed_frame.py"


def test_v5_preregistration_has_frozen_corpus_identities() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))

    assert data["issue"] == 347
    assert data["data_protocol"]["development"]["corpus_sha256"] == (
        "79a7cb9672e6633739e0acd08882019f5cfeff479df103f8199aabacb8501a9f"
    )
    assert data["data_protocol"]["registration_confirmation"]["corpus_sha256"] == (
        "15587c646d64b4f3462127742c05d59092938f68a4c047b731e9a8c78c0eb673"
    )
    assert data["corpus_freeze"]["scored_at_freeze"] is False
    assert data["corpus_freeze"]["both_corpora_generated_together"] is True


def test_v5_has_no_learned_veto_or_route_local_thresholds() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))
    authority = data["route_authority"]

    assert authority["route_specific_thresholds"] is False
    assert authority["probability_thresholds"] is False
    assert authority["rank2_fallback"] is False
    assert authority["pseudo_route"] is False


def test_v5_parser_contains_no_0_11_route_identity_rules() -> None:
    source = PARSER.read_text(encoding="utf-8")
    forbidden = (
        "weather.current",
        "materials.search",
        "papers.citations",
        "finance.quote",
        "calendar.create",
        "support.create_ticket",
        "inventory.update",
        "users.lookup",
    )
    for route_id in forbidden:
        assert route_id not in source


def test_v5_confirmation_stays_unscored_in_dev_protocol() -> None:
    data = json.loads(PREREG.read_text(encoding="utf-8"))
    assert data["data_protocol"]["registration_confirmation"]["role"] == (
        "frozen_confirmation_only"
    )
    assert data["stopping_rule"]["development_pass"].startswith(
        "freeze_exact_parser_compiler_ranker"
    )
