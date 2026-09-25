from __future__ import annotations

from .models import EndpointSpec, EvidenceRequirements, FieldSpec, ToolSpec


def _selected_answer_fields(
    endpoint: EndpointSpec,
    selected_fields: list[str],
) -> list[FieldSpec]:
    field_map = {field.name: field for field in endpoint.output_fields}
    return [
        field_map[name]
        for name in selected_fields
        if name in field_map and not field_map[name].identifier
    ]


def available_evidence(
    tool: ToolSpec,
    endpoint: EndpointSpec,
    selected_fields: list[str],
) -> EvidenceRequirements:
    """Return evidence actually declared by the selected route surface."""

    answer_fields = _selected_answer_fields(endpoint, selected_fields)

    if tool.source_type is not None:
        source_type = tool.source_type
    else:
        field_source_types = {
            field.source_type
            for field in answer_fields
            if field.source_type is not None
        }
        source_type = (
            next(iter(field_source_types))
            if len(field_source_types) == 1
            and len(field_source_types) == len(
                {
                    field.source_type
                    for field in answer_fields
                }
            )
            else None
        )

    return EvidenceRequirements(
        provenance=bool(
            tool.source_type
            or any(field.source_type for field in answer_fields)
        ),
        license=bool(tool.license) or (
            bool(answer_fields)
            and all(field.license for field in answer_fields)
        ),
        units=bool(answer_fields) and all(
            field.unit for field in answer_fields
        ),
        source_type=source_type,
    )


def global_evidence_status(
    tool: ToolSpec,
    endpoint: EndpointSpec,
    selected_fields: list[str],
    required: EvidenceRequirements,
) -> tuple[bool, EvidenceRequirements, list[str]]:
    """Assess global evidence requirements against trusted route declarations."""

    answer_fields = _selected_answer_fields(endpoint, selected_fields)
    available = available_evidence(tool, endpoint, selected_fields)

    source_type_available = (
        required.source_type is None
        or tool.source_type == required.source_type
        or (
            bool(answer_fields)
            and all(
                field.source_type == required.source_type
                for field in answer_fields
            )
        )
    )

    missing: list[str] = []
    if required.provenance and not available.provenance:
        missing.append("provenance")
    if required.license and not available.license:
        missing.append("license")
    if required.units and not available.units:
        missing.append("units")
    if required.source_type is not None and not source_type_available:
        missing.append(f"source_type={required.source_type}")

    return not missing, available, missing


def field_evidence_status(
    tool: ToolSpec,
    endpoint: EndpointSpec,
    selected_fields: list[str],
    required: dict[str, EvidenceRequirements],
) -> tuple[bool, dict[str, dict[str, object]], list[str]]:
    """Assess local-field evidence requirements against trusted field declarations."""

    field_map = {field.name: field for field in endpoint.output_fields}
    selected = set(selected_fields)
    available_context: dict[str, dict[str, object]] = {}
    missing: list[str] = []

    for field_name, requirement in required.items():
        field = field_map.get(field_name)
        if field is None or field_name not in selected or field.identifier:
            missing.append(f"{field_name}.selected_field")
            continue

        provenance_available = bool(tool.source_type or field.source_type)
        license_available = bool(tool.license or field.license)
        units_available = bool(field.unit)
        source_type_available = (
            requirement.source_type is None
            or tool.source_type == requirement.source_type
            or field.source_type == requirement.source_type
        )

        available_context[field_name] = {
            "provenance": provenance_available,
            "license": license_available,
            "units": units_available,
            "source_type": source_type_available,
        }

        if requirement.provenance and not provenance_available:
            missing.append(f"{field_name}.provenance")
        if requirement.license and not license_available:
            missing.append(f"{field_name}.license")
        if requirement.units and not units_available:
            missing.append(f"{field_name}.units")
        if requirement.source_type is not None and not source_type_available:
            missing.append(
                f"{field_name}.source_type={requirement.source_type}"
            )

    return not missing, available_context, missing
