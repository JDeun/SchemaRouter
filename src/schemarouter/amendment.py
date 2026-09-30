"""Validation for trusted local amendment of a registered capability contract.

The application is the execution authority, so it may declare and annotate what
a result *means*. It may not change what gets executed or how a response is
validated.

This is deliberately not `schema_diff.compare_tool_specs`: that function is
documented as diagnostic only and classifies differences for reporting. Here the
rule must be authoritative and fail closed, so aspects are allowlisted by name
and anything unrecognised counts as frozen.
"""
from __future__ import annotations

from .errors import ContractAmendmentError
from .models import EndpointSpec, FieldSpec, ToolSpec

# Everything not named here is frozen, including fields added to the models in
# future versions.
AMENDABLE_ENDPOINT_ASPECTS = frozenset({"description", "operation_aliases", "output_fields"})
AMENDABLE_FIELD_ASPECTS = frozenset(
    {
        "semantic_id",
        "description",
        "aliases",
        "path",
        "result_path",
        "unit",
        "unit_normalization",
        "qualifiers",
        "identifier",
        "source_type",
        "license",
    }
)


def _aspects(model: EndpointSpec | FieldSpec) -> dict[str, object]:
    return model.model_dump(mode="json", exclude={"metadata"})


def _check_field(
    current: FieldSpec,
    amended: FieldSpec,
    *,
    endpoint_name: str,
    violations: list[str],
) -> None:
    current_aspects = _aspects(current)
    amended_aspects = _aspects(amended)
    for aspect in sorted(set(current_aspects) | set(amended_aspects)):
        if aspect in AMENDABLE_FIELD_ASPECTS:
            continue
        if current_aspects.get(aspect) != amended_aspects.get(aspect):
            violations.append(
                f"  endpoint {endpoint_name!r}: field {current.name!r}: "
                f"{aspect} changed (validation shape is frozen)"
            )


def _check_endpoint(
    current: EndpointSpec,
    amended: EndpointSpec,
    *,
    violations: list[str],
) -> None:
    current_aspects = _aspects(current)
    amended_aspects = _aspects(amended)
    for aspect in sorted(set(current_aspects) | set(amended_aspects)):
        if aspect in AMENDABLE_ENDPOINT_ASPECTS:
            continue
        if current_aspects.get(aspect) != amended_aspects.get(aspect):
            violations.append(
                f"  endpoint {current.name!r}: {aspect} changed "
                "(execution identity is frozen)"
            )

    amended_fields = {field.name: field for field in amended.output_fields}
    for field in current.output_fields:
        replacement = amended_fields.get(field.name)
        if replacement is None:
            violations.append(
                f"  endpoint {current.name!r}: field {field.name!r} removed "
                "(removing a published declaration is not amendable)"
            )
            continue
        _check_field(
            field, replacement, endpoint_name=current.name, violations=violations
        )


def validate_amendment(current: ToolSpec, amended: ToolSpec) -> None:
    """Raise `ContractAmendmentError` unless `amended` only declares or annotates."""
    violations: list[str] = []

    current_tool = current.model_dump(mode="json", exclude={"metadata", "endpoints"})
    amended_tool = amended.model_dump(mode="json", exclude={"metadata", "endpoints"})
    for aspect in sorted(set(current_tool) | set(amended_tool)):
        if current_tool.get(aspect) != amended_tool.get(aspect):
            violations.append(f"  {aspect} changed (tool identity is frozen)")

    current_endpoints = {endpoint.name: endpoint for endpoint in current.endpoints}
    amended_endpoints = {endpoint.name: endpoint for endpoint in amended.endpoints}
    if set(current_endpoints) != set(amended_endpoints):
        added = sorted(set(amended_endpoints) - set(current_endpoints))
        removed = sorted(set(current_endpoints) - set(amended_endpoints))
        if added:
            violations.append(f"  endpoints added: {added} (the endpoint set is frozen)")
        if removed:
            violations.append(f"  endpoints removed: {removed} (the endpoint set is frozen)")
    else:
        for name, endpoint in current_endpoints.items():
            _check_endpoint(endpoint, amended_endpoints[name], violations=violations)

    if violations:
        raise ContractAmendmentError(
            f"refused amendment of {current.key!r}:\n" + "\n".join(violations)
        )
