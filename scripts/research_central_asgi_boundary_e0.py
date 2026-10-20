"""Offline E0 ASGI gateway boundary: NO IAM and NO provider egress.

Only an explicitly trusted ASGI-scope fixture may supply workload/operator
identity. HTTP body and headers can NEVER authorize themselves. This app is
not a deployable public gateway; real mTLS/identity attestation, durable
central storage and network egress ownership are not implemented here.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import anyio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from scripts.research_central_durable_reservation_e0 import (
    DurableCentralReservationE0,
)
from scripts.research_central_egress_admission_e0 import (
    SyntheticEgressRequestE0,
)

_SCOPE_KEY = "schemarouter.e0_fixture_identity"
_MAX_BODY_BYTES = 2048
_Route = Literal["workload", "tenant_operator", "emergency_operator"]


@dataclass(frozen=True)
class SyntheticScopeIdentityE0:
    """Only a TEST-SCOPE label; never a credential or authorization proof."""

    role: _Route
    tenant: str
    workload: str = ""


def _trusted_fixture_identity(
    request: Request,
    *,
    role: _Route,
) -> SyntheticScopeIdentityE0 | None:
    candidate = request.scope.get(_SCOPE_KEY)
    if (
        type(candidate) is not SyntheticScopeIdentityE0
        or candidate.role != role
        or type(candidate.tenant) is not str
        or not 0 < len(candidate.tenant) <= 128
        or type(candidate.workload) is not str
        or (role == "workload" and not 0 < len(candidate.workload) <= 128)
    ):
        return None
    return candidate


def _status(decision: str) -> int:
    if decision in ("synthetic_handoff", "synthetic_reservation"):
        return 200
    if decision in ("duplicate_request", "synthetic_handoff_already_claimed"):
        return 409
    if decision == "synthetic_authority_unavailable":
        return 503
    return 403


async def _bounded_json(request: Request) -> dict[str, object] | None:
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        return None
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > _MAX_BODY_BYTES:
            return None
        data.extend(chunk)
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError, TypeError):
        return None
    if type(value) is not dict or set(value) != {
        "request_id", "route_id", "source_fingerprint", "epoch",
    }:
        return None
    return value


def make_synthetic_asgi_gateway_e0(
    authority: DurableCentralReservationE0,
    *,
    synthetic_sink: Callable[[SyntheticEgressRequestE0], None],
) -> Starlette:
    """Create one offline E0 gateway with test-injected identity and sink.

    The app never accepts identity from HTTP headers, request JSON, tokens
    supplied by a model, or the network. A caller with no separately injected
    verified ASGI fixture identity is denied. It has NO real authentication.
    """
    if not isinstance(authority, DurableCentralReservationE0):
        raise ValueError("trusted pre-provisioned E0 authority required")
    if not callable(synthetic_sink):
        raise ValueError("offline synthetic sink required")

    async def execute(request: Request) -> JSONResponse:
        identity = _trusted_fixture_identity(request, role="workload")
        if identity is None:
            return JSONResponse({"decision": "identity_or_scope_denied"}, status_code=403)
        payload = await _bounded_json(request)
        if payload is None:
            return JSONResponse({"decision": "invalid_request"}, status_code=400)
        candidate = SyntheticEgressRequestE0(
            tenant=identity.tenant,
            workload=identity.workload,
            request_id=payload["request_id"],
            route_id=payload["route_id"],
            source_fingerprint=payload["source_fingerprint"],
            epoch=payload["epoch"],
        )

        def attempt() -> str:
            reserved = authority.reserve(candidate)
            if reserved != "synthetic_reservation":
                return reserved
            return authority.synthetic_handoff_after_reservation(
                candidate,
                synthetic_sink=lambda: synthetic_sink(candidate),
            )

        try:
            decision = await anyio.to_thread.run_sync(attempt)
        except Exception:
            decision = "synthetic_authority_unavailable"
        return JSONResponse({"decision": decision}, status_code=_status(decision))

    async def stop_tenant(request: Request) -> JSONResponse:
        identity = _trusted_fixture_identity(request, role="tenant_operator")
        if identity is None:
            return JSONResponse({"decision": "identity_or_scope_denied"}, status_code=403)
        try:
            stopped = await anyio.to_thread.run_sync(
                authority.revoke_tenant, identity.tenant,
            )
        except Exception:
            return JSONResponse(
                {"decision": "synthetic_authority_unavailable"},
                status_code=503,
            )
        return JSONResponse({"decision": "operator_revoked", "changed": stopped})

    async def stop_all(request: Request) -> JSONResponse:
        identity = _trusted_fixture_identity(request, role="emergency_operator")
        if identity is None:
            return JSONResponse({"decision": "identity_or_scope_denied"}, status_code=403)
        try:
            stopped = await anyio.to_thread.run_sync(authority.revoke_all)
        except Exception:
            return JSONResponse(
                {"decision": "synthetic_authority_unavailable"},
                status_code=503,
            )
        return JSONResponse({"decision": "operator_revoked", "changed": stopped})

    return Starlette(
        routes=[
            Route("/e0/execute", execute, methods=["POST"]),
            Route("/e0/stop-tenant", stop_tenant, methods=["POST"]),
            Route("/e0/stop-all", stop_all, methods=["POST"]),
        ],
    )
