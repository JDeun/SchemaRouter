"""In-process signed identity fixture tests: no IAM issuer or provider network."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pytest
from starlette.types import Receive, Scope, Send

from scripts.research_central_asgi_boundary_e0 import (
    SyntheticScopeIdentityE0,
    make_synthetic_asgi_gateway_e0,
)
from scripts.research_central_durable_reservation_e0 import (
    DurableCentralReservationE0,
)
from scripts.research_live_health_model_menu_e1 import GEO
from scripts.research_signed_fixture_identity_e0 import (
    SignedFixtureIdentityVerifierE0,
    SignedFixtureScopeMiddlewareE0,
)

_KEY = b"ONLY_SYNTHETIC_TEST_DO_NOT_USE_IN_PRODUCTION_0123456789"
_CONTEXT = b"SchemaRouter E0 identity-boundary test only\x00"


def _base64(blob: bytes) -> str:
    return base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")


def _test_token(
    *, role: str = "workload", tenant: str = "church",
    workload: str = "agent-a", issued: int = 1000, expiry: int = 1040,
    audience: str = "schemarouter-closed-network-e0",
    key: bytes = _KEY,
) -> str:
    assertion = json.dumps({
        "aud": audience, "exp": expiry, "iat": issued,
        "role": role, "tenant": tenant, "workload": workload,
    }, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = _base64(assertion)
    mac = hmac.new(
        key, _CONTEXT + encoded.encode("ascii"), hashlib.sha256,
    ).digest()
    return encoded + "." + _base64(mac)


def _app(
    db: Path, seen: list[str], *,
    key: bytes = _KEY,
) -> SignedFixtureScopeMiddlewareE0:
    authority = DurableCentralReservationE0(db)
    authority.provision_once(
        allowed={
            ("church", "agent-a", GEO): "source-revision-1",
            ("school", "agent-a", GEO): "source-revision-1",
        },
        cap_per_tenant_route=2,
    )
    source = make_synthetic_asgi_gateway_e0(
        authority, synthetic_sink=lambda request: seen.append(request.tenant),
    )
    return SignedFixtureScopeMiddlewareE0(
        source, verifier=SignedFixtureIdentityVerifierE0(
            key, now=lambda: 1010.0,
        ),
    )


def _request(identifier: str) -> dict[str, str | int]:
    return {
        "request_id": identifier,
        "route_id": GEO,
        "source_fingerprint": "source-revision-1",
        "epoch": 1,
    }


def _attested(
    token: str | None, *, duplicates: bool = False,
) -> list[tuple[str, str]]:
    if token is None:
        return []
    value = [("authorization", f"Bearer {token}")]
    if duplicates:
        value.append(("authorization", f"Bearer {token}"))
    return value


@pytest.mark.asyncio
async def test_only_verified_offline_attestation_can_enter_gateway(tmp_path: Path):
    seen: list[str] = []
    app = _app(tmp_path / "verified.sqlite3", seen)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        without = await client.post("/e0/execute", json=_request("without"))
        assert without.status_code == 403
        with_auth = await client.post(
            "/e0/execute", json=_request("valid"),
            headers=_attested(_test_token()),
        )
        assert with_auth.status_code == 200
        assert with_auth.json() == {"decision": "synthetic_handoff"}
        repeated = await client.post(
            "/e0/execute", json=_request("valid"),
            headers=_attested(_test_token()),
        )
        assert repeated.status_code == 409
        forged = await client.post(
            "/e0/execute", json=_request("forged"),
            headers={
                "x-tenant": "church", "x-role": "workload",
                "x-forwarded-client-cert": "PRIVATE_NOT_AUTHENTICATED",
            },
        )
        assert forged.status_code == 403
    assert seen == ["church"]


@pytest.mark.asyncio
async def test_upstream_scope_spoofing_is_erased_without_valid_signature(
    tmp_path: Path,
):
    seen: list[str] = []
    app = _app(tmp_path / "spoof.sqlite3", seen)

    async def poisoned_scope(
        scope: Scope, receive: Receive, send: Send,
    ) -> None:
        copied = dict(scope)
        copied["schemarouter.e0_fixture_identity"] = SyntheticScopeIdentityE0(
            "emergency_operator", "church",
        )
        await app(copied, receive, send)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=poisoned_scope),
        base_url="http://synthetic.invalid",
    ) as client:
        response = await client.post("/e0/stop-all")
        assert response.status_code == 403
        response = await client.post(
            "/e0/execute", json=_request("untrusted"),
        )
        assert response.status_code == 403
    assert seen == []


@pytest.mark.parametrize("token", [
    _test_token(expiry=1005),  # already expired
    _test_token(issued=1020, expiry=1040),  # not yet valid
    _test_token(expiry=1200),  # overlong TTL
    _test_token(audience="other-app"),
    _test_token(role="superuser"),
    _test_token(role="tenant_operator"),  # improper nonempty workload
    _test_token(key=b"OTHER_SYNTHETIC_TEST_KEY_" + b"z" * 40),
    "not-a-valid-signed-token",
    "",
])
def test_expired_misaligned_and_forged_identity_fails_closed(token: str):
    verifier = SignedFixtureIdentityVerifierE0(
        _KEY, now=lambda: 1010.0,
    )
    assert verifier.verify(token) is None


@pytest.mark.asyncio
async def test_invalid_or_duplicate_authentication_headers_never_dispatch(
    tmp_path: Path,
):
    seen: list[str] = []
    app = _app(tmp_path / "headers.sqlite3", seen)
    original = _test_token()
    payload, signature = original.split(".")
    bad = payload + "." + signature[:-2] + "AB"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        for headers in [
            _attested(bad), _attested(original, duplicates=True),
            [("authorization", "Basic test")],
            [("authorization", "Bearer " + "a" * 1500)],
        ]:
            response = await client.post(
                "/e0/execute", json=_request("denied"), headers=headers,
            )
            assert response.status_code == 403
    assert seen == []


@pytest.mark.asyncio
async def test_separate_signed_operator_role_and_tenant_isolation(
    tmp_path: Path,
):
    seen: list[str] = []
    app = _app(tmp_path / "roles.sqlite3", seen)
    church_stop = _test_token(
        role="tenant_operator", tenant="church", workload="",
    )
    school_call = _test_token(tenant="school")
    emergency = _test_token(
        role="emergency_operator", tenant="control", workload="",
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        deny_global = await client.post(
            "/e0/stop-all", headers=_attested(church_stop),
        )
        assert deny_global.status_code == 403
        stopped = await client.post(
            "/e0/stop-tenant", headers=_attested(church_stop),
            json={"tenant": "school"},
        )
        assert stopped.status_code == 200
        assert stopped.json() == {
            "decision": "operator_revoked", "changed": True,
        }
        denied_church = await client.post(
            "/e0/execute", json=_request("church"),
            headers=_attested(_test_token()),
        )
        assert denied_church.status_code == 403
        allowed_school = await client.post(
            "/e0/execute", json=_request("school"),
            headers=_attested(school_call),
        )
        assert allowed_school.status_code == 200
        global_stop = await client.post(
            "/e0/stop-all", headers=_attested(emergency),
        )
        assert global_stop.status_code == 200
        denied_school = await client.post(
            "/e0/execute", json=_request("after-stop"),
            headers=_attested(school_call),
        )
        assert denied_school.status_code == 403
    assert seen == ["school"]



@pytest.mark.asyncio
async def test_bad_base64_padding_never_causes_asgi_500(tmp_path: Path):
    """Malformed auth can reach the decoder before a valid signature exists."""
    seen: list[str] = []
    app = _app(tmp_path / "malformed-b64.sqlite3", seen)
    payload_segment = "a"  # alphabet-valid but invalid Base64 padding
    valid_mac_for_invalid_payload = _base64(
        hmac.new(
            _KEY, _CONTEXT + payload_segment.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    malformed_assertions = [
        _test_token().split(".")[0] + ".a",  # malformed signature
        payload_segment + "." + valid_mac_for_invalid_payload,
    ]
    verifier = SignedFixtureIdentityVerifierE0(
        _KEY, now=lambda: 1010.0,
    )
    for candidate in malformed_assertions:
        assert verifier.verify(candidate) is None

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        for candidate in malformed_assertions:
            denied = await client.post(
                "/e0/execute",
                json=_request("bad-padding"),
                headers=_attested(candidate),
            )
            assert denied.status_code == 403
            assert denied.json() == {"decision": "identity_or_scope_denied"}
    assert seen == []


def test_wrong_key_or_unusable_clock_can_never_verify_assertion():
    verifier = SignedFixtureIdentityVerifierE0(
        b"A_NEW_SYNTHETIC_KEY_ONLY_" + b"x" * 40,
        now=lambda: 1010.0,
    )
    assert verifier.verify(_test_token()) is None
    verifier = SignedFixtureIdentityVerifierE0(
        _KEY, now=lambda: float("nan"),
    )
    assert verifier.verify(_test_token()) is None
    with pytest.raises(ValueError, match="signing key"):
        SignedFixtureIdentityVerifierE0(b"short")


@pytest.mark.asyncio
async def test_signed_bearer_never_reaches_downstream_asgi_headers(tmp_path: Path):
    authority = DurableCentralReservationE0(tmp_path / "redacted.sqlite3")
    authority.provision_once(
        allowed={("church", "agent-a", GEO): "source-revision-1"},
        cap_per_tenant_route=1,
    )
    emitted: list[str] = []
    seen_headers: list[tuple[bytes, bytes]] = []
    inner = make_synthetic_asgi_gateway_e0(
        authority, synthetic_sink=lambda request: emitted.append(request.request_id),
    )

    async def inspect(scope: Scope, receive: Receive, send: Send) -> None:
        seen_headers.extend(scope.get("headers", ()))
        await inner(scope, receive, send)

    app = SignedFixtureScopeMiddlewareE0(
        inspect,
        verifier=SignedFixtureIdentityVerifierE0(
            _KEY, now=lambda: 1010.0,
        ),
    )
    signed_token = _test_token()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        response = await client.post(
            "/e0/execute",
            json=_request("redacted"),
            headers=_attested(signed_token),
        )
    assert response.status_code == 200
    assert emitted == ["redacted"]
    assert all(name.lower() != b"authorization" for name, _ in seen_headers)
    assert signed_token not in response.text


@pytest.mark.asyncio
async def test_non_http_asgi_scope_cannot_inherit_upstream_forged_identity():
    seen: list[object] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope.get("schemarouter.e0_fixture_identity"))

    protected = SignedFixtureScopeMiddlewareE0(
        downstream,
        verifier=SignedFixtureIdentityVerifierE0(
            _KEY, now=lambda: 1010.0,
        ),
    )

    async def unused_receive() -> dict[str, str]:
        return {"type": "websocket.disconnect"}

    async def unused_send(message: object) -> None:
        raise AssertionError("no websocket network activity is allowed")

    for protocol in ("websocket", "lifespan"):
        await protected(
            {
                "type": protocol,
                "schemarouter.e0_fixture_identity": SyntheticScopeIdentityE0(
                    "emergency_operator", "church",
                ),
            },  # type: ignore[arg-type]
            unused_receive,
            unused_send,
        )
    assert seen == [None, None]
