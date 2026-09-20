from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from .models import StrictModel


class RetryPolicy(StrictModel):
    """Deterministic retry policy applied at the trusted executor boundary."""

    max_attempts: int = Field(default=1, ge=1, le=10)
    initial_backoff_seconds: float = Field(default=0.0, ge=0.0, le=60.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    max_backoff_seconds: float = Field(default=30.0, ge=0.0, le=300.0)
    retry_non_read_only: bool = False


class RunConfig(StrictModel):
    """Per-run metadata and execution controls."""

    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    max_concurrency: int = Field(default=8, ge=1, le=128)
    include_payloads: bool = False
    retry: RetryPolicy = Field(default_factory=RetryPolicy)


RunEventName = Literal[
    "run.start",
    "plan.end",
    "tool.start",
    "tool.end",
    "tool.error",
    "run.end",
    "run.error",
]


class RunEvent(StrictModel):
    """Typed event envelope emitted by SchemaRouter streaming APIs."""

    event: RunEventName
    run_id: str
    sequence: int = Field(ge=0)
    timestamp: datetime
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool: str | None = None
    endpoint: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        event: RunEventName,
        run_id: str,
        sequence: int,
        config: RunConfig,
        tool: str | None = None,
        endpoint: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> RunEvent:
        return cls(
            event=event,
            run_id=run_id,
            sequence=sequence,
            timestamp=datetime.now(timezone.utc),
            tags=list(config.tags),
            metadata=dict(config.metadata),
            tool=tool,
            endpoint=endpoint,
            data=dict(data or {}),
        )
