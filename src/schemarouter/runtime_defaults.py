from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeDefaults:
    """Single source of truth for shared SchemaRouter runtime/adapter defaults."""

    vector_top_k: int = 10
    collection_limit: int = 100
    graph_max_hops: int = 1
    max_discovery_sources: int = 128
    max_fields_per_collection: int = 256
    max_generated_bytes: int = 8 * 1024 * 1024
    transport_timeout_seconds: float = 20.0
    max_response_bytes: int = 10 * 1024 * 1024
    openapi_ref_max_depth: int = 3
    openapi_ref_max_documents: int = 8
    openapi_ref_max_bytes: int = 10 * 1024 * 1024
    documentation_max_chars: int = 60_000

    def __post_init__(self) -> None:
        positive_integer_fields = (
            "vector_top_k",
            "collection_limit",
            "graph_max_hops",
            "max_discovery_sources",
            "max_fields_per_collection",
            "max_generated_bytes",
            "max_response_bytes",
            "openapi_ref_max_depth",
            "openapi_ref_max_documents",
            "openapi_ref_max_bytes",
            "documentation_max_chars",
        )
        for name in positive_integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(self.transport_timeout_seconds, bool)
            or not isinstance(self.transport_timeout_seconds, (int, float))
            or self.transport_timeout_seconds <= 0
        ):
            raise ValueError("transport_timeout_seconds must be > 0")


RUNTIME_DEFAULTS = RuntimeDefaults()
