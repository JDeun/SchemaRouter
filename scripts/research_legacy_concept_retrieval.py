"""Checkout-only raw-query concept resolution and native index adapters.

Preserves the original bounded exact-alias algorithm and typed source lookup
wrappers, not a competing installed Understand implementation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from schemarouter.concept_retrieval import (
    NativeConceptCatalog,
    _alias_mentions,
    _merged_concept_constraints,
    _merged_concept_fields,
    _normalized,
)
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.models import StrictModel
from schemarouter.native_graph_index import STRICT_K

if TYPE_CHECKING:
    from schemarouter.authorization import PrincipalContext
    from schemarouter.native_graph_index import NativeIndexedGraphResult, NativeSchemaGraphIndex
    from schemarouter.native_semantic_index import (
        IndexedNativeFieldResult,
        NativeSchemaPostingIndex,
    )
    from schemarouter.runtime import SchemaRouter

MAX_QUERY_BYTES = 512
MAX_QUERY_CHARS = 256


class ResolvedNativeConcepts(StrictModel):
    concept_ids: tuple[str, ...]
    field_group: NativeDeclaredFieldGroup


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
    constraints = _merged_concept_constraints(selected)
    if constraints is None:
        raise ValueError("incompatible source policy across concepts")

    fields = _merged_concept_fields(selected)
    if fields is None:
        raise ValueError("conflicting typed requirements for semantic field")
    if len(fields) > 8:
        raise ValueError("merged FieldGroup exceeds field budget")

    source_type, license_id = constraints
    group = NativeDeclaredFieldGroup(
        aliases=(query,),
        required_fields=fields,
        source_type=source_type,
        license=license_id,
    )
    return ResolvedNativeConcepts(
        concept_ids=tuple(sorted(matched)),
        field_group=group,
    )


def lookup_posting_concepts(
    self: NativeSchemaPostingIndex,
    router: SchemaRouter,
    query: str,
    *,
    catalog: NativeConceptCatalog,
    principal: PrincipalContext,
    k: int = STRICT_K,
    input_free_only: bool = False,
) -> IndexedNativeFieldResult:
    """Original query → declared concepts → typed field intersection."""
    resolved = resolve_native_concepts(query, catalog=catalog)
    return self.lookup(
        router, query, group=resolved.field_group, principal=principal,
        k=k, input_free_only=input_free_only,
    )


def lookup_graph_concepts(
    self: NativeSchemaGraphIndex,
    router: SchemaRouter,
    query: str,
    *,
    catalog: NativeConceptCatalog,
    principal: PrincipalContext,
    k: int = STRICT_K,
) -> NativeIndexedGraphResult:
    resolved = resolve_native_concepts(query, catalog=catalog)
    return self.lookup(
        router, query, group=resolved.field_group, principal=principal, k=k,
    )
