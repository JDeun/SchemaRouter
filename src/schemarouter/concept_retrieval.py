"""Bounded host-declared concept mentions to typed FieldGroup retrieval (opt-in).

This is an interpretable lookup of *declared* aliases, not multilingual
translation, open-vocabulary intent extraction, or an execution capability.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import model_validator

from .authorization import PrincipalContext
from .capability_contracts import CapabilityFieldContract
from .field_group_retrieval import (
    NativeDeclaredFieldGroup,
    _scalar_contract,
    retrieve_authorized_field_group,
)
from .models import CapabilityRetrieval, StrictModel
from .planner import _locale_lexical_text

if TYPE_CHECKING:
    from .runtime import SchemaRouter

MAX_CONCEPTS = 32
MAX_ALIASES = 128
MAX_QUERY_BYTES = 512
MAX_QUERY_CHARS = 256
_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


def _normalized(value: str) -> str:
    # Reuse the narrow Korean NFC + Japanese width folding from the existing
    # lexical engine; NEVER apply global NFKC to scientific units.
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
    source_type: str
    license: str

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
            or any(not _scalar_contract(f.json_schema)
                   for f in self.required_fields)
            or any(
                type(source) is not str or source != source.strip()
                or not 1 <= len(source) <= 160
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
        aliases: dict[str, str] = {}
        for concept in self.concepts:
            for alias in concept.aliases:
                key = _normalized(alias)
                if key in aliases:
                    raise ValueError("ambiguous owner-declared concept alias")
                aliases[key] = concept.concept_id
        if len(aliases) > MAX_ALIASES:
            raise ValueError("too many declared concept aliases")
        # This is a bound on the full ontology contract, not just query text.
        if len(self.model_dump_json().encode("utf-8")) > 16384:
            raise ValueError("concept catalog exceeds byte budget")
        return self


class ResolvedNativeConcepts(StrictModel):
    concept_ids: tuple[str, ...]
    field_group: NativeDeclaredFieldGroup


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


def resolve_native_concepts(
    query: str, *, catalog: NativeConceptCatalog,
) -> ResolvedNativeConcepts:
    """Resolve exact declared mentions and merge all their required fields.

    Every visible matched concept participates; overlapping *different*
    concepts and conflicting typed contracts fail closed. No semantic names
    or provider fields are guessed from text.
    """
    if (
        type(query) is not str
        or not 2 <= len(query) <= MAX_QUERY_CHARS
        or len(query.encode("utf-8")) > MAX_QUERY_BYTES
        or query != query.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in query)
    ):
        raise ValueError("invalid bounded concept query")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("host-approved concept catalog required")
    try:
        approved = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("trusted concept catalog has changed") from exc

    query_text = _normalized(query)
    hits: list[tuple[int, int, str]] = []
    for concept in approved.concepts:
        for alias in concept.aliases:
            hits.extend((begin, end, concept.concept_id)
                        for begin, end in _alias_mentions(query_text, _normalized(alias)))
    if not hits:
        raise ValueError("no declared concept in query")

    # Never silently choose an overlapping, different semantic concept,
    # even if its alias happens to be shorter.
    for i, (start, end, cid) in enumerate(hits):
        for other_start, other_end, other_id in hits[i + 1:]:
            if cid != other_id and start < other_end and other_start < end:
                raise ValueError("ambiguous overlapping declared concepts")

    matched = {cid for _, _, cid in hits}
    selected = [c for c in approved.concepts if c.concept_id in matched]
    sources = {(c.source_type, c.license) for c in selected}
    if len(sources) != 1:
        raise ValueError("incompatible source policy across concepts")

    unique: dict[str, CapabilityFieldContract] = {}
    for concept in selected:
        for field in concept.required_fields:
            previous = unique.get(field.semantic_id)
            if previous is not None and previous != field:
                raise ValueError("conflicting typed requirements for semantic field")
            unique[field.semantic_id] = field
    if len(unique) > 8:
        raise ValueError("merged FieldGroup exceeds field budget")

    source_type, license_id = next(iter(sources))
    group = NativeDeclaredFieldGroup(
        aliases=(query,),
        required_fields=tuple(unique[key] for key in sorted(unique)),
        source_type=source_type,
        license=license_id,
    )
    return ResolvedNativeConcepts(
        concept_ids=tuple(sorted(matched)),
        field_group=group,
    )


def retrieve_authorized_concepts(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    k: int = 5,
) -> CapabilityRetrieval:
    """Compose existing opt-in principal-scoped pre-K FieldGroup retrieval."""
    resolved = resolve_native_concepts(query, catalog=catalog)
    return retrieve_authorized_field_group(
        router, query, principal=principal, group=resolved.field_group, k=k,
    )
