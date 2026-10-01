from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field

from .errors import RegistrationError
from .executor import BoundEndpointInvoker
from .models import StrictModel, ToolSpec

BindingReconciliationStatus = Literal[
    "ready",
    "intentionally_unbound",
    "missing_trusted_config",
    "incompatible",
    "failed",
]


@dataclass(frozen=True)
class TrustedBindingConfig:
    """Process-local authority used to rebind one persisted ToolSpec.

    None of these live objects or credential values are serializable registry state.
    """

    intentionally_unbound: bool = False
    base_url: str | None = None
    trusted_headers: Mapping[str, str] | None = field(
        default=None,
        repr=False,
    )
    timeout: float = 20.0
    max_response_bytes: int = 10 * 1024 * 1024

    # Generic escape hatch for SDK/private adapters whose live transport cannot
    # be reconstructed from a persisted schema document.
    invoker: BoundEndpointInvoker | None = field(default=None, repr=False)

    # First-class process-local objects for adapters SchemaRouter already owns.
    python_callable: Callable[..., Any] | None = field(default=None, repr=False)
    langchain_tool: Any | None = field(default=None, repr=False)
    llamaindex_tool: Any | None = field(default=None, repr=False)

    # MCP HTTP and caller-owned bound transports are intentionally separate:
    # the former is a protocol client constructor, the latter owns a complete
    # trusted session/stdio/custom transport lifecycle.
    mcp_http_client_factory: Any | None = field(default=None, repr=False)
    mcp_bound_factory: Any | None = field(default=None, repr=False)
    mcp_transport_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if self.intentionally_unbound and any(
            value is not None
            for value in (
                self.base_url,
                self.trusted_headers,
                self.invoker,
                self.python_callable,
                self.langchain_tool,
                self.llamaindex_tool,
                self.mcp_http_client_factory,
                self.mcp_bound_factory,
                self.mcp_transport_fingerprint,
            )
        ):
            raise ValueError(
                "intentionally_unbound cannot be combined with live binding configuration"
            )
        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or not math.isfinite(float(self.timeout))
            or self.timeout <= 0
        ):
            raise ValueError("binding timeout must be a finite positive number")
        if (
            isinstance(self.max_response_bytes, bool)
            or not isinstance(self.max_response_bytes, int)
            or self.max_response_bytes <= 0
        ):
            raise ValueError("max_response_bytes must be a positive integer")
        if self.base_url is not None and not self.base_url.strip():
            raise ValueError("base_url must be non-empty when provided")
        if self.mcp_transport_fingerprint is not None and (
            not self.mcp_transport_fingerprint.strip()
        ):
            raise ValueError(
                "mcp_transport_fingerprint must be non-empty when provided"
            )

        live_authorities = (
            self.invoker is not None,
            self.python_callable is not None,
            self.langchain_tool is not None,
            self.llamaindex_tool is not None,
            self.mcp_bound_factory is not None,
        )
        if sum(live_authorities) > 1:
            raise ValueError(
                "trusted binding config must declare at most one live authority object"
            )
        if (
            self.mcp_bound_factory is not None
            and self.mcp_http_client_factory is not None
        ):
            raise ValueError(
                "MCP HTTP and bound transport factories are mutually exclusive"
            )
        if self.invoker is not None and any(
            (
                self.base_url is not None,
                self.trusted_headers is not None,
                self.mcp_http_client_factory is not None,
                self.mcp_transport_fingerprint is not None,
            )
        ):
            raise ValueError(
                "generic invoker binding cannot be combined with adapter transport config"
            )


class BindingReconciliationItem(StrictModel):
    """Safe startup binding status for one persisted capability."""

    tool: str
    adapter: str | None = None
    fingerprint: str
    status: BindingReconciliationStatus
    error_type: str | None = None


class BindingReconciliationReport(StrictModel):
    """Aggregate startup binding readiness without exposing live runtime state."""

    items: list[BindingReconciliationItem] = Field(default_factory=list)

    @property
    def ready(self) -> tuple[str, ...]:
        return tuple(
            item.tool
            for item in self.items
            if item.status == "ready"
        )

    @property
    def unready(self) -> tuple[str, ...]:
        return tuple(
            item.tool
            for item in self.items
            if item.status != "ready"
        )


class BindingReconciliationError(RegistrationError):
    """Strict startup failure that retains the privacy-safe reconciliation report."""

    def __init__(
        self,
        message: str,
        report: BindingReconciliationReport,
    ) -> None:
        super().__init__(message)
        self.report = report.model_copy(deep=True)


BindingResolver = Callable[[ToolSpec], TrustedBindingConfig | None]
