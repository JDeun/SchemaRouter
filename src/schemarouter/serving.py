from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict

from .errors import (
    ApprovalDeniedError,
    BindingDriftError,
    ExecutionBudgetExceededError,
    ExecutionError,
    PlanningError,
    PlanValidationError,
    PolicyViolationError,
    SchemaDriftError,
    SchemaRouterError,
    SchemaValidationError,
)
from .models import PlanRequest
from .runs import RunConfig
from .runtime import SchemaRouter
from .models import StrictModel

_MAX_HTTP_REQUEST_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class HTTPServerPolicy:
    """Trusted local policy for the optional HTTP serving adapter."""

    bearer_token: str | None = None
    max_request_bytes: int = 1024 * 1024
    expose_error_messages: bool = False
    expose_docs: bool = False

    def __post_init__(self) -> None:
        if self.bearer_token is not None:
            if not self.bearer_token:
                raise ValueError("bearer_token must be non-empty when provided")
            if "\r" in self.bearer_token or "\n" in self.bearer_token:
                raise ValueError("bearer_token must not contain CR/LF characters")
        if not 1 <= self.max_request_bytes <= _MAX_HTTP_REQUEST_BYTES:
            raise ValueError(
                f"max_request_bytes must be between 1 and {_MAX_HTTP_REQUEST_BYTES}"
            )


class _PlanEnvelope(StrictModel):
    model_config = ConfigDict(extra="forbid")

    request: PlanRequest | str


class _InvokeEnvelope(StrictModel):
    model_config = ConfigDict(extra="forbid")

    request: PlanRequest | str
    config: RunConfig | None = None


def _error_status(exc: SchemaRouterError) -> int:
    if isinstance(exc, (ApprovalDeniedError, PolicyViolationError)):
        return 403
    if isinstance(exc, ExecutionBudgetExceededError):
        return 429
    if isinstance(exc, (SchemaDriftError, BindingDriftError)):
        return 409
    if isinstance(exc, (PlanningError, PlanValidationError, SchemaValidationError)):
        return 422
    if isinstance(exc, ExecutionError):
        return 500
    return 500


def create_app(
    router: SchemaRouter,
    *,
    policy: HTTPServerPolicy | None = None,
) -> Any:
    """Create an optional FastAPI app around an already-configured SchemaRouter.

    The app intentionally exposes planning/invocation only. It does not expose schema ingestion,
    registry mutation, proposal approval, adapter loading, or arbitrary Python execution.
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise ImportError(
            'HTTP serving requires: pip install "schemarouter[server]"'
        ) from exc

    server_policy = policy or HTTPServerPolicy()
    app = FastAPI(
        title="SchemaRouter",
        docs_url="/docs" if server_policy.expose_docs else None,
        redoc_url="/redoc" if server_policy.expose_docs else None,
        openapi_url="/openapi.json" if server_policy.expose_docs else None,
    )

    async def json_error(
        status_code: int,
        error: str,
        *,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {"error": error}
        if detail is not None:
            payload["detail"] = detail
        return JSONResponse(
            status_code=status_code,
            content=payload,
            headers=headers,
        )

    @app.middleware("http")
    async def enforce_http_boundary(request: Any, call_next: Any) -> Any:
        path = request.url.path

        if path.startswith("/v1/") and server_policy.bearer_token is not None:
            authorization = request.headers.get("authorization")
            if authorization is None:
                return await json_error(
                    401,
                    "Unauthorized",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            scheme, separator, presented = authorization.partition(" ")
            valid = (
                bool(separator)
                and scheme.lower() == "bearer"
                and bool(presented)
                and secrets.compare_digest(
                    presented.encode("utf-8"),
                    server_policy.bearer_token.encode("utf-8"),
                )
            )
            if not valid:
                return await json_error(
                    401,
                    "Unauthorized",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        if request.method in {"POST", "PUT", "PATCH"}:
            declared = request.headers.get("content-length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError:
                    return await json_error(400, "InvalidContentLength")
                if declared_size < 0:
                    return await json_error(400, "InvalidContentLength")
                if declared_size > server_policy.max_request_bytes:
                    return await json_error(413, "RequestBodyTooLarge")

            body = await request.body()
            if len(body) > server_policy.max_request_bytes:
                return await json_error(413, "RequestBodyTooLarge")

        return await call_next(request)

    @app.exception_handler(SchemaRouterError)
    async def handle_schemarouter_error(request: Any, exc: SchemaRouterError) -> Any:
        del request
        detail = str(exc) if server_policy.expose_error_messages else None
        return await json_error(
            _error_status(exc),
            type(exc).__name__,
            detail=detail,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/schemas")
    async def schemas() -> dict[str, Any]:
        return {
            "input": router.input_schema,
            "output": router.output_schema,
            "config": router.config_schema,
        }

    @app.post("/v1/plan")
    async def plan(envelope: _PlanEnvelope) -> Any:
        return await router.aplan(envelope.request)

    @app.post("/v1/invoke")
    async def invoke(envelope: _InvokeEnvelope) -> Any:
        return await router.ainvoke(
            envelope.request,
            config=envelope.config,
        )

    return app
