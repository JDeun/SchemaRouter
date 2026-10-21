"""Test-only signed E0 ASGI identity boundary; NOT a production IAM layer.

The isolated local HMAC authority here is a *synthetic* test fixture. It
does not implement mTLS, a real credential issuer, key lifecycle, operator
authentication, external HTTP transport, or multi-host trust. The wrapper
overwrites any unverified scope identity rather than trusting caller headers.
Never deploy this as a public endpoint or use it as product authorization.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import time
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from scripts.research_central_asgi_boundary_e0 import (
    SyntheticScopeIdentityE0,
)

_SCOPE_KEY = "schemarouter.e0_fixture_identity"
_AUDIENCE = "schemarouter-closed-network-e0"
_CONTEXT = b"SchemaRouter E0 identity-boundary test only\x00"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_MAX_TOKEN_BYTES = 1024
_MAX_SECONDS = 60


def _decode_part(part: str) -> bytes:
    if not part or re.fullmatch(r"[A-Za-z0-9_-]+", part) is None:
        raise ValueError("invalid synthetic assertion")
    return base64.b64decode(
        part + "=" * ((-len(part)) % 4), altchars=b"-_", validate=True,
    )


class SignedFixtureIdentityVerifierE0:
    """Offline HMAC verifier with audience/role/expiry and no trust fallback."""

    def __init__(
        self, key: bytes, *, now: Callable[[], float] | None = None,
    ) -> None:
        if type(key) is not bytes or len(key) < 32:
            raise ValueError("trusted test-only signing key required")
        self._key = key
        self._now = now if now is not None else time.time
        if not callable(self._now):
            raise ValueError("trusted fixture clock required")

    def verify(self, token: str) -> SyntheticScopeIdentityE0 | None:
        if (
            type(token) is not str
            or len(token) > _MAX_TOKEN_BYTES
            or _TOKEN_RE.fullmatch(token) is None
        ):
            return None
        try:
            payload_segment, signature_segment = token.split(".")
            supplied = _decode_part(signature_segment)
            if len(supplied) != hashlib.sha256().digest_size:
                return None
            canonical = payload_segment.encode("ascii")
            expected = hmac.new(
                self._key, _CONTEXT + canonical, hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(supplied, expected):
                return None
            payload = json.loads(_decode_part(payload_segment))
            if type(payload) is not dict or set(payload) != {
                "aud", "exp", "iat", "role", "tenant", "workload",
            }:
                return None
            if (
                payload["aud"] != _AUDIENCE
                or type(payload["exp"]) is not int
                or type(payload["iat"]) is not int
                or type(payload["tenant"]) is not str
                or type(payload["workload"]) is not str
                or type(payload["role"]) is not str
                or not 0 < len(payload["tenant"]) <= 128
                or len(payload["workload"]) > 128
                or payload["role"] not in (
                    "workload", "tenant_operator", "emergency_operator",
                )
                or (
                    payload["role"] == "workload"
                    and not payload["workload"]
                )
                or (
                    payload["role"] != "workload"
                    and bool(payload["workload"])
                )
            ):
                return None
            current = self._now()
            if not isinstance(current, (int, float)) or not math.isfinite(current):
                return None
            issued, expiry = payload["iat"], payload["exp"]
            if (
                issued > current + 5
                or expiry <= current
                or expiry <= issued
                or expiry - issued > _MAX_SECONDS
            ):
                return None
            return SyntheticScopeIdentityE0(
                role=payload["role"],
                tenant=payload["tenant"],
                workload=payload["workload"],
            )
        except (ValueError, UnicodeDecodeError, TypeError, OverflowError):
            return None


class SignedFixtureScopeMiddlewareE0:
    """Never preserve caller-populated identity; verify an offline token."""

    def __init__(
        self, app: ASGIApp, *,
        verifier: SignedFixtureIdentityVerifierE0,
    ) -> None:
        if not callable(app) or not isinstance(
            verifier, SignedFixtureIdentityVerifierE0,
        ):
            raise ValueError("trusted E0 app and identity verifier required")
        self._app = app
        self._verifier = verifier

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return
        # Scope can be assembled by an untrusted upstream ASGI layer.
        # Remove any pre-injected fixture identity on EVERY HTTP request.
        trusted_scope = dict(scope)
        trusted_scope.pop(_SCOPE_KEY, None)
        headers = scope.get("headers", ())
        authorization = [
            value for name, value in headers
            if name.lower() == b"authorization"
        ]
        if len(authorization) == 1 and len(authorization[0]) < _MAX_TOKEN_BYTES:
            value = authorization[0]
            if value.startswith(b"Bearer "):
                try:
                    token = value[7:].decode("ascii")
                    identity = self._verifier.verify(token)
                except UnicodeDecodeError:
                    identity = None
                if identity is not None:
                    trusted_scope[_SCOPE_KEY] = identity
        await self._app(trusted_scope, receive, send)
