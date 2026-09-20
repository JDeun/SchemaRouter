from __future__ import annotations

from dataclasses import dataclass

from .errors import PolicyViolationError
from .models import EndpointSpec, ToolCall, ToolSpec


@dataclass(frozen=True)
class ExecutionPolicy:
    """Local execution authority for side effects.

    Remote schema metadata cannot grant these permissions. The caller must opt in locally.
    """

    allow_mutations: bool = False
    allow_destructive: bool = False
    allow_unclassified_remote: bool = False

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

        is_remote = bool(tool.metadata.get("remote")) or tool.metadata.get("adapter") in {
            "mcp",
            "openapi",
            "html_proposal",
        }
        if endpoint.read_only is None and is_remote and not self.allow_unclassified_remote:
            raise PolicyViolationError(
                f"remote operation {operation} has unclassified side effects; "
                "set allow_unclassified_remote=True or provide a trusted local contract"
            )
