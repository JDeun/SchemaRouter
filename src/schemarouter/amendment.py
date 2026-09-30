"""Validation for trusted local amendment of a registered capability contract.

The application is the execution authority, so it may declare and annotate what
a result *means*. It may not change what gets executed or how a response is
validated.

`metadata` is frozen for the same reason: validation can derive requirements
from it (for example `validation._synthesized_output_schema` reads
`endpoint.metadata["output_required"]` when a source published no
`output_schema`), so a metadata-only amendment can silently change what a
response must contain. It is compared like any other unlisted aspect, not
special-cased out.

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
    # `metadata` is deliberately included: it is frozen for amendment, unlike
    # the fingerprint definitions in models.py, which exclude it by design.
    return model.model_dump(mode="json")


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
    # Checked first and raised immediately: `model_copy(update=...)` does not
    # validate, so `output_fields` can hold plain dicts instead of `FieldSpec`
    # instances. Catch that before anything below touches `.name` on them (or
    # before `_aspects`' `model_dump` below warns about it, which pytest's
    # `filterwarnings = ["error"]` would otherwise turn into a confusing
    # UserWarning instead of a clear ContractAmendmentError).
    for label, fields in (("current", current.output_fields), ("amended", amended.output_fields)):
        for field in fields:
            if not isinstance(field, FieldSpec):
                raise ContractAmendmentError(
                    f"invalid amendment for endpoint {current.name!r}: {label} "
                    f"output_fields must contain FieldSpec instances, got "
                    f"{type(field).__name__!r} — model_copy(update=...) does not "
                    "validate; construct FieldSpec explicitly"
                )

    current_aspects = _aspects(current)
    amended_aspects = _aspects(amended)
    for aspect in sorted(set(current_aspects) | set(amended_aspects)):
        if aspect in AMENDABLE_ENDPOINT_ASPECTS:
            continue
        if current_aspects.get(aspect) != amended_aspects.get(aspect):
            reason = (
                "validation can derive requirements from it, so it is frozen"
                if aspect == "metadata"
                else "execution identity is frozen"
            )
            violations.append(
                f"  endpoint {current.name!r}: {aspect} changed ({reason})"
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

    # `metadata` is included on purpose: it is frozen for amendment (see module
    # docstring), unlike `ToolSpec.fingerprint`, which excludes it by design.
    current_tool = current.model_dump(mode="json", exclude={"endpoints"})
    amended_tool = amended.model_dump(mode="json", exclude={"endpoints"})
    for aspect in sorted(set(current_tool) | set(amended_tool)):
        if current_tool.get(aspect) != amended_tool.get(aspect):
            reason = (
                "validation can derive requirements from it, so it is frozen"
                if aspect == "metadata"
                else "tool identity is frozen"
            )
            violations.append(f"  {aspect} changed ({reason})")

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
