from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from .capability_contracts import (
    CapabilityContract,
    CompatibilityContext,
    _canonical_compatibility_context_payload,
    compare_capability_composition,
)
from ._document_loading import load_bounded_json
from .storage import PersistedDocumentLimits
from .capability_graph import (
    CapabilityDependencyGraph,
    build_capability_dependency_graph,
)
from .models import StrictModel

LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION = "1.0"
_PREVIOUS_CAPABILITY_ARTIFACT_FORMAT_VERSION = "1.1"
CAPABILITY_ARTIFACT_FORMAT_VERSION = "1.2"
SUPPORTED_CAPABILITY_ARTIFACT_FORMAT_VERSIONS = (
    LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION,
    _PREVIOUS_CAPABILITY_ARTIFACT_FORMAT_VERSION,
    CAPABILITY_ARTIFACT_FORMAT_VERSION,
)

ArtifactSourceKind = Literal["openapi", "mcp", "optimade", "python", "other"]
ArtifactEdgeOrigin = Literal["derived", "external"]


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
    origin: ArtifactEdgeOrigin = "external"


class CapabilityGraphArtifact(StrictModel):
    format_version: str = CAPABILITY_ARTIFACT_FORMAT_VERSION
    artifact_digest: str
    graph_digest: str
    capabilities: tuple[CapabilityContract, ...]
    sources: tuple[CapabilityArtifactSource, ...] = ()
    edges: tuple[CapabilityArtifactEdge, ...] = ()
    provenance: dict[str, str] = Field(default_factory=dict)
    compatibility_context: CompatibilityContext | None = None


class CapabilityArtifactMigrationRecord(StrictModel):
    from_format: str
    to_format: str
    source_digest: str
    result_digest: str
    migrated: bool


class CapabilityArtifactMigrationResult(StrictModel):
    artifact: CapabilityGraphArtifact
    migration: CapabilityArtifactMigrationRecord


def _edge_payload(
    edge: CapabilityArtifactEdge,
    *,
    format_version: str,
) -> dict[str, object]:
    payload = edge.model_dump(mode="json")
    if format_version == LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION:
        payload.pop("origin", None)
    return payload


def _canonical_payload(
    *,
    format_version: str,
    graph_digest: str,
    capabilities: list[CapabilityContract],
    sources: list[CapabilityArtifactSource],
    edges: list[CapabilityArtifactEdge],
    provenance: dict[str, str],
    compatibility_context: CompatibilityContext | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "format_version": format_version,
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
            _edge_payload(item, format_version=format_version)
            for item in sorted(
                edges,
                key=lambda item: (
                    item.producer_id,
                    item.consumer_id,
                    item.compatibility,
                    item.origin,
                ),
            )
        ],
        "provenance": dict(sorted(provenance.items())),
    }
    if format_version == CAPABILITY_ARTIFACT_FORMAT_VERSION:
        payload["compatibility_context"] = _canonical_compatibility_context_payload(
            compatibility_context
        )
    return payload


def _payload_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _artifact_digest(
    artifact: CapabilityGraphArtifact,
    *,
    format_version: str | None = None,
) -> str:
    version = format_version or artifact.format_version
    return _payload_digest(
        _canonical_payload(
            format_version=version,
            graph_digest=artifact.graph_digest,
            capabilities=list(artifact.capabilities),
            sources=list(artifact.sources),
            edges=list(artifact.edges),
            provenance=artifact.provenance,
            compatibility_context=artifact.compatibility_context,
        )
    )


def capability_dependency_graph_digest(
    graph: CapabilityDependencyGraph,
) -> str:
    payload = {
        "capability_ids": list(graph.capability_ids),
        "edges": [
            {
                "producer_id": edge.producer_id,
                "consumer_id": edge.consumer_id,
                "compatibility": edge.compatibility.model_dump(mode="json"),
            }
            for edge in sorted(
                graph.edges,
                key=lambda item: (item.producer_id, item.consumer_id),
            )
        ],
    }
    return _payload_digest(payload)


def artifact_edges_from_graph(
    graph: CapabilityDependencyGraph,
) -> list[CapabilityArtifactEdge]:
    return [
        CapabilityArtifactEdge(
            producer_id=edge.producer_id,
            consumer_id=edge.consumer_id,
            compatibility=edge.compatibility.status,
            reasons=tuple(
                reason.detail
                for compatibility in edge.compatibility.requirements.values()
                for reason in compatibility.reasons
            ),
            origin="derived",
        )
        for edge in sorted(
            graph.edges,
            key=lambda item: (item.producer_id, item.consumer_id),
        )
    ]


def build_capability_artifact(
    *,
    graph_digest: str,
    capabilities: list[CapabilityContract],
    sources: list[CapabilityArtifactSource] | None = None,
    edges: list[CapabilityArtifactEdge] | None = None,
    provenance: dict[str, str] | None = None,
    context: CompatibilityContext | None = None,
) -> CapabilityGraphArtifact:
    source_items = list(sources or [])
    edge_items = list(edges or [])
    provenance_items = dict(provenance or {})
    payload = _canonical_payload(
        format_version=CAPABILITY_ARTIFACT_FORMAT_VERSION,
        graph_digest=graph_digest,
        capabilities=capabilities,
        sources=source_items,
        edges=edge_items,
        provenance=provenance_items,
        compatibility_context=context,
    )
    return CapabilityGraphArtifact(
        format_version=CAPABILITY_ARTIFACT_FORMAT_VERSION,
        artifact_digest=_payload_digest(payload),
        graph_digest=graph_digest,
        capabilities=tuple(sorted(capabilities, key=lambda item: item.capability_id)),
        sources=tuple(sorted(
            source_items,
            key=lambda item: (item.kind, item.provider, item.access_method or ""),
        )),
        edges=tuple(sorted(
            edge_items,
            key=lambda item: (
                item.producer_id,
                item.consumer_id,
                item.compatibility,
                item.origin,
            ),
        )),
        provenance=dict(sorted(provenance_items.items())),
        compatibility_context=(
            context.model_copy(deep=True)
            if context is not None
            else None
        ),
    )


def build_capability_artifact_from_graph(
    *,
    graph: CapabilityDependencyGraph,
    capabilities: list[CapabilityContract],
    sources: list[CapabilityArtifactSource] | None = None,
    provenance: dict[str, str] | None = None,
    context: CompatibilityContext | None = None,
) -> CapabilityGraphArtifact:
    expected = build_capability_dependency_graph(
        capabilities,
        context=context,
    )
    if expected != graph:
        raise ValueError(
            "capability graph does not match the supplied capability contracts"
        )
    return build_capability_artifact(
        graph_digest=capability_dependency_graph_digest(graph),
        capabilities=capabilities,
        sources=sources,
        edges=artifact_edges_from_graph(graph),
        provenance=provenance,
        context=context,
    )


def serialize_capability_artifact(artifact: CapabilityGraphArtifact) -> str:
    return json.dumps(
        artifact.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def validate_capability_artifact(
    artifact: CapabilityGraphArtifact,
) -> CapabilityGraphArtifact:
    if artifact.format_version != CAPABILITY_ARTIFACT_FORMAT_VERSION:
        raise ValueError(
            "semantic integrity validation requires current capability artifact format"
        )

    capability_ids = [item.capability_id for item in artifact.capabilities]
    if len(capability_ids) != len(set(capability_ids)):
        raise ValueError("capability artifact contains duplicate capability IDs")

    source_ids = [
        (item.kind, item.provider, item.access_method or "")
        for item in artifact.sources
    ]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("capability artifact contains duplicate source identities")

    edge_ids = [
        (item.producer_id, item.consumer_id)
        for item in artifact.edges
    ]
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("capability artifact contains duplicate dependency edges")

    known = set(capability_ids)
    by_id = {item.capability_id: item for item in artifact.capabilities}
    derived_pairs: set[tuple[str, str]] = set()
    for edge in artifact.edges:
        if edge.producer_id not in known or edge.consumer_id not in known:
            raise ValueError(
                "capability artifact edge references an unknown capability"
            )
        if edge.producer_id == edge.consumer_id:
            raise ValueError("capability artifact contains a self dependency edge")
        if edge.origin != "derived":
            continue
        compatibility = compare_capability_composition(
            by_id[edge.producer_id],
            by_id[edge.consumer_id],
            context=artifact.compatibility_context,
        )
        if not compatibility.satisfies:
            raise ValueError(
                "derived capability artifact edge is not contract-compatible"
            )
        if edge.compatibility != compatibility.status:
            raise ValueError(
                "derived capability artifact edge compatibility is stale"
            )
        derived_pairs.add((edge.producer_id, edge.consumer_id))

    if artifact.edges and all(edge.origin == "derived" for edge in artifact.edges):
        graph = build_capability_dependency_graph(
            list(artifact.capabilities),
            context=artifact.compatibility_context,
        )
        expected_pairs = {
            (edge.producer_id, edge.consumer_id)
            for edge in graph.edges
        }
        if derived_pairs != expected_pairs:
            raise ValueError(
                "derived capability artifact edges do not match the canonical graph"
            )
        if artifact.graph_digest != capability_dependency_graph_digest(graph):
            raise ValueError(
                "capability artifact graph digest does not match the canonical graph"
            )

    return artifact


def _parse_and_validate_known_artifact(
    document: str,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> CapabilityGraphArtifact:
    raw = load_bounded_json(
        document,
        limits=document_limits,
        label="capability artifact document",
    )
    if not isinstance(raw, dict):
        raise ValueError("capability artifact document must be a JSON object")
    version = raw.get("format_version")
    if version not in SUPPORTED_CAPABILITY_ARTIFACT_FORMAT_VERSIONS:
        raise ValueError(f"unsupported capability artifact format: {version}")

    artifact = CapabilityGraphArtifact.model_validate(raw)
    expected_digest = _artifact_digest(
        artifact,
        format_version=str(version),
    )
    if expected_digest != artifact.artifact_digest:
        raise ValueError("capability artifact digest mismatch")
    return artifact


def migrate_capability_artifact(
    document: str,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> CapabilityArtifactMigrationResult:
    artifact = _parse_and_validate_known_artifact(
        document,
        document_limits=document_limits,
    )
    source_digest = artifact.artifact_digest

    if artifact.format_version == CAPABILITY_ARTIFACT_FORMAT_VERSION:
        validate_capability_artifact(artifact)
        return CapabilityArtifactMigrationResult(
            artifact=artifact,
            migration=CapabilityArtifactMigrationRecord(
                from_format=artifact.format_version,
                to_format=artifact.format_version,
                source_digest=source_digest,
                result_digest=artifact.artifact_digest,
                migrated=False,
            ),
        )

    provenance = dict(artifact.provenance)
    provenance.setdefault("migration.from_format", artifact.format_version)
    provenance.setdefault("migration.source_digest", source_digest)
    migrated_edges = (
        [
            edge.model_copy(update={"origin": "external"})
            for edge in artifact.edges
        ]
        if artifact.format_version == LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION
        else [edge.model_copy(deep=True) for edge in artifact.edges]
    )
    migrated = build_capability_artifact(
        graph_digest=artifact.graph_digest,
        capabilities=list(artifact.capabilities),
        sources=list(artifact.sources),
        edges=migrated_edges,
        provenance=provenance,
        context=None,
    )
    validate_capability_artifact(migrated)
    return CapabilityArtifactMigrationResult(
        artifact=migrated,
        migration=CapabilityArtifactMigrationRecord(
            from_format=artifact.format_version,
            to_format=CAPABILITY_ARTIFACT_FORMAT_VERSION,
            source_digest=source_digest,
            result_digest=migrated.artifact_digest,
            migrated=True,
        ),
    )


def load_capability_artifact(
    document: str,
    *,
    document_limits: PersistedDocumentLimits | None = None,
) -> CapabilityGraphArtifact:
    result = migrate_capability_artifact(
        document,
        document_limits=document_limits,
    )
    return result.artifact
