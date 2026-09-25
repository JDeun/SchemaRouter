from __future__ import annotations

from .models import EndpointSpec, EvidenceRequirements, FieldSpec, ToolSpec


def _semantic_key(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def selected_answer_fields(
    endpoint: EndpointSpec,
    selected_fields: list[str] | tuple[str, ...],
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
    selected_fields: list[str] | tuple[str, ...],
) -> EvidenceRequirements:
    """Return evidence actually declared by the selected route."""

    answer_fields = selected_answer_fields(endpoint, selected_fields)
    source_type: str | None = tool.source_type
    if source_type is None and answer_fields:
        source_types = {field.source_type for field in answer_fields}
        if len(source_types) == 1:
            only = next(iter(source_types))
            if only is not None:
                source_type = only

    return EvidenceRequirements(
        provenance=bool(
            tool.source_type
            or any(field.source_type for field in answer_fields)
        ),
        license=bool(tool.license) or (
            bool(answer_fields)
            and all(field.license for field in answer_fields)
        ),
        units=bool(answer_fields) and all(field.unit for field in answer_fields),
        source_type=source_type,
    )


def missing_global_evidence(
    tool: ToolSpec,
    endpoint: EndpointSpec,
    selected_fields: list[str] | tuple[str, ...],
    requested: EvidenceRequirements,
) -> list[str]:
    answer_fields = selected_answer_fields(endpoint, selected_fields)
    provenance_available = bool(
        tool.source_type or any(field.source_type for field in answer_fields)
    )
    license_available = bool(tool.license) or (
        bool(answer_fields) and all(field.license for field in answer_fields)
    )
    units_available = bool(answer_fields) and all(
        field.unit for field in answer_fields
    )
    source_type_available = (
        requested.source_type is None
        or tool.source_type == requested.source_type
        or (
            bool(answer_fields)
            and all(
                field.source_type == requested.source_type
                for field in answer_fields
            )
        )
    )

    missing: list[str] = []
    if requested.provenance and not provenance_available:
        missing.append("provenance")
    if requested.license and not license_available:
        missing.append("license")
    if requested.units and not units_available:
        missing.append("units")
    if requested.source_type is not None and not source_type_available:
        missing.append(f"source_type={requested.source_type}")
    return missing


def match_semantic_field_evidence(
    endpoint: EndpointSpec,
    selected_fields: list[str] | tuple[str, ...],
    requested: dict[str, EvidenceRequirements],
) -> dict[str, tuple[str, EvidenceRequirements]]:
    requested_by_semantic = {
        _semantic_key(semantic_id): (semantic_id, requirement)
        for semantic_id, requirement in requested.items()
    }
    field_map = {field.name: field for field in endpoint.output_fields}
    matched: dict[str, tuple[str, EvidenceRequirements]] = {}
    for field_name in selected_fields:
        field = field_map.get(field_name)
        if field is None or field.identifier:
            continue
        item = requested_by_semantic.get(
            _semantic_key(field.semantic_id or field.name)
        )
        if item is not None:
            matched[field_name] = item
    return matched


def missing_local_field_evidence(
    tool: ToolSpec,
    endpoint: EndpointSpec,
    requested: dict[str, EvidenceRequirements],
) -> list[str]:
    """Validate requirements keyed by provider-local field names."""

    field_map = {field.name: field for field in endpoint.output_fields}
    missing: list[str] = []
    for field_name, requirement in requested.items():
        field = field_map.get(field_name)
        if field is None or field.identifier:
            missing.append(f"{field_name}.declared_answer_field")
            continue

        provenance_available = bool(tool.source_type or field.source_type)
        license_available = bool(tool.license or field.license)
        units_available = bool(field.unit)
        source_type_available = (
            requirement.source_type is None
            or tool.source_type == requirement.source_type
            or field.source_type == requirement.source_type
        )

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
    return missing