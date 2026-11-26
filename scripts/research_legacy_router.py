"""Source-only construction seam for historical lexical comparison fixtures."""

from __future__ import annotations

from typing import Any

from schemarouter import SchemaRouter


def legacy_router(**kwargs: Any) -> SchemaRouter:
    """Construct the historical engine, never the product default."""
    return SchemaRouter(_legacy_routing=True, **kwargs)
