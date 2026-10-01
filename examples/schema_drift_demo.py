"""Offline schema-drift comparison example with no network dependency."""

from schemarouter import EndpointSpec, FieldSpec, ToolSpec, compare_tool_specs


def make_tool(*, include_formula: bool) -> ToolSpec:
    fields = [
        FieldSpec(
            name="material_id",
            identifier=True,
            json_schema={"type": "string"},
        ),
        FieldSpec(
            name="band_gap",
            semantic_id="band_gap",
            json_schema={"type": "number"},
            unit="eV",
        ),
    ]
    properties: dict[str, dict[str, str]] = {
        "material_id": {"type": "string"},
        "band_gap": {"type": "number"},
    }
    required = ["material_id", "band_gap"]

    if include_formula:
        fields.append(
            FieldSpec(
                name="formula",
                json_schema={"type": "string"},
            )
        )
        properties["formula"] = {"type": "string"}

    return ToolSpec(
        name="materials",
        provider="example-materials",
        access_mode="openapi",
        endpoints=[
            EndpointSpec(
                name="lookup",
                read_only=True,
                output_schema={
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
                output_fields=fields,
            )
        ],
    )


def main() -> None:
    accepted = make_tool(include_formula=False)
    candidate = make_tool(include_formula=True)
    report = compare_tool_specs(accepted, candidate)

    assert report.compatibility == "compatible"
    print("compatibility:", report.compatibility)
    for change in report.changes:
        print(change.severity, change.path, change.kind)


if __name__ == "__main__":
    main()
