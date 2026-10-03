import json

import pytest

from schemarouter.capability_artifact import (
    CapabilityArtifactSource,
    build_capability_artifact,
    load_capability_artifact,
    serialize_capability_artifact,
)
from schemarouter.capability_contracts import CapabilityContract


@pytest.mark.parametrize(
    ("kind", "provider", "access_method"),
    [
        ("openapi", "provider-a", "rest"),
        ("mcp", "provider-b", "mcp"),
        ("optimade", "materials", "optimade"),
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


def test_artifact_serialization_is_deterministic() -> None:
    a = CapabilityContract(capability_id="a")
    b = CapabilityContract(capability_id="b")

    first = build_capability_artifact(graph_digest="g", capabilities=[a, b])
    second = build_capability_artifact(graph_digest="g", capabilities=[b, a])

    assert first.artifact_digest == second.artifact_digest
    assert serialize_capability_artifact(first) == serialize_capability_artifact(second)


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
    raw["format_version"] = "2.0"

    with pytest.raises(ValueError, match="unsupported"):
        load_capability_artifact(json.dumps(raw))


def test_artifact_model_has_no_runtime_or_secret_transport_fields() -> None:
    fields = set(build_capability_artifact(graph_digest="g", capabilities=[]).model_fields)
    assert "health" not in fields
    assert "credentials" not in fields
    assert "headers" not in fields
