import pytest

from schemarouter import (\n    EndpointSpec,\n    EvidenceContract,\n    EvidenceContractError,\n    EvidenceRequirements,\n    FieldSpec,\n    ToolSpec,\n)
from schemarouter.evidence import build_evidence_ledger_entry, contract_for_call


def route() -> tuple[ToolSpec, EndpointSpec]:
    endpoint = EndpointSpec(
        name="search",
        read_only=True,
        output_fields=[
            FieldSpec(name="material_id", identifier=True),
            FieldSpec(
                name="band_gap",
                unit="eV",
                source_type="calculated",
                license="CC BY 4.0",
            ),
        ],
    )
    tool = ToolSpec(
        name="materials",
        source_type="calculated",
        license="CC BY 4.0",
        endpoints=[endpoint],
    )
    return tool, endpoint


def test_evidence_ledger_is_payload_free_and_fingerprinted() -> None:
    tool, endpoint = route()
    entry = build_evidence_ledger_entry(
        tool,
        endpoint,
        ["material_id", "band_gap"],
        EvidenceContract(
            required=EvidenceRequirements(
                provenance=True,
                license=True,
                units=True,
                source_type="calculated",
            )
        ),
    )

    assert entry.tool == "materials"
    assert entry.endpoint == "search"
    assert entry.tool_fingerprint == tool.fingerprint
    assert entry.endpoint_fingerprint == endpoint.fingerprint
    assert entry.available.units is True
    assert "data" not in entry.model_dump()


def test_missing_evidence_fails_closed() -> None:
    tool, endpoint = route()
    tool = tool.model_copy(update={"license": None})
    endpoint = endpoint.model_copy(
        update={
            "output_fields": [
                endpoint.output_fields[0],
                endpoint.output_fields[1].model_copy(update={"license": None}),
            ]
        }
    )

    with pytest.raises(EvidenceContractError, match="license"):
        build_evidence_ledger_entry(
            tool,
            endpoint,
            ["material_id", "band_gap"],
            EvidenceContract(required=EvidenceRequirements(license=True)),
        )


def test_field_contract_requires_selected_declared_field() -> None:
    tool, endpoint = route()
    with pytest.raises(EvidenceContractError, match="band_gap.selected_field"):
        build_evidence_ledger_entry(
            tool,
            endpoint,
            ["material_id"],
            EvidenceContract(
                field_requirements={
                    "band_gap": EvidenceRequirements(units=True),
                }
            ),
        )


def test_corroboration_above_one_requires_explicit_aggregation_boundary() -> None:
    tool, endpoint = route()
    with pytest.raises(EvidenceContractError, match="aggregation boundary"):
        build_evidence_ledger_entry(
            tool,
            endpoint,
            ["material_id", "band_gap"],
            EvidenceContract(minimum_corroboration=2),
        )


def test_compiled_call_materializes_same_evidence_contract() -> None:
    tool, endpoint = route()
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        fields=["material_id", "band_gap"],
        required_evidence=EvidenceRequirements(provenance=True, units=True),
        field_evidence={"band_gap": EvidenceRequirements(units=True)},
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    contract = contract_for_call(call)
    entry = build_evidence_ledger_entry(tool, endpoint, call.fields, contract)

    assert contract.required.units is True
    assert entry.validated is True
