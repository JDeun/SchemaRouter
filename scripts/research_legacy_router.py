"""Source-only construction seam for historical lexical comparison fixtures."""

from __future__ import annotations

from typing import Any

from scripts.research_legacy_runtime import LegacySchemaRouter


def legacy_router(**kwargs: Any) -> LegacySchemaRouter:
    """Construct the historical engine, never the product default."""
    return LegacySchemaRouter(**kwargs)
