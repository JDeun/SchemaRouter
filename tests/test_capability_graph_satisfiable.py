from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
)
from schemarouter.capability_graph import satisfiable_capability_ids


def _field(semantic_id: str, type_name: str = "number") -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema={"type": type_name},
    )


def test_satisfiable_query_includes_requirement_free_and_compatible_contracts() -> None:
    capabilities = [
        CapabilityContract(capability_id="source"),
        CapabilityContract(capability_id="energy", requires=[_field("energy")]),
        CapabilityContract(capability_id="structure", requires=[_field("structure", "object")]),
    ]

    result = satisfiable_capability_ids(capabilities, [_field("energy")])

    assert result == ("energy", "source")


def test_satisfiable_query_fails_closed_for_unknown_metadata() -> None:
    capability = CapabilityContract(
        capability_id="energy",
        requires=[CapabilityFieldContract(semantic_id="energy", json_schema={"type": "number"})],
    )
    unknown = CapabilityFieldContract(semantic_id="energy")

    assert satisfiable_capability_ids([capability], [unknown]) == ()
