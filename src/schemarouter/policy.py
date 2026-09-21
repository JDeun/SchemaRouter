from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from .errors import PolicyViolationError
from .models import EndpointSpec, ToolCall, ToolSpec

ApprovalMode = Literal["never", "non_read_only", "all"]
ApprovalCallback = Callable[
    [ToolSpec, EndpointSpec, ToolCall],
    bool | Awaitable[bool],
]


def is_remote_tool(tool: ToolSpec) -> bool:
    return bool(tool.metadata.get("remote")) or tool.metadata.get("adapter") in {
        "mcp",
        "openapi",
        "html_proposal",
    }


@dataclass(frozen=True)
class ExecutionPolicy:
    """Local execution authority for side effects and optional per-call approval."""

    allow_mutations: bool = False
    allow_destructive: bool = False
    allow_unclassified_remote: bool = False
    approval_mode: ApprovalMode = "never"

    def __post_init__(self) -> None:
        if self.approval_mode not in {"never", "non_read_only", "all"}:
            raise ValueError("approval_mode must be 'never', 'non_read_only', or 'all'")

    def requires_approval(self, endpoint: EndpointSpec) -> bool:
        if self.approval_mode == "all":
            return True
        if self.approval_mode == "non_read_only":
            return endpoint.read_only is not True
        return False

    def validate(
        self,
        tool: ToolSpec,
        endpoint: EndpointSpec,
        call: ToolCall,
    ) -> None:
        operation = f"{call.tool}.{call.endpoint}"

        if endpoint.destructive is True:
            if not self.allow_destructive:
                raise PolicyViolationError(
                    f"destructive operation {operation} requires allow_destructive=True"
                )
            return

        if endpoint.read_only is False:
            if not self.allow_mutations:
                raise PolicyViolationError(
                    f"mutating operation {operation} requires allow_mutations=True"
                )
            return

        if (
            endpoint.read_only is None
            and is_remote_tool(tool)
            and not self.allow_unclassified_remote
        ):
            raise PolicyViolationError(
                f"remote operation {operation} has unclassified side effects; "
                "set allow_unclassified_remote=True or provide a trusted local contract"
            )
