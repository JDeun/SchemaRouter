"""Host-reviewed, source-revision-pinned semantic annotations for native adapters.

This does not infer provider fields or grant read-only, execution, credentials,
license permission or access. The trusted host owns the approval out of band.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import model_validator

from .models import FieldSpec, StrictModel, ToolSpec

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SEMANTIC = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]{0,159}\Z")
_MAX_MAPPINGS = 64
_MAX_BYTES = 16384
_SCALARS = frozenset({"string", "integer", "number", "boolean"})


def _reviewed_text(value: str) -> bool:
    return (
        type(value) is str and 1 <= len(value) <= 160
        and value == value.strip()
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


class HostSemanticMapping(StrictModel):
    """One native existing output field or input parameter, never a new field."""

    endpoint_name: str
    expected_endpoint_fingerprint: str
    member_kind: Literal["output_field", "input_parameter"]
    member_name: str
    semantic_id: str

    @model_validator(mode="after")
    def validate_source_mapping(self) -> HostSemanticMapping:
        if (
            not _reviewed_text(self.endpoint_name)
            or not _reviewed_text(self.member_name)
            or not _HEX64.fullmatch(self.expected_endpoint_fingerprint)
            or not _SEMANTIC.fullmatch(self.semantic_id)
        ):
            raise ValueError("invalid bounded source-pinned semantic mapping")
        return self


class HostSemanticAttestation(StrictModel):
    """Local owner's reviewed, exact adapter-result fingerprint receipt.

    `reviewed_by` is a caller-supplied provenance label, NOT a signature.
    """

    expected_tool_key: str
    expected_tool_fingerprint: str
    source_type: str
    license: str
    reviewed_by: str
    mappings: tuple[HostSemanticMapping, ...]

    @model_validator(mode="after")
    def validate_attestation(self) -> HostSemanticAttestation:
        if (
            not all(_reviewed_text(x) for x in (
                self.expected_tool_key, self.source_type,
                self.license, self.reviewed_by,
            ))
            or not _HEX64.fullmatch(self.expected_tool_fingerprint)
            or not 1 <= len(self.mappings) <= _MAX_MAPPINGS
            or len({
                (x.endpoint_name, x.member_kind, x.member_name)
                for x in self.mappings
            }) != len(self.mappings)
            or len(self.model_dump_json().encode("utf-8")) > _MAX_BYTES
        ):
            raise ValueError("invalid bounded host semantic attestation")
        return self


def apply_host_semantic_attestation(
    source_tool: ToolSpec,
    *,
    attestation: HostSemanticAttestation,
) -> ToolSpec:
    """Build a NEW native ToolSpec with host-attested existing semantic edges.

    Strictly requires original adapter-native scalar fields/inputs. A
    metadata-only tool catalog cannot be 'completed' by fabricating
    output fields from test gold or natural-language descriptions.
    """
    if type(source_tool) is not ToolSpec or type(attestation) is not HostSemanticAttestation:
        raise ValueError("trusted native tool and attestation required")
    try:
        reviewed = HostSemanticAttestation.model_validate(
            attestation.model_dump(mode="python"), strict=True,
        )
        original = ToolSpec.model_validate(
            source_tool.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("native source or approval mutated after review") from exc

    if (
        original.key != reviewed.expected_tool_key
        or original.fingerprint != reviewed.expected_tool_fingerprint
        or original.source_type != reviewed.source_type
        or original.license != reviewed.license
    ):
        raise ValueError("source-owned tool contract differs from reviewed revision")

    amended = original.model_copy(deep=True)
    for mapping in reviewed.mappings:
        try:
            original_ep = original.endpoint(mapping.endpoint_name)
            changed_ep = amended.endpoint(mapping.endpoint_name)
        except KeyError:
            raise ValueError("mapping refers to nonexistent native endpoint") from None
        if original_ep.fingerprint != mapping.expected_endpoint_fingerprint:
            raise ValueError("native endpoint changed since semantic review")
        members = (
            changed_ep.output_fields
            if mapping.member_kind == "output_field"
            else changed_ep.parameters
        )
        exact = [member for member in members if member.name == mapping.member_name]
        if len(exact) != 1:
            raise ValueError("semantic mapping cannot invent native schema members")
        member = exact[0]
        # No assuming a broad provider schema is equivalent to a scalar
        # contract: subtype/pattern/enum/nested constraints remain UNKNOWN.
        if (
            type(member.json_schema) is not dict
            or set(member.json_schema) != {"type"}
            or member.json_schema.get("type") not in _SCALARS
        ):
            raise ValueError("unproved native member JSON Schema must abstain")
        if isinstance(member, FieldSpec) and member.unit_normalization is not None:
            raise ValueError("unproved unit conversion cannot create semantic edge")
        if member.semantic_id is not None and member.semantic_id != mapping.semantic_id:
            raise ValueError("source semantic identity conflicts with host review")
        member.semantic_id = mapping.semantic_id

    # Validate against the original native endpoint/output field model, so
    # no unreviewed field, argument, tool metadata or access mode is added.
    validated = ToolSpec.model_validate(amended.model_dump(mode="python"), strict=True)
    if source_tool.fingerprint != reviewed.expected_tool_fingerprint:
        raise ValueError("source changed during semantic attestation")
    return validated
