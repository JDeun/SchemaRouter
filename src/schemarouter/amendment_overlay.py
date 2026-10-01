from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import Field

from .amendment import (
    AMENDABLE_ENDPOINT_ASPECTS,
    AMENDABLE_FIELD_ASPECTS,
    validate_amendment,
)
from .errors import ContractAmendmentError
from .models import EndpointSpec, FieldSpec, StrictModel, ToolSpec

_AMENDMENT_OVERLAY_KEY = "schemarouter_trusted_amendment_overlay"
_OVERLAY_VERSION = 1


class AmendmentAspectPatch(StrictModel):
    original: Any = None
    desired: Any = None


class AmendmentFieldOverlay(StrictModel):
    origin: Literal["provider", "local"]
    aspects: dict[str, AmendmentAspectPatch] = Field(default_factory=dict)
    desired_field: dict[str, Any] | None = None


class AmendmentEndpointOverlay(StrictModel):
    aspects: dict[str, AmendmentAspectPatch] = Field(default_factory=dict)
    fields: dict[str, AmendmentFieldOverlay] = Field(default_factory=dict)


class CapabilityAmendmentOverlay(StrictModel):
    version: Literal[1] = _OVERLAY_VERSION
    endpoints: dict[str, AmendmentEndpointOverlay] = Field(default_factory=dict)


def _json_value(value: Any) -> Any:
    if isinstance(value, StrictModel):
        return value.model_dump(mode="json")
    return deepcopy(value)


def _without_overlay_metadata(tool: ToolSpec) -> ToolSpec:
    clean = tool.model_copy(deep=True)
    clean.metadata.pop(_AMENDMENT_OVERLAY_KEY, None)
    return clean


def amendment_overlay(tool: ToolSpec) -> CapabilityAmendmentOverlay | None:
    raw = tool.metadata.get(_AMENDMENT_OVERLAY_KEY)
    if raw is None:
        return None
    try:
        return CapabilityAmendmentOverlay.model_validate(raw)
    except Exception as exc:
        raise ContractAmendmentError(
            f"invalid trusted amendment overlay for {tool.key!r}: {type(exc).__name__}"
        ) from exc


def _field_dict(field: FieldSpec) -> dict[str, Any]:
    return field.model_dump(mode="json")


def _endpoint_dict(endpoint: EndpointSpec) -> dict[str, Any]:
    return endpoint.model_dump(mode="json")


def _endpoint_map(tool: ToolSpec) -> dict[str, EndpointSpec]:
    return {endpoint.name: endpoint for endpoint in tool.endpoints}


def _field_map(endpoint: EndpointSpec) -> dict[str, FieldSpec]:
    return {field.name: field for field in endpoint.output_fields}


def _clean_overlay(overlay: CapabilityAmendmentOverlay) -> CapabilityAmendmentOverlay:
    cleaned: dict[str, AmendmentEndpointOverlay] = {}
    for endpoint_name, endpoint_overlay in overlay.endpoints.items():
        fields = {
            name: field_overlay
            for name, field_overlay in endpoint_overlay.fields.items()
            if field_overlay.origin == "local" or field_overlay.aspects
        }
        if endpoint_overlay.aspects or fields:
            cleaned[endpoint_name] = AmendmentEndpointOverlay(
                aspects=dict(endpoint_overlay.aspects),
                fields=fields,
            )
    return CapabilityAmendmentOverlay(endpoints=cleaned)


def strip_amendment_overlay(tool: ToolSpec) -> ToolSpec:
    """Reconstruct the last accepted raw provider contract from an effective ToolSpec."""

    overlay = amendment_overlay(tool)
    clean = _without_overlay_metadata(tool)
    if overlay is None:
        return clean

    endpoint_overlays = overlay.endpoints
    rebuilt: list[EndpointSpec] = []
    for endpoint in clean.endpoints:
        endpoint_overlay = endpoint_overlays.get(endpoint.name)
        if endpoint_overlay is None:
            rebuilt.append(endpoint)
            continue

        data = _endpoint_dict(endpoint)
        for aspect, patch in endpoint_overlay.aspects.items():
            data[aspect] = deepcopy(patch.original)

        fields = {field.name: _field_dict(field) for field in endpoint.output_fields}
        order = [field.name for field in endpoint.output_fields]
        for field_name, field_overlay in endpoint_overlay.fields.items():
            if field_overlay.origin == "local":
                if field_name not in fields:
                    raise ContractAmendmentError(
                        f"trusted amendment overlay for endpoint {endpoint.name!r} "
                        f"expects local field {field_name!r} to exist"
                    )
                fields.pop(field_name, None)
                order = [name for name in order if name != field_name]
                continue

            raw_field = fields.get(field_name)
            if raw_field is None:
                raise ContractAmendmentError(
                    f"trusted amendment overlay for endpoint {endpoint.name!r} "
                    f"lost provider field {field_name!r}"
                )
            for aspect, patch in field_overlay.aspects.items():
                raw_field[aspect] = deepcopy(patch.original)

        data["output_fields"] = [fields[name] for name in order]
        rebuilt.append(EndpointSpec.model_validate(data))

    clean.endpoints = rebuilt
    return ToolSpec.model_validate(clean.model_dump(mode="json"))


def _merge_endpoint_patch(
    overlay: CapabilityAmendmentOverlay,
    *,
    baseline: EndpointSpec,
    current: EndpointSpec,
    amended: EndpointSpec,
) -> None:
    endpoint_overlay = overlay.endpoints.get(
        current.name,
        AmendmentEndpointOverlay(),
    )

    for aspect in AMENDABLE_ENDPOINT_ASPECTS - {"output_fields"}:
        old_value = getattr(current, aspect)
        new_value = getattr(amended, aspect)
        if old_value == new_value:
            continue
        baseline_value = getattr(baseline, aspect)
        if new_value == baseline_value:
            endpoint_overlay.aspects.pop(aspect, None)
        else:
            endpoint_overlay.aspects[aspect] = AmendmentAspectPatch(
                original=_json_value(baseline_value),
                desired=_json_value(new_value),
            )

    baseline_fields = _field_map(baseline)
    current_fields = _field_map(current)
    amended_fields = _field_map(amended)

    for field_name, amended_field in amended_fields.items():
        current_field = current_fields.get(field_name)
        existing_overlay = endpoint_overlay.fields.get(field_name)

        if current_field is None:
            endpoint_overlay.fields[field_name] = AmendmentFieldOverlay(
                origin="local",
                desired_field=_field_dict(amended_field),
            )
            continue

        if existing_overlay is not None and existing_overlay.origin == "local":
            if amended_field != current_field:
                endpoint_overlay.fields[field_name] = AmendmentFieldOverlay(
                    origin="local",
                    desired_field=_field_dict(amended_field),
                )
            continue

        baseline_field = baseline_fields.get(field_name)
        if baseline_field is None:
            raise ContractAmendmentError(
                f"cannot reproduce trusted amendment for endpoint {current.name!r}: "
                f"provider baseline for field {field_name!r} is missing"
            )

        field_overlay = existing_overlay or AmendmentFieldOverlay(origin="provider")
        for aspect in AMENDABLE_FIELD_ASPECTS:
            old_value = getattr(current_field, aspect)
            new_value = getattr(amended_field, aspect)
            if old_value == new_value:
                continue
            baseline_value = getattr(baseline_field, aspect)
            if new_value == baseline_value:
                field_overlay.aspects.pop(aspect, None)
            else:
                field_overlay.aspects[aspect] = AmendmentAspectPatch(
                    original=_json_value(baseline_value),
                    desired=_json_value(new_value),
                )

        if field_overlay.aspects:
            endpoint_overlay.fields[field_name] = field_overlay
        else:
            endpoint_overlay.fields.pop(field_name, None)

    if endpoint_overlay.aspects or endpoint_overlay.fields:
        overlay.endpoints[current.name] = endpoint_overlay
    else:
        overlay.endpoints.pop(current.name, None)


def prepare_amended_capability(current: ToolSpec, amended: ToolSpec) -> ToolSpec:
    """Validate a trusted local amendment and persist its reproducible overlay."""

    current_effective = _without_overlay_metadata(current)
    amended_clean = _without_overlay_metadata(amended)
    validate_amendment(current_effective, amended_clean)

    baseline = strip_amendment_overlay(current)
    overlay = amendment_overlay(current) or CapabilityAmendmentOverlay()

    baseline_endpoints = _endpoint_map(baseline)
    current_endpoints = _endpoint_map(current_effective)
    amended_endpoints = _endpoint_map(amended_clean)
    for endpoint_name, current_endpoint in current_endpoints.items():
        baseline_endpoint = baseline_endpoints.get(endpoint_name)
        amended_endpoint = amended_endpoints.get(endpoint_name)
        if baseline_endpoint is None or amended_endpoint is None:
            raise ContractAmendmentError(
                f"cannot reproduce trusted amendment for endpoint {endpoint_name!r}"
            )
        _merge_endpoint_patch(
            overlay,
            baseline=baseline_endpoint,
            current=current_endpoint,
            amended=amended_endpoint,
        )

    overlay = _clean_overlay(overlay)
    result = amended_clean.model_copy(deep=True)
    if overlay.endpoints:
        result.metadata[_AMENDMENT_OVERLAY_KEY] = overlay.model_dump(mode="json")
    else:
        result.metadata.pop(_AMENDMENT_OVERLAY_KEY, None)
    return ToolSpec.model_validate(result.model_dump(mode="json"))


def reapply_amendment_overlay(
    raw_candidate: ToolSpec,
    overlay: CapabilityAmendmentOverlay,
) -> ToolSpec:
    """Apply trusted local semantics to one freshly inspected provider contract."""

    raw = _without_overlay_metadata(raw_candidate)
    raw_endpoints = _endpoint_map(raw)
    rebuilt: list[EndpointSpec] = []
    rebased = CapabilityAmendmentOverlay()

    for endpoint in raw.endpoints:
        endpoint_overlay = overlay.endpoints.get(endpoint.name)
        if endpoint_overlay is None:
            rebuilt.append(endpoint)
            continue

        data = _endpoint_dict(endpoint)
        rebased_endpoint = AmendmentEndpointOverlay()

        for aspect, patch in endpoint_overlay.aspects.items():
            if aspect not in AMENDABLE_ENDPOINT_ASPECTS - {"output_fields"}:
                raise ContractAmendmentError(
                    f"trusted amendment overlay contains unsupported endpoint aspect {aspect!r}"
                )
            rebased_endpoint.aspects[aspect] = AmendmentAspectPatch(
                original=_json_value(getattr(endpoint, aspect)),
                desired=deepcopy(patch.desired),
            )
            data[aspect] = deepcopy(patch.desired)

        raw_fields = _field_map(endpoint)
        field_data = {field.name: _field_dict(field) for field in endpoint.output_fields}
        order = [field.name for field in endpoint.output_fields]

        for field_name, field_overlay in endpoint_overlay.fields.items():
            if field_overlay.origin == "local":
                if field_name in raw_fields:
                    raise ContractAmendmentError(
                        f"provider now publishes field {field_name!r} in endpoint "
                        f"{endpoint.name!r}, conflicting with a trusted local field"
                    )
                if field_overlay.desired_field is None:
                    raise ContractAmendmentError(
                        f"local amendment field {field_name!r} has no reproducible definition"
                    )
                local_field = FieldSpec.model_validate(field_overlay.desired_field)
                field_data[field_name] = _field_dict(local_field)
                order.append(field_name)
                rebased_endpoint.fields[field_name] = field_overlay.model_copy(deep=True)
                continue

            raw_field = raw_fields.get(field_name)
            if raw_field is None:
                raise ContractAmendmentError(
                    f"provider removed or renamed amendment target field {field_name!r} "
                    f"in endpoint {endpoint.name!r}"
                )

            patched = _field_dict(raw_field)
            rebased_field = AmendmentFieldOverlay(origin="provider")
            for aspect, patch in field_overlay.aspects.items():
                if aspect not in AMENDABLE_FIELD_ASPECTS:
                    raise ContractAmendmentError(
                        f"trusted amendment overlay contains unsupported field aspect {aspect!r}"
                    )
                rebased_field.aspects[aspect] = AmendmentAspectPatch(
                    original=_json_value(getattr(raw_field, aspect)),
                    desired=deepcopy(patch.desired),
                )
                patched[aspect] = deepcopy(patch.desired)
            field_data[field_name] = patched
            rebased_endpoint.fields[field_name] = rebased_field

        data["output_fields"] = [field_data[name] for name in order]
        rebuilt.append(EndpointSpec.model_validate(data))
        rebased.endpoints[endpoint.name] = rebased_endpoint

    missing_endpoints = sorted(set(overlay.endpoints) - set(raw_endpoints))
    if missing_endpoints:
        raise ContractAmendmentError(
            "provider removed or renamed amendment target endpoints: "
            + ", ".join(repr(name) for name in missing_endpoints)
        )

    effective = raw.model_copy(deep=True)
    effective.endpoints = rebuilt
    effective = ToolSpec.model_validate(effective.model_dump(mode="json"))

    # This is the authoritative safety gate: the overlay may only perform the
    # same semantic declaration/annotation operations as amend_capability().
    validate_amendment(raw, effective)

    rebased = _clean_overlay(rebased)
    if rebased.endpoints:
        effective.metadata[_AMENDMENT_OVERLAY_KEY] = rebased.model_dump(mode="json")
    return ToolSpec.model_validate(effective.model_dump(mode="json"))
