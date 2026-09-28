from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asymmetric_ontology_veto import (  # noqa: E402
    AUX_MODEL,
    AUX_REVISION,
    BGE_MODEL,
    BGE_REVISION,
    compile_registry_contracts,
    decide_veto,
    explicit_leaf,
)
from benchmarks.operation_routing_v5d_catalog import (  # noqa: E402
    confirmation_registry,
    development_registry,
)


def test_model_revisions_are_pinned() -> None:
    assert BGE_MODEL == "BAAI/bge-m3"
    assert BGE_REVISION == "5617a9f61b028005a4858fdac845db406aefb181"
    assert AUX_MODEL == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert AUX_REVISION == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


def test_source_contains_no_evaluation_route_or_tool_identities() -> None:
    source = (
        ROOT / "benchmarks" / "asymmetric_ontology_veto.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "incidents_api.i17",
        "repository_ops.r11",
        "artifact_ops.export",
        "records_api.z17",
        "inventory_ops.v11",
        "content_pipeline.export",
        "weather.current",
        "materials.search",
    ):
        assert forbidden not in source


def test_explicit_parser_is_high_precision_and_read_is_unknown() -> None:
    assert explicit_leaf("delete this item") == "delete"
    assert explicit_leaf("이 항목을 삭제해줘") == "delete"
    assert explicit_leaf("traduce el documento") == "translate"
    assert explicit_leaf("ジョブを再起動して") == "restart"
    assert explicit_leaf("refund this payment") == "refund"

    assert explicit_leaf("retrieve item X-1") is None
    assert explicit_leaf("search for matching entries") is None
    assert explicit_leaf("list all entries") is None


def test_exact_veto_rule_explicit_plus_one_semantic_vote() -> None:
    leaf, rule = decide_veto(
        explicit="delete",
        bge_leaf="delete",
        aux_leaf="update",
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    )
    assert leaf == "delete"
    assert rule == "explicit_plus_semantic_agreement"


def test_exact_veto_rule_dual_semantic_only_when_explicit_unknown() -> None:
    leaf, rule = decide_veto(
        explicit=None,
        bge_leaf="translate",
        aux_leaf="translate",
        supported_leaves={"retrieve", "export"},
        tool_has_unknown=False,
    )
    assert leaf == "translate"
    assert rule == "dual_semantic_agreement"


def test_veto_never_fires_on_disagreement_or_supported_leaf() -> None:
    assert decide_veto(
        explicit=None,
        bge_leaf="delete",
        aux_leaf="translate",
        supported_leaves={"retrieve"},
        tool_has_unknown=False,
    ) == (None, None)

    assert decide_veto(
        explicit="update",
        bge_leaf="update",
        aux_leaf="delete",
        supported_leaves={"retrieve", "update"},
        tool_has_unknown=False,
    ) == (None, None)


def test_unknown_endpoint_disables_absence_claim() -> None:
    assert decide_veto(
        explicit="delete",
        bge_leaf="delete",
        aux_leaf="delete",
        supported_leaves={"retrieve"},
        tool_has_unknown=True,
    ) == (None, None)


def test_all_frozen_eval_endpoints_have_known_operation_leaves() -> None:
    for registry in (development_registry(), confirmation_registry()):
        contracts = compile_registry_contracts(registry)
        assert contracts
        assert all(contract.leaf is not None for contract in contracts.values())


def test_development_and_confirmation_routes_are_disjoint() -> None:
    dev = set(compile_registry_contracts(development_registry()))
    confirm = set(compile_registry_contracts(confirmation_registry()))
    assert dev.isdisjoint(confirm)


def test_typed_field_metadata_survives_contract_compile() -> None:
    contracts = compile_registry_contracts(development_registry())
    current = contracts["traffic.current"]
    level = next(
        field for field in current.data_contract
        if field.get("name") == "level"
    )
    assert level["type"] == "number"
    assert level["source_unit"] == "vehicles/hour"
