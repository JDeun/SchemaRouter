from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Literal

from pydantic import Field, model_validator

from .models import StrictModel


EntityKind = Literal["document", "material", "chemical", "generic"]
MergeMode = Literal["deduplicate", "preserve_observations"]


class SourceRecord(StrictModel):
    """One provider record before cross-provider identity resolution."""

    provider: str
    entity_kind: EntityKind = "generic"
    identifiers: dict[str, str] = Field(default_factory=dict)
    fields: dict[str, Any] = Field(default_factory=dict)
    field_units: dict[str, str] = Field(default_factory=dict)
    qualifiers: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> "SourceRecord":
        if not self.provider.strip():
            raise ValueError("provider must be non-empty")
        if any(not key.strip() or not value.strip() for key, value in self.identifiers.items()):
            raise ValueError("identifiers require non-empty keys and values")
        return self


class FieldObservation(StrictModel):
    """A provider-specific observation retained for scientific comparison."""

    field: str
    value: Any
    provider: str
    unit: str | None = None
    qualifiers: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class AggregatedField(StrictModel):
    name: str
    mode: MergeMode
    value: Any | None = None
    observations: list[FieldObservation] = Field(default_factory=list)
    agreement: bool | None = None


class CanonicalEntity(StrictModel):
    """One resolved entity with provider evidence kept explicit."""

    entity_kind: EntityKind
    canonical_key: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    providers: list[str] = Field(default_factory=list)
    fields: dict[str, AggregatedField] = Field(default_factory=dict)


_DOCUMENT_IDENTIFIER_PRIORITY = ("doi", "pmid", "pmcid", "arxiv")
_SCIENTIFIC_KINDS = {"material", "chemical"}


def _normalise_identifier(kind: str, value: str) -> str:
    value = value.strip()
    lowered = kind.casefold()
    if lowered == "doi":
        value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
        value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    elif lowered == "arxiv":
        value = re.sub(r"^arxiv:\s*", "", value, flags=re.I)
    return value.casefold()


def canonical_identity(record: SourceRecord) -> str:
    """Return a stable identity key without guessing from titles or values."""

    normalized = {
        key.casefold(): _normalise_identifier(key, value)
        for key, value in record.identifiers.items()
    }
    priority = (
        _DOCUMENT_IDENTIFIER_PRIORITY
        if record.entity_kind == "document"
        else tuple(sorted(normalized))
    )
    for identifier_type in priority:
        value = normalized.get(identifier_type)
        if value:
            return f"{record.entity_kind}:{identifier_type}:{value}"

    # No fuzzy title/name merging: false merges are more damaging than duplicates.
    payload = json.dumps(
        {
            "provider": record.provider,
            "identifiers": normalized,
            "fields": record.fields,
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return f"{record.entity_kind}:unresolved:{__import__('hashlib').sha256(payload.encode()).hexdigest()}"


def _default_merge_mode(entity_kind: EntityKind, field: str) -> MergeMode:
    if entity_kind in _SCIENTIFIC_KINDS:
        return "preserve_observations"
    return "deduplicate"


def aggregate_records(
    records: list[SourceRecord],
    *,
    field_modes: dict[str, MergeMode] | None = None,
) -> list[CanonicalEntity]:
    """Resolve duplicate entities while preserving independent scientific observations.

    Documents default to metadata deduplication. Material/chemical records default to
    observation preservation so equal semantic fields from independent providers remain
    available for agreement/conflict analysis.
    """

    field_modes = field_modes or {}
    groups: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        groups[canonical_identity(record)].append(record)

    entities: list[CanonicalEntity] = []
    for key, group in groups.items():
        entity_kind = group[0].entity_kind
        identifiers: dict[str, str] = {}
        providers: list[str] = []
        field_observations: dict[str, list[FieldObservation]] = defaultdict(list)

        for record in group:
            if record.provider not in providers:
                providers.append(record.provider)
            for identifier_type, value in record.identifiers.items():
                identifiers.setdefault(identifier_type.casefold(), value)
            for field, value in record.fields.items():
                field_observations[field].append(
                    FieldObservation(
                        field=field,
                        value=value,
                        provider=record.provider,
                        unit=record.field_units.get(field),
                        qualifiers=dict(record.qualifiers),
                        provenance=dict(record.provenance),
                    )
                )

        fields: dict[str, AggregatedField] = {}
        for field, observations in field_observations.items():
            mode = field_modes.get(field, _default_merge_mode(entity_kind, field))
            if mode == "preserve_observations":
                comparable = [
                    (obs.value, obs.unit, tuple(sorted(obs.qualifiers.items())))
                    for obs in observations
                ]
                fields[field] = AggregatedField(
                    name=field,
                    mode=mode,
                    observations=observations,
                    agreement=len(set(map(repr, comparable))) <= 1,
                )
                continue

            # Metadata deduplication keeps one canonical value but does not erase provenance:
            # every source observation remains inspectable.
            canonical = next((obs.value for obs in observations if obs.value is not None), None)
            fields[field] = AggregatedField(
                name=field,
                mode=mode,
                value=canonical,
                observations=observations,
                agreement=len({repr(obs.value) for obs in observations}) <= 1,
            )

        entities.append(
            CanonicalEntity(
                entity_kind=entity_kind,
                canonical_key=key,
                identifiers=identifiers,
                providers=providers,
                fields=fields,
            )
        )

    return entities
