"""Editable AutoResearch prototype: re-rank *existing* typed candidates only.

This file is the only source file the research agent may edit in stage C.
Input contains trusted registry-derived public descriptions, NEVER gold labels.
Returning reordered route IDs cannot create new endpoints or grant authority.
The fixed evaluator checks the candidate output and all metric provenance.
"""
from __future__ import annotations

from typing import Any


def rerank(query: str, candidates: list[dict[str, Any]]) -> list[str]:
    """Return every registered input route ID once, ordered best-to-worst.

    Initial control: preserve current SchemaRouter ranking exactly. Future
    research agents can change lexical/field/hybrid ranking *here* without
    modifying actual product code, schemas, gold, authorizations or scorer.
    """
    del query
    return [item["route_id"] for item in candidates]
