"""E0 ONLY: request-bound synthetic ASGI assertion, not production IAM.

A valid signed *fixture* Bearer assertion is also bound to one exact HTTP
method, fixed ASGI path and request-body bytes by a separate test-only HMAC.
This reduces credential-only cross-request reuse; copying the COMPLETE
Bearer+proof+body is still replayable. The merged SQLite E0 idempotency
store limits duplicate *execute* request IDs, but it is NOT sender-binding,
a real token issuer, certificate-based IAM or a network egress proxy.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from scripts.research_signed_fixture_identity_e0 import (
    SignedFixtureIdentityVerifierE0,
    SignedFixtureScopeMiddlewareE0,
)

_CONTEXT = b"SchemaRouter E0 bound request proof (NOT IAM)\x00"
_PATHS = frozenset(("/e0/execute", "/e0/stop-tenant", "/e0/stop-all"))
_BODY_CAP = 2048
_CHUNK_CAP = 32
_PROOF_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _message(
    bearer: str, *, method: str, path: str, body: bytes,
) -> bytes:
    return (
        _CONTEXT
        + bearer.encode("ascii") + b"\x00"
        + method.encode("ascii") + b"\x00"
        + path.encode("ascii") + b"\x00"
        + hashlib.sha256(body).digest()
    )


class RequestBoundSignedFixtureE0:
    """Authenticated *synthetic* request bytes; never authorize provider GET."""

    def __init__(
        self, app: ASGIApp, *,
        identity_verifier: SignedFixtureIdentityVerifierE0,
        proof_key: bytes,
    ) -> None:
        if (
            not callable(app)
            or not isinstance(
                identity_verifier, SignedFixtureIdentityVerifierE0,
            )
            or type(proof_key) is not bytes
            or len(proof_key) < 32
        ):
            raise ValueError("trusted offline request verifier required")
        self._key = proof_key
        self._identity = identity_verifier
        self._app = SignedFixtureScopeMiddlewareE0(
            app, verifier=identity_verifier,
        )

    def _validate(
        self, *, bearer: str, signature: str,
        method: str, path: str, body: bytes,
    ) -> bool:
        if (
            method != "POST"
            or path not in _PATHS
            or type(bearer) is not str
            or type(signature) is not str
            or _PROOF_RE.fullmatch(signature) is None
            or self._identity.verify(bearer) is None
        ):
            return False
        try:
            raw = base64.b64decode(
                signature + "=", altchars=b"-_", validate=True,
            )
            expected = hmac.new(
                self._key,
                _message(bearer, method=method, path=path, body=body),
                hashlib.sha256,
            ).digest()
            return hmac.compare_digest(raw, expected)
        except (UnicodeEncodeError, ValueError, binascii.Error):
            return False

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send,
    ) -> None:
        if scope.get("type") != "http":
            # Underlying merged fixture middleware removes any upstream
            # injected identity from all non-HTTP ASGI scopes.
            await self._app(scope, receive, send)
            return

        async def deny() -> None:
            await JSONResponse(
                {"decision": "identity_or_scope_denied"}, status_code=403,
            )(scope, receive, send)

        headers = scope.get("headers", ())
        auth = [
            v for k, v in headers if k.lower() == b"authorization"
        ]
        proofs = [
            v for k, v in headers if k.lower() == b"x-e0-request-proof"
        ]
        if (
            len(auth) != 1 or len(proofs) != 1
            or not auth[0].startswith(b"Bearer ")
            or len(auth[0]) > 1031
            or len(proofs[0]) > 64
        ):
            await deny()
            return
        try:
            bearer = auth[0][7:].decode("ascii")
            proof = proofs[0].decode("ascii")
        except UnicodeDecodeError:
            await deny()
            return
        # Validate the signed *identity* before allocating a request body;
        # a forged Bearer cannot force buffering an arbitrarily long body.
        if self._identity.verify(bearer) is None:
            await deny()
            return
        body = bytearray()
        for _ in range(_CHUNK_CAP):
            message = await receive()
            if message.get("type") != "http.request":
                await deny()
                return
            piece = message.get("body", b"")
            if not isinstance(piece, bytes) or len(body) + len(piece) > _BODY_CAP:
                await JSONResponse(
                    {"decision": "invalid_request"}, status_code=400,
                )(scope, receive, send)
                return
            body.extend(piece)
            if not message.get("more_body", False):
                break
        else:
            await JSONResponse(
                {"decision": "invalid_request"}, status_code=400,
            )(scope, receive, send)
            return

        method, path = scope.get("method"), scope.get("path")
        if (
            type(method) is not str or type(path) is not str
            or not self._validate(
                bearer=bearer, signature=proof, method=method,
                path=path, body=bytes(body),
            )
        ):
            await deny()
            return

        # Remove the proof credential. The existing signed-identity
        # middleware removes the Bearer before passing on to the E0 app.
        scrubbed = dict(scope)
        scrubbed["headers"] = [
            (name, value) for name, value in headers
            if name.lower() != b"x-e0-request-proof"
        ]
        sent = False

        async def replay_body() -> dict[str, object]:
            nonlocal sent
            if not sent:
                sent = True
                return {
                    "type": "http.request", "body": bytes(body),
                    "more_body": False,
                }
            # A later downstream receive may wait for disconnect; preserve
            # normal ASGI semantics rather than yielding a second body.
            return await receive()

        await self._app(scrubbed, replay_body, send)
