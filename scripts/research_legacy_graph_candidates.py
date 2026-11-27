"""Historical G5 candidate contracts, checkout only; preserve ranked evidence shape.

These nonexecuting records are distinct from installed unranked source proofs.
The product must not import them or treat them as execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass

# Frozen historical callback/fork/depth exposure and expansion budget.
# This is not an installed-product setting or a change to the historical K5.
MAX_RESEARCH_RANKABLE_PATHS = 32


@dataclass(frozen=True, slots=True)
class NativeIndexedGraphCandidate:
    """Nonexecuting, native original-source-pinned typed one-hop evidence."""

    producer_route_id: str
    consumer_route_id: str
    producer_tool_fingerprint: str
    producer_endpoint_fingerprint: str
    consumer_tool_fingerprint: str
    consumer_endpoint_fingerprint: str
    # Single-binding legacy fields are intentionally absent for multi-input
    # routes, so hosts cannot mistake a partial mapping for a complete one.
    producer_identifier_field: str | None
    consumer_required_parameter: str | None
    consumer_output_fields: tuple[str, ...]
    parameter_bindings: tuple[tuple[str, str], ...] = ()
    source_root_parameters: tuple[str, ...] = ()
    # Counts reflect current principal-scoped source views; never raw
    # provider schemas, denied output fields or unscoped graph metadata.
    producer_visible_field_count: int | None = None
    consumer_visible_field_count: int | None = None


@dataclass(frozen=True, slots=True)
class NativeIndexedTwoHopCandidate:
    """Three current source-native routes, two verified typed joins, no execution."""

    route_ids: tuple[str, str, str]
    route_fingerprints: tuple[tuple[str, str], tuple[str, str], tuple[str, str]]
    root_to_intermediate: tuple[tuple[str, str], ...]
    intermediate_to_target: tuple[tuple[str, str], ...]
    target_output_fields: tuple[str, ...]
    source_root_parameters: tuple[str, ...]
    visible_field_counts: tuple[int, int, int] | None = None
