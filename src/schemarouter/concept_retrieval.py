"""Trusted owner concept catalog, typed contract composition and alias utilities.

These shared contracts support schema-independent Understand and source-proven
planning. Raw query-alias retrieval is preserved only in research checkouts.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import model_validator

from ._schema_identity import _locale_lexical_text
from .capability_contracts import CapabilityFieldContract
from .field_group_retrieval import _response_contract
from .models import StrictModel
from .validation import json_schemas_compatible

MAX_CONCEPTS = 32
MAX_ALIASES = 128
_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


def _normalized(value: str) -> str:
    # Use shared narrow Korean NFC + Japanese width folding;
    # NEVER apply global NFKC to scientific units.
    return _locale_lexical_text(value).casefold()


def _bounded_alias(value: str) -> bool:
    return (
        type(value) is str
        and 2 <= len(value) <= 160
        and value.strip() == value
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


class NativeDeclaredConcept(StrictModel):
    """A trusted owner-declared concept -> complete typed field requirement."""

    concept_id: str
    aliases: tuple[str, ...]
    required_fields: tuple[CapabilityFieldContract, ...]
    source_type: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def validate_concept(self) -> NativeDeclaredConcept:
        if (
            type(self.concept_id) is not str
            or not _ID_PATTERN.fullmatch(self.concept_id)
            or not 1 <= len(self.aliases) <= 16
            or any(not _bounded_alias(a) for a in self.aliases)
            or len({_normalized(a) for a in self.aliases}) != len(self.aliases)
            or not 1 <= len(self.required_fields) <= 8
            or len({f.semantic_id for f in self.required_fields})
            != len(self.required_fields)
            or any(not _response_contract(f.json_schema)
                   for f in self.required_fields)
            or any(
                source is not None and (
                    type(source) is not str or source != source.strip()
                    or not 1 <= len(source) <= 160
                )
                for source in (self.source_type, self.license)
            )
        ):
            raise ValueError("invalid bounded owner-declared concept")
        return self


class NativeConceptCatalog(StrictModel):
    concepts: tuple[NativeDeclaredConcept, ...]

    @model_validator(mode="after")
    def validate_catalog(self) -> NativeConceptCatalog:
        if not 1 <= len(self.concepts) <= MAX_CONCEPTS:
            raise ValueError("invalid bounded concept count")
        if len({c.concept_id for c in self.concepts}) != len(self.concepts):
            raise ValueError("duplicate trusted concept ID")
        aliases: dict[str, list[NativeDeclaredConcept]] = {}
        for concept in self.concepts:
            for alias in concept.aliases:
                key = _normalized(alias)
                if any(not _distinct_query_conditions(concept, previous)
                       for previous in aliases.get(key, ())):
                    raise ValueError("ambiguous owner-declared concept alias")
                aliases.setdefault(key, []).append(concept)
        if sum(len(concept.aliases) for concept in self.concepts) > MAX_ALIASES:
            raise ValueError("too many declared concept aliases")
        # This is a bound on the full ontology contract, not just query text.
        if len(self.model_dump_json().encode("utf-8")) > 16384:
            raise ValueError("concept catalog exceeds byte budget")
        return self


def _distinct_query_conditions(left: NativeDeclaredConcept, right: NativeDeclaredConcept) -> bool:
    """Shared aliases need explicit owner distinctions, never inferred namespaces."""
    if (left.source_type is not None and right.source_type is not None
            and left.source_type != right.source_type):
        return True
    return all(
        first.unit is not None and second.unit is not None and first.unit != second.unit
        or any(key in second.qualifiers and second.qualifiers[key] != value
               for key, value in first.qualifiers.items())
        for first in left.required_fields for second in right.required_fields
    )


def _merged_concept_constraints(
    concepts: Iterable[NativeDeclaredConcept],
) -> tuple[str | None, str | None] | None:
    """Intersect optional owner narrowing constraints; None means incompatible."""
    concepts = tuple(concepts)
    sources = {concept.source_type for concept in concepts if concept.source_type is not None}
    licenses = {concept.license for concept in concepts if concept.license is not None}
    if len(sources) > 1 or len(licenses) > 1:
        return None
    return next(iter(sources), None), next(iter(licenses), None)


def _merged_concept_fields(
    concepts: Iterable[NativeDeclaredConcept],
) -> tuple[CapabilityFieldContract, ...] | None:
    """Merge one SID-keyed group only when repeated typed contracts agree."""
    unique: dict[str, CapabilityFieldContract] = {}
    for concept in concepts:
        for field in concept.required_fields:
            previous = unique.get(field.semantic_id)
            if previous is not None and (
                previous != field
                or not json_schemas_compatible(previous.json_schema, field.json_schema)
            ):
                return None
            unique[field.semantic_id] = field
    return tuple(unique[key] for key in sorted(unique))


def _alias_mentions(query: str, alias: str) -> list[tuple[int, int]]:
    """Literal phrase mentions, bounded at ASCII identifiers, not substrings.

    Non-ASCII substrings are allowed only where the host explicitly declared
    them (e.g. Japanese sentence without spaces). This cannot understand
    scope or negation; unknown and ambiguous queries must not be promoted.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = query.find(alias, start)
        if index < 0:
            return spans
        end = index + len(alias)
        first, last = alias[0], alias[-1]
        valid_start = not (
            first.isascii() and (first.isalnum() or first == "_")
            and index > 0
            and query[index - 1].isascii()
            and (query[index - 1].isalnum() or query[index - 1] == "_")
        )
        valid_end = not (
            last.isascii() and (last.isalnum() or last == "_")
            and end < len(query)
            and query[end].isascii()
            and (query[end].isalnum() or query[end] == "_")
        )
        if valid_start and valid_end:
            spans.append((index, end))
        start = index + 1
