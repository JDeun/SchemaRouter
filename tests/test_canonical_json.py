from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import pytest

from schemarouter.adaptive_context import (
    SessionSchemaExposure,
    SuccessfulCapabilityHistory,
)
from schemarouter.canonical_json import (
    canonical_json_bytes,
    canonical_json_sha256,
    canonical_json_text,
)
from schemarouter.capability_artifact import _payload_digest
from schemarouter.capability_contracts import (
    CapabilityFieldContract,
    _capability_requirement_identity,
)
from schemarouter.capability_decision_trace import _trace_digest
from schemarouter.capability_snapshot import _digest_payload
from schemarouter.models import EndpointSpec, ToolSpec
from schemarouter.provider_profiles import (
    ProviderDiscoveryCandidate,
    ProviderProfile,
)
from schemarouter.source_identity import (
    StructuredSourceIdentity,
    structured_source_identity_digest,
)

_GOLDEN_PAYLOAD = {
    "z": "한글",
    "a": [1, True, None, 1.5],
    "nested": {"b": "é", "a": "e\u0301"},
}
_GOLDEN_TEXT = (
    '{"a":[1,true,null,1.5],"nested":{"a":"e\\u0301","b":"\\u00e9"},'
    '"z":"\\ud55c\\uae00"}'
)
_GOLDEN_SHA256 = "e1fd6dcf59b2d76fbe6128e58851bf855ef12781737125cf948a86fa01061422"


def test_canonical_json_golden_vector_preserves_historical_digest_contract() -> None:
    assert canonical_json_text(_GOLDEN_PAYLOAD) == _GOLDEN_TEXT
    assert canonical_json_bytes(_GOLDEN_PAYLOAD) == _GOLDEN_TEXT.encode("utf-8")
    assert canonical_json_sha256(_GOLDEN_PAYLOAD) == _GOLDEN_SHA256


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_non_finite_floats(value: float) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json_bytes({"value": value})


def test_canonical_json_rejects_non_string_object_keys() -> None:
    with pytest.raises(TypeError, match="keys must be strings"):
        canonical_json_bytes({1: "coerced-by-json-dumps"})


def test_digest_surfaces_share_the_canonical_encoder_contract() -> None:
    assert _payload_digest(_GOLDEN_PAYLOAD) == _GOLDEN_SHA256
    assert _digest_payload(_GOLDEN_PAYLOAD) == _GOLDEN_SHA256

    profile = ProviderProfile(
        provider_id="golden-provider",
        display_name="Golden Provider",
        aliases=("golden",),
    )
    candidate = ProviderDiscoveryCandidate(
        candidate_id=profile.provider_id,
        display_name=profile.display_name,
        source="test",
        profile=profile,
    )
    assert candidate.approval_digest == canonical_json_sha256(
        profile.model_dump(mode="json")
    )

    history = SuccessfulCapabilityHistory()
    history.record_success("materials", "search")
    assert history.dumps() == canonical_json_text(
        {"schema_version": 1, "counts": history.snapshot()}
    )
    assert history.digest() == canonical_json_sha256(history.snapshot())

    exposure = SessionSchemaExposure()
    exposure.mark_exposed("materials", "search")
    assert exposure.dumps() == canonical_json_text(
        {"schema_version": 1, **exposure.snapshot()}
    )
    assert exposure.digest() == canonical_json_sha256(exposure.snapshot())


def _legacy_digest(value: object, *, ensure_ascii: bool = True) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_canonical_json_legacy_utf8_mode_is_explicit_and_stable() -> None:
    payload = {"z": "한글", "a": "é"}
    assert canonical_json_text(payload, ensure_ascii=False) == '{"a":"é","z":"한글"}'
    assert canonical_json_sha256(
        payload,
        ensure_ascii=False,
    ) == _legacy_digest(payload, ensure_ascii=False)


def test_model_fingerprints_preserve_legacy_digest_values() -> None:
    endpoint = EndpointSpec(
        name="search",
        description="검색",
        method="GET",
        path="/search",
        read_only=True,
        destructive=False,
    )
    endpoint_payload = endpoint.model_dump(mode="json", exclude={"metadata"})
    endpoint_payload.pop("auth_requirements", None)
    assert endpoint.fingerprint == _legacy_digest(endpoint_payload)

    tool = ToolSpec(
        name="materials",
        provider="example",
        access_mode="openapi",
        endpoints=[endpoint],
    )
    tool_payload = tool.model_dump(
        mode="json",
        exclude={"metadata", "endpoints"},
    )
    tool_payload["endpoints"] = [endpoint_payload]
    assert tool.fingerprint == _legacy_digest(tool_payload)


def test_decision_trace_digest_uses_canonical_json_contract() -> None:
    payload = {
        "snapshot_id": "snapshot-1",
        "registry_version": 7,
        "candidates": [],
        "lineage": None,
    }
    assert _trace_digest(
        snapshot_id="snapshot-1",
        registry_version=7,
        candidates=(),
        lineage=None,
    ) == canonical_json_sha256(payload)


def test_structured_source_identity_digest_preserves_legacy_value() -> None:
    identity = StructuredSourceIdentity(
        adapter="openapi",
        source_url="https://example.test/openapi.json",
        transport="https",
        qualifiers=(("tenant", "alpha"),),
    )
    payload = asdict(identity)
    assert structured_source_identity_digest(identity) == canonical_json_sha256(payload)
    assert structured_source_identity_digest(identity) == _legacy_digest(payload)


def test_capability_requirement_identity_keeps_legacy_unescaped_unicode() -> None:
    requirement = CapabilityFieldContract(
        semantic_id="재료.밴드갭",
        json_schema={"type": "number"},
        unit="eV",
    )
    payload = requirement.model_dump(mode="json")
    assert _capability_requirement_identity(requirement) == canonical_json_text(
        payload,
        ensure_ascii=False,
    )
