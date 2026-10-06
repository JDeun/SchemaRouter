from __future__ import annotations

import hashlib
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
    def validate_record(self) -> SourceRecord:
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
_MATERIAL_IDENTITY_TYPES = {
    "material_id",
    "structure_id",
    "structure_hash",
    "crystal_id",
}
_CHEMICAL_IDENTITY_TYPES = {
    "inchikey",
    "inchi",
    "canonical_smiles",
    "isomeric_smiles",
    "cid",
}
_SCIENTIFIC_KINDS = {"material", "chemical"}


def _trusted_identity_types(entity_kind: EntityKind) -> set[str] | None:
    if entity_kind == "document":
        return set(_DOCUMENT_IDENTIFIER_PRIORITY)
    if entity_kind == "material":
        return _MATERIAL_IDENTITY_TYPES
    if entity_kind == "chemical":
        return _CHEMICAL_IDENTITY_TYPES
    return None


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
    trusted = _trusted_identity_types(record.entity_kind)
    eligible = {
        key: value
        for key, value in normalized.items()
        if trusted is None or key in trusted
    }
    priority = (
        _DOCUMENT_IDENTIFIER_PRIORITY
        if record.entity_kind == "document"
        else tuple(sorted(eligible))
    )
    for identifier_type in priority:
        value = eligible.get(identifier_type)
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
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"{record.entity_kind}:unresolved:{digest}"


def _default_merge_mode(entity_kind: EntityKind, field: str) -> MergeMode:
    if entity_kind in _SCIENTIFIC_KINDS:
        return "preserve_observations"
    return "deduplicate"


def _trusted_identifier_claims(record: SourceRecord) -> dict[str, str]:
    trusted = _trusted_identity_types(record.entity_kind)
    claims: dict[str, str] = {}
    for kind, value in record.identifiers.items():
        normalized_kind = kind.casefold()
        if trusted is not None and normalized_kind not in trusted:
            continue
        normalized_value = _normalise_identifier(kind, value)
        previous = claims.get(normalized_kind)
        if previous is not None and previous != normalized_value:
            raise ValueError(
                "record contains conflicting values for one trusted identifier type"
            )
        claims[normalized_kind] = normalized_value
    return claims


def _identifier_tokens(record: SourceRecord) -> set[tuple[str, str]]:
    return set(_trusted_identifier_claims(record).items())


def _claims_compatible(left: dict[str, str], right: dict[str, str]) -> bool:
    shared_types = left.keys() & right.keys()
    return all(left[kind] == right[kind] for kind in shared_types)


def aggregate_records(
    records: list[SourceRecord],
    *,
    field_modes: dict[str, MergeMode] | None = None,
) -> list[CanonicalEntity]:
    """Resolve duplicate entities while preserving independent scientific observations.

    Identity resolution is transitive across trusted identifiers only while the evidence
    remains internally consistent. A shared identifier is treated as ambiguous when its
    owners disagree on another trusted identifier, and any residual transitive component
    containing contradictory trusted claims is conservatively left unresolved. Records
    without identifiers are never fuzzy-merged.

    Documents default to metadata deduplication. Material/chemical records default to
    observation preservation so equal semantic fields from independent providers remain
    available for agreement/conflict analysis.
    """

    field_modes = field_modes or {}
    if not records:
        return []

    parent = list(range(len(records)))
    record_claims = [_trusted_identifier_claims(record) for record in records]

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    def combined_claims(indices: list[int]) -> dict[str, str] | None:
        combined: dict[str, str] = {}
        for index in indices:
            claims = record_claims[index]
            if not _claims_compatible(combined, claims):
                return None
            combined.update(claims)
        return combined

    token_members: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, (record, claims) in enumerate(
        zip(records, record_claims, strict=True)
    ):
        for kind, value in claims.items():
            token_members[(record.entity_kind, kind, value)].append(index)

    # A shared token is safe merge evidence only when all of its owners agree on
    # every other trusted identifier they actually assert. This prevents a sparse
    # bridge record from attaching to whichever conflicting owner happens to be
    # processed first.
    for members in token_members.values():
        if len(members) < 2 or combined_claims(members) is None:
            continue
        anchor = members[0]
        for index in members[1:]:
            union(anchor, index)

    candidate_groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        candidate_groups[find(index)].append(index)

    resolved_groups: list[list[SourceRecord]] = []
    for indices in candidate_groups.values():
        if combined_claims(indices) is None:
            # Individually safe token edges can still form a contradictory
            # transitive component through records with missing claims. Prefer
            # duplicates over a false merge and keep provenance units separate.
            resolved_groups.extend([[records[index]] for index in indices])
            continue
        resolved_groups.append([records[index] for index in indices])

    entities: list[CanonicalEntity] = []
    for group in resolved_groups:
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

        representative = SourceRecord(
            provider=group[0].provider,
            entity_kind=entity_kind,
            identifiers=identifiers,
        )
        key = canonical_identity(representative)

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
