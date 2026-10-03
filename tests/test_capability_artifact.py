import hashlib
import json

import pytest

from schemarouter.capability_artifact import (
    CAPABILITY_ARTIFACT_FORMAT_VERSION,
    LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION,
    CapabilityArtifactEdge,
    CapabilityArtifactSource,
    build_capability_artifact,
    build_capability_artifact_from_graph,
    capability_dependency_graph_digest,
    load_capability_artifact,
    migrate_capability_artifact,
    serialize_capability_artifact,
    validate_capability_artifact,
)
from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
)
from schemarouter.capability_graph import build_capability_dependency_graph


def _legacy_document(
    *,
    graph_digest: str,
    capabilities: list[CapabilityContract],
    sources: list[CapabilityArtifactSource] | None = None,
    edges: list[dict[str, object]] | None = None,
    provenance: dict[str, str] | None = None,
) -> str:
    payload = {
        "format_version": LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION,
        "graph_digest": graph_digest,
        "capabilities": [
            item.model_dump(mode="json")
            for item in sorted(capabilities, key=lambda item: item.capability_id)
        ],
        "sources": [
            item.model_dump(mode="json")
            for item in sorted(
                sources or [],
                key=lambda item: (item.kind, item.provider, item.access_method or ""),
            )
        ],
        "edges": sorted(
            edges or [],
            key=lambda item: (
                str(item["producer_id"]),
                str(item["consumer_id"]),
                str(item["compatibility"]),
            ),
        ),
        "provenance": dict(sorted((provenance or {}).items())),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    return json.dumps(
        {
            "artifact_digest": digest,
            **payload,
        },
        sort_keys=True,
    )


@pytest.mark.parametrize(
    ("kind", "provider", "access_method"),
    [
        ("openapi", "provider-a", "rest"),
        ("mcp", "provider-b", "mcp"),
        ("optimade", "materials", "optimade"),
        ("python", "materials", "mp-api"),
    ],
)
def test_provider_fixture_artifact_round_trip(kind: str, provider: str, access_method: str) -> None:
    artifact = build_capability_artifact(
        graph_digest="graph-1",
        capabilities=[CapabilityContract(capability_id=f"{provider}.query")],
        sources=[
            CapabilityArtifactSource(
                kind=kind,
                provider=provider,
                access_method=access_method,
                schema_fingerprint="schema-1",
            )
        ],
    )

    loaded = load_capability_artifact(serialize_capability_artifact(artifact))

    assert loaded == artifact
    assert loaded.format_version == CAPABILITY_ARTIFACT_FORMAT_VERSION


def test_artifact_serialization_is_deterministic() -> None:
    a = CapabilityContract(capability_id="a")
    b = CapabilityContract(capability_id="b")

    first = build_capability_artifact(graph_digest="g", capabilities=[a, b])
    second = build_capability_artifact(graph_digest="g", capabilities=[b, a])

    assert first.artifact_digest == second.artifact_digest
    assert serialize_capability_artifact(first) == serialize_capability_artifact(second)


def test_legacy_v1_artifact_migrates_deterministically_without_inventing_edge_authority() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[CapabilityFieldContract(semantic_id="resource.id")],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[CapabilityFieldContract(semantic_id="resource.id")],
    )
    legacy = _legacy_document(
        graph_digest="legacy-graph",
        capabilities=[producer, consumer],
        edges=[
            {
                "producer_id": "producer",
                "consumer_id": "consumer",
                "compatibility": "compatible",
                "reasons": [],
            }
        ],
    )

    first = migrate_capability_artifact(legacy)
    second = migrate_capability_artifact(legacy)

    assert first == second
    assert first.migration.from_format == "1.0"
    assert first.migration.to_format == CAPABILITY_ARTIFACT_FORMAT_VERSION
    assert first.migration.migrated is True
    assert first.artifact.edges[0].origin == "external"
    assert first.artifact.provenance["migration.from_format"] == "1.0"
    assert first.artifact.provenance["migration.source_digest"] == first.migration.source_digest

    idempotent = migrate_capability_artifact(
        serialize_capability_artifact(first.artifact)
    )
    assert idempotent.artifact == first.artifact
    assert idempotent.migration.migrated is False


def test_tampered_legacy_artifact_is_rejected_before_migration() -> None:
    legacy = json.loads(
        _legacy_document(
            graph_digest="g",
            capabilities=[CapabilityContract(capability_id="a")],
        )
    )
    legacy["graph_digest"] = "tampered"

    with pytest.raises(ValueError, match="digest mismatch"):
        migrate_capability_artifact(json.dumps(legacy))


def test_tampered_artifact_fails_strict_digest_validation() -> None:
    artifact = build_capability_artifact(
        graph_digest="g",
        capabilities=[CapabilityContract(capability_id="a")],
    )
    raw = json.loads(serialize_capability_artifact(artifact))
    raw["graph_digest"] = "tampered"

    with pytest.raises(ValueError, match="digest mismatch"):
        load_capability_artifact(json.dumps(raw))


def test_unknown_format_version_fails_closed() -> None:
    artifact = build_capability_artifact(graph_digest="g", capabilities=[])
    raw = json.loads(serialize_capability_artifact(artifact))
    raw["format_version"] = "9.0"

    with pytest.raises(ValueError, match="unsupported"):
        load_capability_artifact(json.dumps(raw))


def test_dangling_edge_fails_semantic_integrity_validation() -> None:
    artifact = build_capability_artifact(
        graph_digest="g",
        capabilities=[CapabilityContract(capability_id="a")],
        edges=[
            CapabilityArtifactEdge(
                producer_id="a",
                consumer_id="missing",
                compatibility="external",
                origin="external",
            )
        ],
    )

    with pytest.raises(ValueError, match="unknown capability"):
        validate_capability_artifact(artifact)


def test_duplicate_source_identity_fails_semantic_integrity_validation() -> None:
    source = CapabilityArtifactSource(
        kind="openapi",
        provider="provider-a",
        access_method="rest",
        schema_fingerprint="one",
    )
    artifact = build_capability_artifact(
        graph_digest="g",
        capabilities=[],
        sources=[
            source,
            source.model_copy(update={"schema_fingerprint": "two"}),
        ],
    )

    with pytest.raises(ValueError, match="duplicate source"):
        validate_capability_artifact(artifact)


def test_derived_artifact_validates_edge_semantics_and_graph_digest() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[
            CapabilityFieldContract(
                semantic_id="resource.id",
                json_schema={"type": "string"},
            )
        ],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[
            CapabilityFieldContract(
                semantic_id="resource.id",
                json_schema={"type": "string"},
            )
        ],
    )
    graph = build_capability_dependency_graph([producer, consumer])

    artifact = build_capability_artifact_from_graph(
        graph=graph,
        capabilities=[producer, consumer],
    )

    assert artifact.graph_digest == capability_dependency_graph_digest(graph)
    assert artifact.edges[0].origin == "derived"
    assert validate_capability_artifact(artifact) is artifact

    stale = artifact.model_copy(
        update={"graph_digest": "stale-graph-digest"}
    )
    with pytest.raises(ValueError, match="graph digest"):
        validate_capability_artifact(stale)


def test_build_from_graph_rejects_graph_contract_mismatch() -> None:
    capability = CapabilityContract(capability_id="a")
    graph = build_capability_dependency_graph([capability])

    with pytest.raises(ValueError, match="does not match"):
        build_capability_artifact_from_graph(
            graph=graph,
            capabilities=[CapabilityContract(capability_id="b")],
        )


def test_artifact_model_has_no_runtime_or_secret_transport_fields() -> None:
    fields = set(type(build_capability_artifact(graph_digest="g", capabilities=[])).model_fields)
    assert "health" not in fields
    assert "credentials" not in fields
    assert "headers" not in fields
