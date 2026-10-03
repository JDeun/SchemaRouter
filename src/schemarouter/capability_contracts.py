from __future__ import annotations

from collections.abc import Iterable
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
    def validate_contract(self) -> CapabilityFieldContract:
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
    def from_field(cls, field: FieldSpec) -> CapabilityFieldContract | None:
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


class SemanticEquivalence(StrictModel):
    """Explicit semantic equivalence; never inferred from spelling similarity."""

    canonical_id: str
    aliases: set[str] = Field(default_factory=set)

    def contains(self, semantic_id: str) -> bool:
        return semantic_id == self.canonical_id or semantic_id in self.aliases


class UnitConversion(StrictModel):
    """Declared safe unit conversion relation for one dimension."""

    dimension: str
    from_unit: str
    to_unit: str


class CompatibilityContext(StrictModel):
    semantic_equivalences: list[SemanticEquivalence] = Field(default_factory=list)
    unit_conversions: list[UnitConversion] = Field(default_factory=list)

    def semantics_equivalent(self, left: str, right: str) -> bool:
        if left == right:
            return True
        return any(item.contains(left) and item.contains(right) for item in self.semantic_equivalences)

    def unit_convertible(self, dimension: str, from_unit: str, to_unit: str) -> bool:
        if from_unit == to_unit:
            return True
        return any(
            item.dimension == dimension
            and item.from_unit == from_unit
            and item.to_unit == to_unit
            for item in self.unit_conversions
        )


class CompatibilityReason(StrictModel):
    code: Literal[
        "semantic_id_mismatch",
        "semantic_equivalence_declared",
        "type_incompatible",
        "unit_incompatible",
        "dimension_incompatible",
        "qualifier_mismatch",
        "conversion_declared",
        "metadata_incomplete",
        "missing_requirement",
    ]
    detail: str


class CapabilityCompatibility(StrictModel):
    status: CompatibilityStatus
    reasons: list[CompatibilityReason] = Field(default_factory=list)

    @property
    def satisfies(self) -> bool:
        return self.status in {"exact", "compatible", "convertible"}


class CapabilityContract(StrictModel):
    capability_id: str
    requires: list[CapabilityFieldContract] = Field(default_factory=list)
    produces: list[CapabilityFieldContract] = Field(default_factory=list)


class CapabilityComposition(StrictModel):
    status: CompatibilityStatus
    requirements: dict[str, CapabilityCompatibility] = Field(default_factory=dict)

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
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityCompatibility:
    """Compare one produced field against one required field without executing anything."""

    reasons: list[CompatibilityReason] = []
    semantic_exact = required.semantic_id == produced.semantic_id
    if not semantic_exact:
        if context is None or not context.semantics_equivalent(
            required.semantic_id, produced.semantic_id
        ):
            return CapabilityCompatibility(
                status="incompatible",
                reasons=[CompatibilityReason(
                    code="semantic_id_mismatch",
                    detail=f"{produced.semantic_id!r} does not satisfy {required.semantic_id!r}",
                )],
            )
        reasons.append(CompatibilityReason(
            code="semantic_equivalence_declared",
            detail="semantic compatibility is explicitly declared",
        ))

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

    unit_convertible = False
    if required.unit and produced.unit and required.unit != produced.unit:
        dimension = required.dimension or produced.dimension
        if (
            dimension is not None
            and context is not None
            and context.unit_convertible(dimension, produced.unit, required.unit)
        ):
            unit_convertible = True
            reasons.append(CompatibilityReason(
                code="conversion_declared",
                detail=f"declared conversion {produced.unit!r} -> {required.unit!r}",
            ))
        else:
            reasons.append(CompatibilityReason(
                code="unit_incompatible",
                detail=f"{produced.unit!r} does not match required {required.unit!r}",
            ))

    incompatible_codes = {
        "type_incompatible",
        "qualifier_mismatch",
        "dimension_incompatible",
        "unit_incompatible",
    }
    if any(reason.code in incompatible_codes for reason in reasons):
        return CapabilityCompatibility(status="incompatible", reasons=reasons)

    incomplete = (
        type_compatible is None
        or (required.unit is not None and produced.unit is None)
        or (required.dimension is not None and produced.dimension is None)
    )
    if incomplete:
        reasons.append(CompatibilityReason(
            code="metadata_incomplete",
            detail="declared metadata is insufficient to prove compatibility",
        ))
        return CapabilityCompatibility(status="unknown", reasons=reasons)

    if unit_convertible:
        return CapabilityCompatibility(status="convertible", reasons=reasons)
    if required.model_dump() == produced.model_dump():
        return CapabilityCompatibility(status="exact", reasons=reasons)
    return CapabilityCompatibility(status="compatible", reasons=reasons)


def compare_capability_composition(
    producer: CapabilityContract,
    consumer: CapabilityContract,
    *,
    context: CompatibilityContext | None = None,
) -> CapabilityComposition:
    """Check whether producer outputs can satisfy every consumer requirement."""

    results: dict[str, CapabilityCompatibility] = {}
    statuses: list[CompatibilityStatus] = []
    for required in consumer.requires:
        candidates = [
            compare_capability_fields(required, produced, context=context)
            for produced in producer.produces
        ]
        satisfiable = [candidate for candidate in candidates if candidate.satisfies]
        unknown = [candidate for candidate in candidates if candidate.status == "unknown"]
        if satisfiable:
            result = min(satisfiable, key=lambda item: _status_rank(item.status))
        elif unknown:
            result = unknown[0]
        else:
            result = CapabilityCompatibility(
                status="incompatible",
                reasons=[CompatibilityReason(
                    code="missing_requirement",
                    detail=f"producer does not satisfy required semantic field {required.semantic_id!r}",
                )],
            )
        results[required.semantic_id] = result
        statuses.append(result.status)

    return CapabilityComposition(
        status=_composition_status(statuses),
        requirements=results,
    )


def _status_rank(status: CompatibilityStatus) -> int:
    return {"exact": 0, "compatible": 1, "convertible": 2, "unknown": 3, "incompatible": 4}[status]


def _composition_status(statuses: Iterable[CompatibilityStatus]) -> CompatibilityStatus:
    values = list(statuses)
    if not values:
        return "exact"
    if "incompatible" in values:
        return "incompatible"
    if "unknown" in values:
        return "unknown"
    if "convertible" in values:
        return "convertible"
    if "compatible" in values:
        return "compatible"
    return "exact"
