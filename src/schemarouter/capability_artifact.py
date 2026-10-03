from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from .capability_contracts import CapabilityContract
from .models import StrictModel

CAPABILITY_ARTIFACT_FORMAT_VERSION = "1.0"
ArtifactSourceKind = Literal["openapi", "mcp", "optimade", "python", "other"]


class CapabilityArtifactSource(StrictModel):
    kind: ArtifactSourceKind
    provider: str
    access_method: str | None = None
    schema_fingerprint: str


class CapabilityArtifactEdge(StrictModel):
    producer_id: str
    consumer_id: str
    compatibility: str
    reasons: tuple[str, ...] = ()


class CapabilityGraphArtifact(StrictModel):
    format_version: str = CAPABILITY_ARTIFACT_FORMAT_VERSION
    artifact_digest: str
    graph_digest: str
    capabilities: tuple[CapabilityContract, ...]
    sources: tuple[CapabilityArtifactSource, ...] = ()
    edges: tuple[CapabilityArtifactEdge, ...] = ()
    provenance: dict[str, str] = Field(default_factory=dict)


def _canonical_payload(
    *,
    graph_digest: str,
    capabilities: list[CapabilityContract],
    sources: list[CapabilityArtifactSource],
    edges: list[CapabilityArtifactEdge],
    provenance: dict[str, str],
) -> dict[str, object]:
    return {
        "format_version": CAPABILITY_ARTIFACT_FORMAT_VERSION,
        "graph_digest": graph_digest,
        "capabilities": [
            item.model_dump(mode="json")
            for item in sorted(capabilities, key=lambda item: item.capability_id)
        ],
        "sources": [
            item.model_dump(mode="json")
            for item in sorted(
                sources,
                key=lambda item: (item.kind, item.provider, item.access_method or ""),
            )
        ],
        "edges": [
            item.model_dump(mode="json")
            for item in sorted(
                edges,
                key=lambda item: (item.producer_id, item.consumer_id, item.compatibility),
            )
        ],
        "provenance": dict(sorted(provenance.items())),
    }


def build_capability_artifact(
    *,
    graph_digest: str,
    capabilities: list[CapabilityContract],
    sources: list[CapabilityArtifactSource] | None = None,
    edges: list[CapabilityArtifactEdge] | None = None,
    provenance: dict[str, str] | None = None,
) -> CapabilityGraphArtifact:
    payload = _canonical_payload(
        graph_digest=graph_digest,
        capabilities=capabilities,
        sources=list(sources or []),
        edges=list(edges or []),
        provenance=dict(provenance or {}),
    )
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return CapabilityGraphArtifact(
        artifact_digest=digest,
        graph_digest=graph_digest,
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability_id)),
        sources=tuple(sorted(
            sources or [],
            key=lambda item: (item.kind, item.provider, item.access_method or ""),
        )),
        edges=tuple(sorted(
            edges or [],
            key=lambda item: (item.producer_id, item.consumer_id, item.compatibility),
        )),
        provenance=dict(sorted((provenance or {}).items())),
    )


def serialize_capability_artifact(artifact: CapabilityGraphArtifact) -> str:
    return json.dumps(
        artifact.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def load_capability_artifact(document: str) -> CapabilityGraphArtifact:
    raw = json.loads(document)
    artifact = CapabilityGraphArtifact.model_validate(raw)
    if artifact.format_version != CAPABILITY_ARTIFACT_FORMAT_VERSION:
        raise ValueError(f"unsupported capability artifact format: {artifact.format_version}")
    expected = build_capability_artifact(
        graph_digest=artifact.graph_digest,
        capabilities=list(artifact.capabilities),
        sources=list(artifact.sources),
        edges=list(artifact.edges),
        provenance=artifact.provenance,
    )
    if expected.artifact_digest != artifact.artifact_digest:
        raise ValueError("capability artifact digest mismatch")
    return artifact
