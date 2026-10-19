"""E0 declared intent→semantic-field bridge for paper-to-runtime graph parity.

The host declares exact query-alias → canonical semantic-ID edges. The
currently principal-scoped registry must contain that semantic field before
the edge is allowed to enrich QueryIntent. The existing SchemaPlanner
performs native typed field/route ranking and host authorization.

This is NOT natural-language understanding, automatic translation, a
general graph query engine, model inference or an autonomous agent.
Never enable it as a product default from synthetic E0 evidence.
"""
from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from schemarouter import PlanRequest, QueryIntent
from schemarouter.capability_contracts import SemanticEquivalence
from schemarouter.errors import PlanningError
from schemarouter.planner import KeywordAnalyzer
from schemarouter.registry import ToolRegistry

MAX_DECLARED_EQUIVALENCES = 32
MAX_DECLARED_ALIASES = 128
MAX_DECLARATION_BYTES = 16384

# E0 research-only phrase matcher: provider/host-declared concepts ONLY.
_NEGATION_CUES = (
    "제외", "말고", "아닌", "하지 마", "사용하지", "빼고",
    "除外", "以外", "使わない", "ではなく", "しない",
    " not ", "don't", "do not", "except", "without ",
)
# Include coordination particles: a query requesting BOTH approved concepts must
# be treated as ambiguous, never promote only the one after a space.
_CJK_PARTICLES = frozenset("의을를은는이가에도만와과はがをのにでとへ")


def _is_cjk(value: str) -> bool:
    return any(
        "\u3040" <= char <= "\u30ff"
        or "\u3400" <= char <= "\u9fff"
        or "\uac00" <= char <= "\ud7a3"
        for char in value
    )


def _matches_declared_phrase(query: str, alias: str) -> bool:
    """Conservative declared whole-phrase match, with bounded CJK particles."""
    if len(alias) < 3:
        return False
    start = 0
    cjk = _is_cjk(alias)
    while (found := query.find(alias, start)) >= 0:
        end = found + len(alias)
        before = query[found - 1] if found else ""
        after = query[end] if end < len(query) else ""
        start = found + 1
        left_ok = not before or not before.isalnum() or (
            cjk and before in _CJK_PARTICLES
        )
        right_ok = not after or not after.isalnum() or (
            cjk and after in _CJK_PARTICLES
        )
        if left_ok and right_ok:
            return True
    return False




def _literal(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


@dataclass(frozen=True)
class DeclaredConceptGraphAnalyzer:
    """Narrow, host-declared exact alias edge to current visible field IDs."""

    equivalences: tuple[SemanticEquivalence, ...]
    match_mode: Literal["exact", "bounded_phrase"] = "exact"
    _alias_to_semantic: Mapping[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.match_mode not in ("exact", "bounded_phrase"):
            raise ValueError("unsupported declared concept match mode")
        items = self.equivalences
        if (
            type(items) is not tuple
            or not items
            or len(items) > MAX_DECLARED_EQUIVALENCES
            or any(type(item) is not SemanticEquivalence for item in items)
        ):
            raise ValueError("invalid bounded declared concept graph")
        try:
            size = len(json.dumps(
                [item.model_dump(mode="json") for item in items],
                ensure_ascii=False, sort_keys=True, allow_nan=False,
            ).encode("utf-8"))
        except (ValueError, TypeError):
            raise ValueError("invalid declared graph serialization") from None
        if size > MAX_DECLARATION_BYTES:
            raise ValueError("declared graph exceeds input byte budget")

        edges: dict[str, str] = {}
        count = 0
        for item in items:
            semantic_id = item.canonical_id
            if (
                type(semantic_id) is not str
                or not semantic_id
                or semantic_id != semantic_id.strip()
                or type(item.aliases) is not set
            ):
                raise ValueError("invalid canonical field semantic identity")
            for alias in item.aliases:
                if type(alias) is not str or not _literal(alias):
                    raise ValueError("invalid declared concept alias")
                key = _literal(alias)
                if key in edges:
                    # An ambiguous alias cannot grant a different field.
                    raise ValueError("ambiguous or duplicate declared concept alias")
                edges[key] = semantic_id
                count += 1
                if count > MAX_DECLARED_ALIASES:
                    raise ValueError("too many declared concept graph edges")
        if not edges:
            raise ValueError("declared concept graph has no aliases")
        object.__setattr__(self, "_alias_to_semantic", MappingProxyType(edges))

    def analyze(self, request: PlanRequest, registry: ToolRegistry) -> QueryIntent:
        # Preserve the production keyword analyzer as the strict baseline.
        intent = KeywordAnalyzer().analyze(request, registry)
        literal_query = _literal(request.query)
        if self.match_mode == "exact":
            requested_semantic = self._alias_to_semantic.get(literal_query)
        elif any(cue in f" {literal_query} " for cue in _NEGATION_CUES):
            requested_semantic = None
        else:
            possible = {
                semantic
                for alias, semantic in self._alias_to_semantic.items()
                if _matches_declared_phrase(literal_query, alias)
            }
            # No arbitrary winner for a multi-concept request.
            requested_semantic = next(iter(possible)) if len(possible) == 1 else None
        if requested_semantic is None:
            return intent

        # IMPORTANT: SchemaRouter's scoped retrieval supplies an analysis
        # registry already projected for this principal. NEVER inspect a
        # separate unscoped raw registry or infer hidden field existence.
        before = registry.version
        tools = registry.tools()
        after = registry.version
        if before != after:
            raise PlanningError("declared concept source changed during read")
        visible = {
            field.semantic_id
            for tool in tools
            for endpoint in tool.endpoints
            for field in endpoint.output_fields
            if field.semantic_id is not None
        }
        if requested_semantic not in visible:
            return intent

        return QueryIntent(
            concepts=list(dict.fromkeys([*intent.concepts, requested_semantic])),
            preferred_tools=intent.preferred_tools,
            preferred_endpoints=intent.preferred_endpoints,
            arguments=intent.arguments,
            evidence=intent.evidence,
            field_evidence=intent.field_evidence,
        )
