from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import FieldSpec, StrictModel

CompatibilityStatus = Literal["exact", "compatible", "convertible", "incompatible", "unknown"]


class CapabilityFieldContract(StrictModel):
    """Provider-neutral field requirement/production contract."""

    semantic_id: str
    json_schema: dict = Field(default_factory=dict)
    unit: str | None = None
    dimension: str | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract(self) -> "CapabilityFieldContract":
        if not self.semantic_id.strip() or self.semantic_id != self.semantic_id.strip():
            raise ValueError("semantic_id must be non-empty and have no surrounding whitespace")
        if self.unit is not None and (not self.unit.strip() or self.unit != self.unit.strip()):
            raise ValueError("unit must be non-empty and have no surrounding whitespace")
        if self.dimension is not None and (
            not self.dimension.strip() or self.dimension != self.dimension.strip()
        ):
            raise ValueError("dimension must be non-empty and have no surrounding whitespace")
        return self

    @classmethod
    def from_field(cls, field: FieldSpec) -> "CapabilityFieldContract | None":
        if field.semantic_id is None:
            return None
        normalization = field.unit_normalization
        return cls(
            semantic_id=field.semantic_id,
            json_schema=field.json_schema,
            unit=normalization.canonical_unit if normalization is not None else field.unit,
            dimension=normalization.dimension if normalization is not None else None,
            qualifiers=field.qualifiers,
        )


class CompatibilityReason(StrictModel):
    code: Literal[
        "semantic_id_mismatch",
        "type_incompatible",
        "unit_incompatible",
        "dimension_incompatible",
        "qualifier_mismatch",
        "conversion_declared",
        "metadata_incomplete",
    ]
    detail: str


class CapabilityCompatibility(StrictModel):
    status: CompatibilityStatus
    reasons: list[CompatibilityReason] = Field(default_factory=list)

    @property
    def satisfies(self) -> bool:
        return self.status in {"exact", "compatible", "convertible"}


def _types(schema: dict) -> set[str]:
    raw = schema.get("type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {value for value in raw if isinstance(value, str)}
    return set()


def _type_compatible(required: dict, produced: dict) -> bool | None:
    required_types = _types(required)
    produced_types = _types(produced)
    if not required_types or not produced_types:
        return None
    for value in produced_types:
        if value in required_types:
            continue
        if value == "integer" and "number" in required_types:
            continue
        return False
    return True


def compare_capability_fields(
    required: CapabilityFieldContract,
    produced: CapabilityFieldContract,
) -> CapabilityCompatibility:
    """Compare one produced field against one required field without executing anything."""

    reasons: list[CompatibilityReason] = []
    if required.semantic_id != produced.semantic_id:
        return CapabilityCompatibility(
            status="incompatible",
            reasons=[CompatibilityReason(
                code="semantic_id_mismatch",
                detail=f"{produced.semantic_id!r} does not satisfy {required.semantic_id!r}",
            )],
        )

    type_compatible = _type_compatible(required.json_schema, produced.json_schema)
    if type_compatible is False:
        reasons.append(CompatibilityReason(
            code="type_incompatible",
            detail="produced JSON type is not assignable to the required JSON type",
        ))

    for key, value in required.qualifiers.items():
        if produced.qualifiers.get(key) != value:
            reasons.append(CompatibilityReason(
                code="qualifier_mismatch",
                detail=f"required qualifier {key}={value!r} is not produced",
            ))

    if required.dimension and produced.dimension and required.dimension != produced.dimension:
        reasons.append(CompatibilityReason(
            code="dimension_incompatible",
            detail=f"{produced.dimension!r} does not match required {required.dimension!r}",
        ))

    if required.unit and produced.unit and required.unit != produced.unit:
        reasons.append(CompatibilityReason(
            code="unit_incompatible",
            detail=f"{produced.unit!r} does not match required {required.unit!r}",
        ))

    if reasons:
        return CapabilityCompatibility(status="incompatible", reasons=reasons)

    incomplete = (
        type_compatible is None
        or (required.unit is not None and produced.unit is None)
        or (required.dimension is not None and produced.dimension is None)
    )
    if incomplete:
        return CapabilityCompatibility(
            status="unknown",
            reasons=[CompatibilityReason(
                code="metadata_incomplete",
                detail="declared metadata is insufficient to prove compatibility",
            )],
        )

    if required.model_dump() == produced.model_dump():
        return CapabilityCompatibility(status="exact")
    return CapabilityCompatibility(status="compatible")
