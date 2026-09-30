from __future__ import annotations

from schemarouter import (
    AdapterContext,
    AdapterLoadResult,
    EndpointSpec,
    FieldSpec,
    SchemaRouter,
    ToolSpec,
)


class NestedContractAdapter:
    kind = "nested-contract-test"
    priority = 1

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        if not context.url.endswith("/nested-contract"):
            return None
        tool = ToolSpec(
            name="plugin_contract",
            source_type="plugin-test",
            endpoints=[
                EndpointSpec(
                    name="read",
                    output_schema={
                        "type": "object",
                        "properties": {
                            "metrics": {
                                "type": "object",
                                "properties": {
                                    "band_gap": {"type": "number"},
                                },
                            }
                        },
                    },
                    output_fields=[
                        FieldSpec(
                            name="metrics",
                            json_schema={
                                "type": "object",
                                "properties": {
                                    "band_gap": {"type": "number"},
                                },
                            },
                            source_type="plugin-test",
                        ),
                        FieldSpec(
                            name="metrics.band_gap",
                            semantic_id="materials.band_gap",
                            json_schema={"type": "number"},
                            path=["metrics", "band_gap"],
                            result_path=["metrics.band_gap"],
                            unit="eV",
                            unit_normalization={
                                "dimension": "energy",
                                "canonical_unit": "eV",
                            },
                            qualifiers={"temperature": "300 K"},
                            source_type="plugin-test",
                            license="plugin-license",
                        ),
                    ],
                )
            ],
        )
        return AdapterLoadResult(tool=tool)


async def test_custom_adapter_nested_field_contract_is_preserved() -> None:
    router = SchemaRouter()
    router.register_adapter(NestedContractAdapter())

    tool = await router.add_url(
        "https://example.test/nested-contract",
        kind="nested-contract-test",
    )

    field = {
        item.name: item
        for item in tool.endpoint("read").output_fields
    }["metrics.band_gap"]

    assert field.semantic_id == "materials.band_gap"
    assert field.path == ["metrics", "band_gap"]
    assert field.result_path == ["metrics.band_gap"]
    assert field.unit == "eV"
    assert field.unit_normalization is not None
    assert field.unit_normalization.dimension == "energy"
    assert field.qualifiers == {"temperature": "300 K"}
    assert field.source_type == "plugin-test"
    assert field.license == "plugin-license"
