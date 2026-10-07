from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeDefaults:
    """Single source of truth for public runtime/adapter registration defaults."""

    vector_top_k: int = 10
    query_limit: int = 100
    graph_max_hops: int = 1
    timeout_seconds: float = 20.0
    http_response_max_bytes: int = 10 * 1024 * 1024


RUNTIME_DEFAULTS = RuntimeDefaults()
