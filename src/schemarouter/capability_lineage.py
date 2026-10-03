from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from .models import StrictModel

CapabilityLineageReason = Literal[
    "selected",
    "method_unhealthy",
    "contract_incompatible",
    "contract_drifted",
    "state_ineligible",
    "policy_denied",
    "provider_fallback",
    "method_fallback",
    "unknown",
]


class CapabilityLineageHop(StrictModel):
    provider: str | None = None
    access_method: str | None = None
    route_id: str
    capability_id: str | None = None
    schema_revision: str | None = None
    schema_fingerprint: str | None = None
    semantic_ids: tuple[str, ...] = ()
    reason: CapabilityLineageReason = "selected"


class CapabilityLineage(StrictModel):
    lineage_id: str
    selected: CapabilityLineageHop
    actual: CapabilityLineageHop
    fallbacks: list[CapabilityLineageHop] = Field(default_factory=list)


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_capability_lineage(
    *,
    selected: CapabilityLineageHop,
    actual: CapabilityLineageHop | None = None,
    fallbacks: list[CapabilityLineageHop] | None = None,
) -> CapabilityLineage:
    """Build privacy-safe deterministic routing lineage.

    Callers provide identifiers and reason codes only. Payload values, credentials,
    and hidden candidate inventories are deliberately absent from the model.
    """

    actual_hop = actual or selected
    fallback_hops = list(fallbacks or [])
    document = {
        "selected": selected.model_dump(mode="json"),
        "actual": actual_hop.model_dump(mode="json"),
        "fallbacks": [item.model_dump(mode="json") for item in fallback_hops],
    }
    return CapabilityLineage(
        lineage_id=_canonical_digest(document),
        selected=selected,
        actual=actual_hop,
        fallbacks=fallback_hops,
    )
