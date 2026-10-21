"""E0 only: exact-request HMAC proof tests; no sockets or provider calls."""
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
from scripts.research_request_bound_signed_fixture_e0 import (
    RequestBoundSignedFixtureE0,
)
from scripts.research_signed_fixture_identity_e0 import (
    SignedFixtureIdentityVerifierE0,
)

_IDENTITY_KEY = b"OFFLINE_E0_FIXTURE_IDENTITY_KEY_ONLY_012345678901234567"
_PROOF_KEY = b"OFFLINE_E0_FIXTURE_PROOF_KEY_ONLY_01234567890123456789"
_IDENTITY_CONTEXT = b"SchemaRouter E0 identity-boundary test only\x00"
_PROOF_CONTEXT = b"SchemaRouter E0 bound request proof (NOT IAM)\x00"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _token(
    *, role: str = "workload", tenant: str = "church",
    workload: str = "agent-a", expiry: int = 1040,
) -> str:
    payload = {
        "aud": "schemarouter-closed-network-e0",
        "exp": expiry,
        "iat": 1000,
        "role": role,
        "tenant": tenant,
        "workload": workload,
    }
    first = _b64(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
    )
    mac = hmac.new(
        _IDENTITY_KEY,
        _IDENTITY_CONTEXT + first.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return first + "." + _b64(mac)


def _body(request_id: str) -> bytes:
    return json.dumps({
        "request_id": request_id,
        "route_id": GEO,
        "source_fingerprint": "geo-1",
        "epoch": 1,
    }, separators=(",", ":")).encode("utf-8")


def _proof(
    token: str, *, method: str = "POST", path: str = "/e0/execute",
    body: bytes = b"",
) -> str:
    message = (
        _PROOF_CONTEXT + token.encode() + b"\x00"
        + method.encode() + b"\x00"
        + path.encode() + b"\x00"
        + hashlib.sha256(body).digest()
    )
    return _b64(hmac.new(_PROOF_KEY, message, hashlib.sha256).digest())


def _headers(
    token: str, *, body: bytes, path: str = "/e0/execute",
    method: str = "POST",
) -> list[tuple[str, str]]:
    return [
        ("authorization", "Bearer " + token),
        ("x-e0-request-proof", _proof(
            token, method=method, path=path, body=body,
        )),
        ("content-type", "application/json"),
    ]


def _app(path: Path, emitted: list[str]) -> RequestBoundSignedFixtureE0:
    authority = DurableCentralReservationE0(path)
    authority.provision_once(
        allowed={
            ("church", "agent-a", GEO): "geo-1",
            ("school", "agent-a", GEO): "geo-1",
        },
        cap_per_tenant_route=2,
    )
    source = make_synthetic_asgi_gateway_e0(
        authority, synthetic_sink=lambda req: emitted.append(
            req.tenant + ":" + req.request_id,
        ),
    )
    return RequestBoundSignedFixtureE0(
        source,
        identity_verifier=SignedFixtureIdentityVerifierE0(
            _IDENTITY_KEY, now=lambda: 1010.0,
        ),
        proof_key=_PROOF_KEY,
    )


@pytest.mark.asyncio
async def test_exact_request_bound_proof_allows_only_original_synthetic_call(
    tmp_path: Path,
):
    emitted: list[str] = []
    app = _app(tmp_path / "valid.sqlite3", emitted)
    token = _token()
    raw = _body("original")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        first = await client.post(
            "/e0/execute", content=raw,
            headers=_headers(token, body=raw),
        )
        assert first.status_code == 200
        assert first.json() == {"decision": "synthetic_handoff"}
        # A copied complete assertion cannot execute a duplicate idempotent
        # request again, but this is NOT sender-bound token theft protection.
        replay = await client.post(
            "/e0/execute", content=raw,
            headers=_headers(token, body=raw),
        )
        assert replay.status_code == 409
        assert replay.json() == {"decision": "duplicate_request"}
    assert emitted == ["church:original"]


@pytest.mark.asyncio
async def test_copied_bearer_cannot_change_signed_body_or_request_id(tmp_path):
    emitted: list[str] = []
    app = _app(tmp_path / "tampers.sqlite3", emitted)
    original = _body("first")
    stolen = _token()
    authentic = _headers(stolen, body=original)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        tampered = await client.post(
            "/e0/execute", content=_body("changed"),
            headers=authentic,
        )
        assert tampered.status_code == 403
        assert tampered.json() == {"decision": "identity_or_scope_denied"}
        other_endpoint = await client.post(
            "/e0/stop-all", content=original, headers=authentic,
        )
        assert other_endpoint.status_code == 403
        # Body-binding alone must NOT elevate workload role to operator.
        invalid_operator = await client.post(
            "/e0/stop-tenant", content=original,
            headers=_headers(stolen, body=original, path="/e0/stop-tenant"),
        )
        assert invalid_operator.status_code == 403
        correct = await client.post(
            "/e0/execute", content=original, headers=authentic,
        )
        assert correct.status_code == 200
    assert emitted == ["church:first"]


@pytest.mark.asyncio
async def test_operator_stop_is_bound_to_signed_role_path_and_body(tmp_path):
    emitted: list[str] = []
    app = _app(tmp_path / "operator.sqlite3", emitted)
    operator = _token(role="tenant_operator", tenant="church", workload="")
    body = b'{"tenant":"school"}'  # test payload cannot change scope tenant
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        stop = await client.post(
            "/e0/stop-tenant",
            content=body,
            headers=_headers(operator, path="/e0/stop-tenant", body=body),
        )
        assert stop.status_code == 200
        assert stop.json() == {"decision": "operator_revoked", "changed": True}
        # Captured operator assertion may not be switched to stop-all.
        wrong_endpoint = await client.post(
            "/e0/stop-all",
            content=body,
            headers=_headers(operator, path="/e0/stop-tenant", body=body),
        )
        assert wrong_endpoint.status_code == 403
        school = _token(tenant="school")
        school_raw = _body("school")
        outcome = await client.post(
            "/e0/execute", content=school_raw,
            headers=_headers(school, body=school_raw),
        )
        assert outcome.status_code == 200
        original = _token()
        original_raw = _body("church")
        denied = await client.post(
            "/e0/execute", content=original_raw,
            headers=_headers(original, body=original_raw),
        )
        assert denied.status_code == 403
    assert emitted == ["school:school"]


@pytest.mark.asyncio
async def test_header_tampering_missing_proof_and_wrong_binding_fail_closed(
    tmp_path: Path,
):
    emitted: list[str] = []
    app = _app(tmp_path / "invalid-proofs.sqlite3", emitted)
    raw = _body("unspent")
    token = _token()
    headers = _headers(token, body=raw)
    negative = [
        [headers[0], headers[2]],  # signed identity but NO request proof
        [*headers, headers[1]],  # duplicated proof
        [(headers[0][0], headers[0][1]), ("x-e0-request-proof", "a")],
        _headers(token, body=raw, method="GET"),
        _headers(token, body=b"tampered"),
        _headers(_token(expiry=1005), body=raw),
        _headers(_token(tenant="school"), body=raw)[:1] + headers[1:],
    ]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        for bad in negative:
            outcome = await client.post(
                "/e0/execute", content=raw, headers=bad,
            )
            assert outcome.status_code == 403
            assert outcome.json() == {"decision": "identity_or_scope_denied"}
    assert emitted == []
    assert DurableCentralReservationE0(
        tmp_path / "invalid-proofs.sqlite3",
    ).reserved_for_test("church", GEO) == 0


@pytest.mark.asyncio
async def test_body_bound_and_buffered_once_for_existing_asgi_app(tmp_path):
    emitted: list[str] = []
    app = _app(tmp_path / "body-forward.sqlite3", emitted)
    body = _body("body-once")
    token = _token()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        result = await client.post(
            "/e0/execute", content=body,
            headers=_headers(token, body=body),
        )
        assert result.status_code == 200
        # Proof is over actual raw bytes, not semantic JSON equivalence.
        with_spaces = json.dumps(json.loads(body)).encode()
        denied = await client.post(
            "/e0/execute", content=with_spaces,
            headers=_headers(token, body=body),
        )
        assert denied.status_code == 403
        too_big = b" " * 2100
        blocked = await client.post(
            "/e0/execute", content=too_big,
            headers=_headers(token, body=too_big),
        )
        assert blocked.status_code == 400
    assert emitted == ["church:body-once"]


@pytest.mark.asyncio
async def test_request_proof_removed_from_downstream_headers(tmp_path):
    authority = DurableCentralReservationE0(tmp_path / "redact.sqlite3")
    authority.provision_once(
        allowed={("church", "agent-a", GEO): "geo-1"},
        cap_per_tenant_route=1,
    )
    forwarded_headers: list[tuple[bytes, bytes]] = []
    calls: list[str] = []
    base = make_synthetic_asgi_gateway_e0(
        authority, synthetic_sink=lambda req: calls.append(req.request_id),
    )

    async def inspect(
        scope: Scope, receive: Receive, send: Send,
    ) -> None:
        forwarded_headers.extend(scope.get("headers", []))
        await base(scope, receive, send)

    app = RequestBoundSignedFixtureE0(
        inspect,
        identity_verifier=SignedFixtureIdentityVerifierE0(
            _IDENTITY_KEY, now=lambda: 1010.0,
        ),
        proof_key=_PROOF_KEY,
    )
    token, raw = _token(), _body("redact")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        ok = await client.post(
            "/e0/execute", content=raw, headers=_headers(token, body=raw),
        )
    assert ok.status_code == 200
    assert calls == ["redact"]
    names = {k.lower() for k, _ in forwarded_headers}
    assert b"authorization" not in names
    assert b"x-e0-request-proof" not in names
