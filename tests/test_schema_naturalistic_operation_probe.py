# ruff: noqa: E402,I001
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6f_catalog import (
    confirmation_registry,
    development_registry,
)
from benchmarks.schema_adb_baseline import compile_registry_contracts
from benchmarks.schema_naturalistic_operation_probe import (
    BACKGROUND,
    MINILM_REVISION,
    TOOL_OPERATION,
    apply_membership_decision,
    load_naturalistic_bank,
)


def test_v6f_naturalistic_bank_is_frozen_and_unique() -> None:
    bank = load_naturalistic_bank()
    assert bank.languages == ("en", "ko", "es", "ja", "de", "mixed")
    assert len(bank.operation_labels) == 18
    assert len(bank.operation_texts) == 432
    assert len(bank.background_texts) == 384
    assert len(
        {*bank.operation_texts, *bank.background_texts}
    ) == 816
    assert MINILM_REVISION == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"


def test_v6f_membership_decision_is_negative_only() -> None:
    raw = "tool.retrieve"
    supported = {"retrieve", "update"}

    assert apply_membership_decision(
        raw_top_route=raw,
        scope_class=TOOL_OPERATION,
        operation_class="retrieve",
        supported_leaves=supported,
        unknown_tool=False,
    ) == (raw, "registered_operation_probe_preserve")

    assert apply_membership_decision(
        raw_top_route=raw,
        scope_class=TOOL_OPERATION,
        operation_class="delete",
        supported_leaves=supported,
        unknown_tool=False,
    ) == (None, "unsupported_operation_probe_veto")

    assert apply_membership_decision(
        raw_top_route=raw,
        scope_class=BACKGROUND,
        operation_class=None,
        supported_leaves=supported,
        unknown_tool=False,
    ) == (None, "background_probe_veto")

    assert apply_membership_decision(
        raw_top_route=raw,
        scope_class=TOOL_OPERATION,
        operation_class=None,
        supported_leaves=set(),
        unknown_tool=True,
    ) == (raw, "unknown_operation_semantics_preserve")


def test_v6f_registries_compile_known_operation_leaves() -> None:
    for registry in (development_registry(), confirmation_registry()):
        contracts = compile_registry_contracts(registry)
        assert len(contracts) == 19
        assert all(contract.leaf is not None for contract in contracts.values())
        assert all(
            len(contract.synthetic_positives) == 18
            for contract in contracts.values()
        )
        assert {contract.adapter or "native" for contract in contracts.values()} == {
            "native",
            "openapi",
            "mcp",
        }


def test_v6f_typed_unit_metadata_survives_compilation() -> None:
    dev = compile_registry_contracts(development_registry())
    refractive = next(
        row
        for row in dev["refractive_index.current"].data_contract
        if row.get("name") == "refractive_index"
    )
    assert refractive["semantic_id"] == "material.refractive_index"
    assert refractive["source_unit"] == "1"
    assert refractive["canonical_unit"] == "1"
    assert refractive["dimension"] == "refractive_index"
    assert refractive["scale"] == 1.0

    confirm = compile_registry_contracts(confirmation_registry())
    dielectric = next(
        row
        for row in confirm["dielectric_constant.current"].data_contract
        if row.get("name") == "dielectric_constant"
    )
    assert dielectric["semantic_id"] == "material.relative_permittivity"
    assert dielectric["source_unit"] == "1"
    assert dielectric["canonical_unit"] == "1"
    assert dielectric["dimension"] == "relative_permittivity"
    assert dielectric["scale"] == 1.0


def test_probe_core_contains_no_v6f_route_identities() -> None:
    source = (
        ROOT / "benchmarks" / "schema_naturalistic_operation_probe.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "waivers_api.m71",
        "spectra_index.n71",
        "leases_api.p71",
        "formula_index.q71",
    ):
        assert forbidden not in source
