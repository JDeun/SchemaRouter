import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ToolSpec,
    UnitNormalizationSpec,
    compare_endpoint_specs,
    compare_tool_specs,
)


def endpoint(**updates):
    base = EndpointSpec(
        name="search",
        description="Search materials",
        method="GET",
        path="/materials",
        read_only=True,
        destructive=False,
        parameters=[
            ParameterSpec(
                name="limit",
                required=False,
                location="query",
                json_schema={"type": "integer", "minimum": 1, "maximum": 100},
            )
        ],
        output_fields=[
            FieldSpec(name="material_id", identifier=True, json_schema={"type": "string"}),
            FieldSpec(name="band_gap", unit="eV", json_schema={"type": "number"}),
        ],
    )
    return base.model_copy(update=updates)


def test_identical_endpoint_schema_report_is_identical() -> None:
    old = endpoint()
    report = compare_endpoint_specs(old, old.model_copy(deep=True))

    assert report.compatibility == "identical"
    assert report.changed is False
    assert report.old_fingerprint == report.new_fingerprint


def test_optional_parameter_addition_is_compatible() -> None:
    old = endpoint()
    new = endpoint(
        parameters=[
            *old.parameters,
            ParameterSpec(
                name="page",
                required=False,
                location="query",
                json_schema={"type": "integer"},
            ),
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "compatible"
    assert any(
        change.kind == "parameter_added" and change.path == "parameters.page"
        for change in report.changes
    )


def test_required_parameter_addition_is_breaking() -> None:
    old = endpoint()
    new = endpoint(
        parameters=[
            *old.parameters,
            ParameterSpec(
                name="token",
                required=True,
                location="query",
                json_schema={"type": "string"},
            ),
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "parameter_added" and change.severity == "breaking"
        for change in report.changes
    )


def test_side_effect_escalation_requires_security_review() -> None:
    old = endpoint()
    new = endpoint(read_only=False)

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.kind == "execution_semantics_changed"
        and change.severity == "security"
        for change in report.changes
    )


def test_destructive_escalation_requires_security_review() -> None:
    old = endpoint()
    new = endpoint(read_only=False, destructive=True)

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.kind == "destructive_semantics_changed"
        and change.severity == "security"
        for change in report.changes
    )


def test_integer_to_number_schema_change_is_proven_widening() -> None:
    old = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "integer"},
            )
        ]
    )
    new = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "number"},
            )
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "compatible"
    assert report.changes[0].severity == "compatible"


def test_unknown_json_schema_change_is_conservatively_breaking() -> None:
    old = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "string"},
            )
        ]
    )
    new = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "string", "pattern": "^[A-Z]+$"},
            )
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "breaking"
    assert any(change.kind == "json_schema_changed" for change in report.changes)


def test_tool_report_prefixes_endpoint_changes() -> None:
    old_endpoint = endpoint()
    new_endpoint = endpoint(read_only=False)
    old = ToolSpec(name="materials", endpoints=[old_endpoint])
    new = ToolSpec(name="materials", endpoints=[new_endpoint])

    report = compare_tool_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.path == "endpoints.search.read_only"
        for change in report.changes
    )


def test_tool_endpoint_addition_is_compatible_but_never_reuses_fingerprint() -> None:
    old = ToolSpec(name="materials", endpoints=[endpoint()])
    new = ToolSpec(
        name="materials",
        endpoints=[
            endpoint(),
            EndpointSpec(name="health", method="GET", path="/health", read_only=True),
        ],
    )

    report = compare_tool_specs(old, new)

    assert report.compatibility == "compatible"
    assert old.fingerprint != new.fingerprint
    assert report.old_fingerprint != report.new_fingerprint


def test_http_method_escalation_requires_security_review_even_if_read_only_flag_is_stale() -> None:
    old = endpoint(method="GET", read_only=True)
    new = endpoint(method="POST", read_only=True)

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.kind == "method_changed"
        and change.severity == "security"
        for change in report.changes
    )


def test_type_widening_with_simultaneous_new_constraint_is_not_false_compatible() -> None:
    old = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "integer"},
            )
        ]
    )
    new = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "number", "maximum": 10},
            )
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "json_schema_changed"
        and change.severity == "breaking"
        for change in report.changes
    )


def test_enum_expansion_with_simultaneous_new_constraint_is_not_false_compatible() -> None:
    old = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "string", "enum": ["a"]},
            )
        ]
    )
    new = endpoint(
        parameters=[
            ParameterSpec(
                name="value",
                location="query",
                json_schema={"type": "string", "enum": ["a", "b"], "maxLength": 1},
            )
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "breaking"


def test_untyped_optional_output_field_addition_is_compatible() -> None:
    old = endpoint(
        output_fields=[FieldSpec(name="material_id", identifier=True)]
    )
    new = endpoint(
        output_fields=[
            FieldSpec(name="material_id", identifier=True),
            FieldSpec(name="note"),
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "compatible"
    assert any(
        change.kind == "output_field_added"
        and change.severity == "compatible"
        for change in report.changes
    )


def test_typed_output_field_addition_is_conservatively_breaking() -> None:
    old = endpoint(
        output_fields=[FieldSpec(name="material_id", identifier=True)]
    )
    new = endpoint(
        output_fields=[
            FieldSpec(name="material_id", identifier=True),
            FieldSpec(name="band_gap", json_schema={"type": "number"}),
        ]
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "output_field_added"
        and change.severity == "breaking"
        for change in report.changes
    )



def test_execution_metadata_drift_is_breaking() -> None:
    old = endpoint(
        execution_metadata={"request_body_mode": "root_schema"}
    )
    new = endpoint(
        execution_metadata={"request_body_mode": "flattened_object"}
    )

    report = compare_endpoint_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.kind == "execution_metadata_changed"
        and change.severity == "security"
        for change in report.changes
    )


def test_execution_origin_drift_requires_security_review() -> None:
    old = ToolSpec(
        name="materials",
        endpoints=[endpoint()],
        remote=False,
    )
    new = ToolSpec(
        name="materials",
        endpoints=[endpoint()],
        remote=True,
    )

    report = compare_tool_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.kind == "execution_origin_changed"
        and change.severity == "security"
        for change in report.changes
    )



def test_read_only_endpoint_addition_is_compatible() -> None:
    old = ToolSpec(
        name="demo",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    new = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(name="read", read_only=True),
            EndpointSpec(name="extra_read", read_only=True, method="GET"),
        ],
    )

    report = compare_tool_specs(old, new)

    assert report.compatibility == "compatible"
    assert any(
        change.kind == "endpoint_added"
        and change.severity == "compatible"
        for change in report.changes
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        EndpointSpec(name="write", read_only=False),
        EndpointSpec(name="delete", read_only=True, destructive=True),
        EndpointSpec(name="post", read_only=True, method="POST"),
    ],
)
def test_side_effect_endpoint_addition_requires_security_review(
    endpoint: EndpointSpec,
) -> None:
    old = ToolSpec(
        name="demo",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    new = ToolSpec(
        name="demo",
        endpoints=[
            EndpointSpec(name="read", read_only=True),
            endpoint,
        ],
    )

    report = compare_tool_specs(old, new)

    assert report.compatibility == "security_review"
    assert any(
        change.kind == "endpoint_added"
        and change.severity == "security"
        for change in report.changes
    )


def test_unclassified_remote_endpoint_addition_requires_security_review() -> None:
    old = ToolSpec(
        name="demo",
        remote=True,
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    new = ToolSpec(
        name="demo",
        remote=True,
        endpoints=[
            EndpointSpec(name="read", read_only=True),
            EndpointSpec(name="mystery", read_only=None),
        ],
    )

    report = compare_tool_specs(old, new)

    assert report.compatibility == "security_review"



@pytest.mark.parametrize(
    ("field", "old_value", "new_value", "kind"),
    [
        ("provider", "materials_project", "oqmd", "information_provider_changed"),
        ("access_mode", "openapi", "optimade", "access_mode_changed"),
    ],
)
def test_provider_route_identity_drift_requires_security_review(
    field: str,
    old_value: str,
    new_value: str,
    kind: str,
) -> None:
    old = ToolSpec(
        name="materials",
        provider="materials_project",
        access_mode="openapi",
        endpoints=[endpoint()],
    )
    new = old.model_copy(update={field: new_value}, deep=True)

    report = compare_tool_specs(old, new)

    assert report.compatibility == "security_review"
    assert report.old_fingerprint != report.new_fingerprint
    assert any(
        change.kind == kind
        and change.severity == "security"
        for change in report.changes
    )



def test_field_semantic_id_change_is_breaking() -> None:
    old = endpoint()
    new_fields = [field.model_copy(deep=True) for field in old.output_fields]
    new_fields[1] = new_fields[1].model_copy(
        update={"semantic_id": "electronic_band_gap"},
        deep=True,
    )
    report = compare_endpoint_specs(
        old,
        old.model_copy(update={"output_fields": new_fields}, deep=True),
    )

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "semantic_id_changed"
        for change in report.changes
    )


def test_field_result_path_change_is_breaking() -> None:
    old = endpoint()
    new_fields = [field.model_copy(deep=True) for field in old.output_fields]
    new_fields[1] = new_fields[1].model_copy(
        update={"result_path": ["properties", "band_gap"]},
        deep=True,
    )
    report = compare_endpoint_specs(
        old,
        old.model_copy(update={"output_fields": new_fields}, deep=True),
    )

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "result_projection_path_changed"
        for change in report.changes
    )


def test_field_unit_normalization_change_is_breaking() -> None:
    old = endpoint()
    old_fields = [field.model_copy(deep=True) for field in old.output_fields]
    old_fields[1] = old_fields[1].model_copy(
        update={
            "unit_normalization": UnitNormalizationSpec(
                dimension="energy",
                canonical_unit="J",
                scale=1.602176634e-19,
            )
        },
        deep=True,
    )
    old_with_units = old.model_copy(
        update={"output_fields": old_fields},
        deep=True,
    )

    new_fields = [field.model_copy(deep=True) for field in old_fields]
    new_fields[1] = new_fields[1].model_copy(
        update={
            "unit_normalization": UnitNormalizationSpec(
                dimension="energy",
                canonical_unit="J",
                scale=1.0,
            )
        },
        deep=True,
    )
    report = compare_endpoint_specs(
        old_with_units,
        old_with_units.model_copy(
            update={"output_fields": new_fields},
            deep=True,
        ),
    )

    assert report.compatibility == "breaking"
    assert any(
        change.kind == "unit_normalization_changed"
        for change in report.changes
    )
