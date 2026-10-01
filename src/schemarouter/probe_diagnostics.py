from __future__ import annotations

from typing import Literal, cast

import httpx
from pydantic import Field

from .errors import AdapterProbeError
from .models import StrictModel

ProbeStatus = Literal[
    "recognized",
    "not_recognized",
    "skipped_active",
    "unreachable",
    "authentication_failed",
    "invalid_schema",
    "unsupported_feature",
    "protocol_error",
]


class SourceProbeDiagnostic(StrictModel):
    """Credential-free diagnostic for one adapter considered during probing."""

    adapter_kind: str
    activity: Literal["passive", "active"] | None = None
    status: ProbeStatus
    error_type: str | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    message: str = ""


def http_probe_error(
    adapter_kind: str,
    exc: Exception,
    *,
    operation: str,
) -> AdapterProbeError:
    """Classify HTTP transport failures without copying remote bodies or secrets."""

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401, 403}:
            category = "authentication_failed"
            message = f"{operation} was refused with HTTP {status}"
        elif status == 404:
            category = "unreachable"
            message = f"{operation} was not found"
        elif status in {408, 425, 429} or status >= 500:
            category = "unreachable"
            message = f"{operation} is temporarily unavailable with HTTP {status}"
        else:
            category = "protocol_error"
            message = f"{operation} failed with HTTP {status}"
        return AdapterProbeError(
            adapter_kind,
            category,
            message,
            status_code=status,
        )

    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return AdapterProbeError(
            adapter_kind,
            "unreachable",
            f"{operation} could not reach the remote source",
        )

    return AdapterProbeError(
        adapter_kind,
        "protocol_error",
        f"{operation} failed",
    )


def diagnostic_from_error(
    error: AdapterProbeError,
    *,
    activity: Literal["passive", "active"] | None,
) -> SourceProbeDiagnostic:
    allowed_failures = {
        "unreachable",
        "authentication_failed",
        "invalid_schema",
        "unsupported_feature",
        "protocol_error",
    }
    category = (
        error.category
        if error.category in allowed_failures
        else "protocol_error"
    )
    return SourceProbeDiagnostic(
        adapter_kind=error.adapter_kind,
        activity=activity,
        status=cast(ProbeStatus, category),
        error_type=(
            type(error.__cause__).__name__
            if error.__cause__ is not None
            else type(error).__name__
        ),
        status_code=error.status_code,
        message=str(error),
    )
